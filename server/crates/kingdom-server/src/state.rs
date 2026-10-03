use crate::clock::{Clock, RealClock};
use crate::store::{SqliteStore, Store, StoreError};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicU64, Ordering},
};

use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier, password_hash::SaltString};
use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
use data::GameData;
use game_core::{City, PlayerId};
use protocol::{BuildingView, CityView, ResourcesView};
use protocol::{ErrorCode, ServerMsg};
use rand::{RngCore, rngs::OsRng};

/// Authoritative state backed by a serialized persistence connection.
pub struct Kingdom {
    pub data: GameData,
    store: Mutex<Box<dyn Store>>,
    clock: Arc<dyn Clock>,
    last_tick: AtomicU64,
}

impl Kingdom {
    /// Isolated in-memory SQLite kingdom for tests and embedding.
    pub fn new(data: GameData) -> Result<Self, StoreError> {
        Ok(Self::with_store(
            data,
            Box::new(SqliteStore::open(":memory:")?),
        ))
    }

    /// Inject an already migrated store. Storage methods run on blocking workers.
    pub fn with_store(data: GameData, store: Box<dyn Store>) -> Self {
        Self::with_clock(data, store, Arc::new(RealClock))
    }

    /// Inject storage and time independently for deterministic server tests.
    pub fn with_clock(data: GameData, store: Box<dyn Store>, clock: Arc<dyn Clock>) -> Self {
        Self {
            data,
            store: Mutex::new(store),
            clock,
            last_tick: AtomicU64::new(0),
        }
    }

    /// Current game time in Unix seconds.
    pub fn now(&self) -> u64 {
        self.clock.now()
    }

    /// Execute one server tick. Timer processing is added here as rules land.
    pub fn tick(&self) {
        self.last_tick.store(self.now(), Ordering::SeqCst);
    }

    /// Timestamp of the most recent completed server tick, for health/tests.
    pub fn last_tick(&self) -> u64 {
        self.last_tick.load(Ordering::SeqCst)
    }

    /// Verify credentials with Argon2id, registering only previously unused names.
    /// Call on a blocking worker: hashing is intentionally expensive.
    pub fn login(&self, name: &str, password: &str) -> Result<ServerMsg, ErrorCode> {
        if !valid_name(name) || !(8..=128).contains(&password.chars().count()) {
            return Err(ErrorCode::InvalidCredentials);
        }
        let mut store = self.store.lock().map_err(|_| ErrorCode::Internal)?;
        let id = if let Some(account) = store.account(name).map_err(|_| ErrorCode::Internal)? {
            let hash =
                PasswordHash::new(&account.password_hash).map_err(|_| ErrorCode::Internal)?;
            Argon2::default()
                .verify_password(password.as_bytes(), &hash)
                .map_err(|_| ErrorCode::InvalidCredentials)?;
            account.id
        } else {
            let salt = SaltString::generate(&mut OsRng);
            let hash = Argon2::default()
                .hash_password(password.as_bytes(), &salt)
                .map_err(|_| ErrorCode::Internal)?
                .to_string();
            store
                .register(name, &hash, &City::new_starting(&self.data, self.now()))
                .map_err(|_| ErrorCode::Internal)?
        };
        let mut bytes = [0; 32];
        OsRng
            .try_fill_bytes(&mut bytes)
            .map_err(|_| ErrorCode::Internal)?;
        let token = URL_SAFE_NO_PAD.encode(bytes);
        store
            .save_session(&token, id)
            .map_err(|_| ErrorCode::Internal)?;
        Ok(ServerMsg::LoggedIn {
            player_id: id,
            name: name.to_owned(),
            token,
        })
    }

    /// Resolve an opaque bearer token without accepting a client player id.
    pub fn resume(&self, token: &str) -> Result<ServerMsg, ErrorCode> {
        let store = self.store.lock().map_err(|_| ErrorCode::Internal)?;
        let (id, name) = store
            .session(token)
            .map_err(|_| ErrorCode::Internal)?
            .ok_or(ErrorCode::InvalidCredentials)?;
        Ok(ServerMsg::LoggedIn {
            player_id: id,
            name,
            token: token.to_owned(),
        })
    }

    /// Fetch the authoritative persisted city snapshot.
    pub fn city_view(&self, player: PlayerId) -> Option<CityView> {
        let store = self.store.lock().ok()?;
        store.city(player).ok()?.map(|c| self.to_view(&c))
    }

    fn to_view(&self, city: &City) -> CityView {
        let r = city.resources;
        CityView {
            size: city.size,
            resources: ResourcesView {
                food: r.food,
                wood: r.wood,
                stone: r.stone,
                gold: r.gold,
            },
            buildings: city
                .buildings
                .iter()
                .map(|b| {
                    let def = self
                        .data
                        .building(&b.kind)
                        .expect("cities only contain validated building kinds");
                    BuildingView {
                        id: b.id,
                        kind: b.kind.clone(),
                        name: def.name.clone(),
                        level: b.level,
                        x: b.x,
                        y: b.y,
                        footprint: def.footprint,
                    }
                })
                .collect(),
        }
    }
}

/// Player names: 3-16 chars of ASCII letters, digits or underscore.
pub fn valid_name(name: &str) -> bool {
    (3..=16).contains(&name.len()) && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn name_rules() {
        assert!(valid_name("alice_01"));
        assert!(!valid_name("al"));
        assert!(!valid_name("bad name"));
        assert!(!valid_name("seventeen_chars__"));
    }

    #[test]
    fn password_boundaries_and_tokens() {
        let k = Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap()).unwrap();
        for password in ["short".to_owned(), "x".repeat(129)] {
            assert_eq!(
                k.login("alice", &password),
                Err(ErrorCode::InvalidCredentials)
            );
        }
        let ServerMsg::LoggedIn {
            player_id, token, ..
        } = k.login("alice", "password123").unwrap()
        else {
            panic!()
        };
        assert_eq!(URL_SAFE_NO_PAD.decode(&token).unwrap().len(), 32);
        assert!(
            matches!(k.resume(&token), Ok(ServerMsg::LoggedIn { player_id: p, .. }) if p == player_id)
        );
        assert_eq!(
            k.login("alice", "wrongpass"),
            Err(ErrorCode::InvalidCredentials)
        );
        assert_eq!(k.resume("forged"), Err(ErrorCode::InvalidCredentials));
        let ServerMsg::LoggedIn { token: next, .. } = k.login("alice", "password123").unwrap()
        else {
            panic!()
        };
        assert_ne!(token, next);
        for (name, password) in [("eight", "x".repeat(8)), ("maximum", "?".repeat(128))] {
            assert!(k.login(name, &password).is_ok());
        }
        let store = k.store.lock().unwrap();
        let hash = store.account("alice").unwrap().unwrap().password_hash;
        assert!(hash.starts_with("$argon2id$"));
        assert!(!hash.contains("password123"));
    }
}
