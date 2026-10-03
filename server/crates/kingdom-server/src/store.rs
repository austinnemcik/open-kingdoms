//! Synchronous persistence, invoked only from blocking workers by the server.
use game_core::{City, PlayerId};
use rusqlite::{Connection, OptionalExtension, params};
use sha2::{Digest, Sha256};
use std::{path::Path, time::Duration};

/// Persistence failures never include credentials in client responses.
#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("database: {0}")]
    Sql(#[from] rusqlite::Error),
    #[error("city serialization: {0}")]
    Json(#[from] serde_json::Error),
    #[error("unsupported database schema version {0}")]
    Schema(u32),
}

/// Account identity and its encoded, salted Argon2id password hash.
pub struct Account {
    pub id: PlayerId,
    pub password_hash: String,
}

/// Storage boundary. Callers serialize mutations and run all methods off-runtime.
pub trait Store: Send {
    /// Look up credentials using the exact, case-sensitive account name.
    fn account(&self, name: &str) -> Result<Option<Account>, StoreError>;
    /// Atomically create the identity, credentials, and starting city.
    fn register(&mut self, name: &str, hash: &str, city: &City) -> Result<PlayerId, StoreError>;
    /// Persist a new bearer session before returning it to the client.
    fn save_session(
        &self,
        token: &str,
        player: PlayerId,
        now: u64,
        ttl: u64,
        cap: u32,
    ) -> Result<(), StoreError>;
    /// Resolve a previously issued bearer token.
    fn session(&self, token: &str, now: u64) -> Result<Option<(PlayerId, String)>, StoreError>;
    /// Load a player's authoritative city.
    fn city(&self, player: PlayerId) -> Result<Option<City>, StoreError>;
    /// Replace a city atomically after applying pure rules.
    fn save_city(&self, player: PlayerId, city: &City) -> Result<(), StoreError>;
    /// Enumerate owners for background timer processing.
    fn player_ids(&self) -> Result<Vec<PlayerId>, StoreError>;
}

/// Bundled SQLite connection with foreign keys, WAL, and versioned migrations.
pub struct SqliteStore {
    connection: Connection,
}
impl SqliteStore {
    /// Open a file (or `:memory:` for isolated tests) and apply migrations.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, StoreError> {
        let mut connection = Connection::open(path)?;
        connection.busy_timeout(Duration::from_secs(5))?;
        connection.execute_batch(
            "PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL;",
        )?;
        let version: u32 = connection.query_row("PRAGMA user_version", [], |r| r.get(0))?;
        if version > 2 {
            return Err(StoreError::Schema(version));
        }
        if version == 0 {
            let tx = connection.transaction()?;
            tx.execute_batch(include_str!("../migrations/001_initial.sql"))?;
            tx.commit()?;
        }
        if version < 2 {
            let tx = connection.transaction()?;
            tx.execute_batch(include_str!("../migrations/002_hashed_sessions.sql"))?;
            tx.commit()?;
        }
        Ok(Self { connection })
    }
}
impl Store for SqliteStore {
    fn account(&self, name: &str) -> Result<Option<Account>, StoreError> {
        Ok(self.connection.query_row("SELECT p.id, c.password_hash FROM players p JOIN credentials c ON c.player_id=p.id WHERE p.name=?1", [name], |r| Ok(Account { id: r.get(0)?, password_hash: r.get(1)? })).optional()?)
    }
    fn register(&mut self, name: &str, hash: &str, city: &City) -> Result<PlayerId, StoreError> {
        let json = serde_json::to_string(city)?;
        let tx = self.connection.transaction()?;
        tx.execute("INSERT INTO players(name) VALUES (?1)", [name])?;
        let id = tx.last_insert_rowid() as PlayerId;
        tx.execute(
            "INSERT INTO credentials(player_id,password_hash) VALUES (?1,?2)",
            params![id, hash],
        )?;
        tx.execute(
            "INSERT INTO cities(player_id,state_json) VALUES (?1,?2)",
            params![id, json],
        )?;
        tx.commit()?;
        Ok(id)
    }
    fn save_session(
        &self,
        token: &str,
        player: PlayerId,
        now: u64,
        ttl: u64,
        cap: u32,
    ) -> Result<(), StoreError> {
        let tx = self.connection.unchecked_transaction()?;
        tx.execute("DELETE FROM sessions WHERE expires_at <= ?1", [now])?;
        tx.execute(
            "INSERT INTO sessions(token_hash,player_id,created_at,expires_at) VALUES (?1,?2,?3,?4)",
            params![
                Sha256::digest(token.as_bytes()).as_slice(),
                player,
                now,
                now.saturating_add(ttl).min(i64::MAX as u64)
            ],
        )?;
        tx.execute("DELETE FROM sessions WHERE player_id=?1 AND rowid NOT IN (SELECT rowid FROM sessions WHERE player_id=?1 ORDER BY created_at DESC, rowid DESC LIMIT ?2)", params![player, cap])?;
        tx.commit()?;
        Ok(())
    }
    fn session(&self, token: &str, now: u64) -> Result<Option<(PlayerId, String)>, StoreError> {
        self.connection
            .execute("DELETE FROM sessions WHERE expires_at <= ?1", [now])?;
        Ok(self.connection.query_row("SELECT p.id,p.name FROM sessions s JOIN players p ON p.id=s.player_id WHERE s.token_hash=?1 AND s.expires_at>?2", params![Sha256::digest(token.as_bytes()).as_slice(), now], |r| Ok((r.get(0)?,r.get(1)?))).optional()?)
    }
    fn city(&self, player: PlayerId) -> Result<Option<City>, StoreError> {
        let json: Option<String> = self
            .connection
            .query_row(
                "SELECT state_json FROM cities WHERE player_id=?1",
                [player],
                |r| r.get(0),
            )
            .optional()?;
        Ok(json.map(|text| serde_json::from_str(&text)).transpose()?)
    }
    fn save_city(&self, player: PlayerId, city: &City) -> Result<(), StoreError> {
        let changed = self.connection.execute(
            "UPDATE cities SET state_json=?2 WHERE player_id=?1",
            params![player, serde_json::to_string(city)?],
        )?;
        if changed != 1 {
            return Err(rusqlite::Error::QueryReturnedNoRows.into());
        }
        Ok(())
    }
    fn player_ids(&self) -> Result<Vec<PlayerId>, StoreError> {
        let mut stmt = self
            .connection
            .prepare("SELECT id FROM players ORDER BY id")?;
        Ok(stmt
            .query_map([], |r| r.get(0))?
            .collect::<Result<_, _>>()?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn migration_revokes_plaintext_tokens_and_hashes_caps_and_expires_new_sessions() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("legacy.db");
        let db = Connection::open(&path).unwrap();
        db.execute_batch(include_str!("../migrations/001_initial.sql"))
            .unwrap();
        db.execute("INSERT INTO players(id,name) VALUES (1,'alice')", [])
            .unwrap();
        db.execute(
            "INSERT INTO sessions(token,player_id) VALUES ('legacy',1)",
            [],
        )
        .unwrap();
        drop(db);
        let store = SqliteStore::open(&path).unwrap();
        assert!(store.session("legacy", 100).unwrap().is_none());
        for token in ["one", "two", "three"] {
            store.save_session(token, 1, 100, 10, 2).unwrap();
        }
        assert!(store.session("one", 100).unwrap().is_none());
        assert!(store.session("two", 109).unwrap().is_some());
        let hashes: Vec<Vec<u8>> = store
            .connection
            .prepare("SELECT token_hash FROM sessions")
            .unwrap()
            .query_map([], |r| r.get(0))
            .unwrap()
            .collect::<Result<_, _>>()
            .unwrap();
        assert_eq!(hashes.len(), 2);
        assert!(hashes.contains(&Sha256::digest(b"three").to_vec()));
        assert!(store.session("two", 110).unwrap().is_none());
        assert_eq!(
            store
                .connection
                .query_row("SELECT count(*) FROM sessions", [], |r| r.get::<_, u32>(0))
                .unwrap(),
            0
        );
        drop(store);
        assert!(SqliteStore::open(path).is_ok());
    }
    #[test]
    fn migrations_atomic_registration_and_city_roundtrip() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("kingdom.db");
        let mut store = SqliteStore::open(&path).unwrap();
        let data = data::GameData::load(data::GameData::repo_data_dir()).unwrap();
        let mut city = City::new_starting(&data, 123);
        let id = store.register("alice", "hash", &city).unwrap();
        assert!(store.register("alice", "other", &city).is_err());
        assert_eq!(store.player_ids().unwrap(), vec![id]);
        city.resources.food = 42;
        store.save_city(id, &city).unwrap();
        store.save_session("token", id, 100, 1000, 5).unwrap();
        assert!(store.save_session("orphan", id + 1, 100, 1000, 5).is_err());
        assert!(store.save_city(id + 1, &city).is_err());
        drop(store);
        let store = SqliteStore::open(path).unwrap();
        assert_eq!(store.city(id).unwrap(), Some(city));
        assert_eq!(
            store.account("alice").unwrap().unwrap().password_hash,
            "hash"
        );
        assert_eq!(
            store.session("token", 100).unwrap(),
            Some((id, "alice".into()))
        );
        assert!(store.session("' OR 1=1 --", 100).unwrap().is_none());
    }
}
