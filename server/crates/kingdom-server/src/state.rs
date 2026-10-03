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
use protocol::{BuildingState, BuildingView, CityView, ResourcesView};
use protocol::{ErrorCode, ServerMsg};
use rand::{RngCore, rngs::OsRng};
use tokio::sync::broadcast;

/// Authoritative state backed by a serialized persistence connection.
pub struct Kingdom {
    pub data: GameData,
    pub(crate) security: crate::security::Security,
    store: Mutex<Box<dyn Store>>,
    // Preserve publication order while constructing snapshots outside the store lock.
    city_updates: Mutex<()>,
    clock: Arc<dyn Clock>,
    last_tick: AtomicU64,
    updates: broadcast::Sender<(PlayerId, CityView)>,
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
            security: crate::security::Security::new(&data.limits),
            data,
            store: Mutex::new(store),
            city_updates: Mutex::new(()),
            clock,
            last_tick: AtomicU64::new(0),
            updates: broadcast::channel(64).0,
        }
    }

    /// Current game time in Unix seconds.
    pub fn now(&self) -> u64 {
        self.clock.now()
    }

    /// Subscribe to persisted city changes; sessions filter by authenticated owner.
    pub fn subscribe(&self) -> broadcast::Receiver<(PlayerId, CityView)> {
        self.updates.subscribe()
    }

    /// Complete due jobs and persist them before notifying connected owners.
    pub fn tick(&self) -> Result<(), ErrorCode> {
        let _publication = self.city_updates.lock().unwrap_or_else(|e| e.into_inner());
        let now = self.now();
        let store = self.store.lock().unwrap_or_else(|e| e.into_inner());
        let mut changed = Vec::new();
        for player in store.player_ids().map_err(|_| ErrorCode::Internal)? {
            let Some(mut city) = store.city(player).map_err(|_| ErrorCode::Internal)? else {
                continue;
            };
            if city
                .buildings
                .iter()
                .any(|b| b.upgrade.as_ref().is_some_and(|u| u.completes_at <= now))
            {
                city.collect(now, &self.data);
                store
                    .save_city(player, &city)
                    .map_err(|_| ErrorCode::Internal)?;
                changed.push((player, city));
            }
        }
        drop(store);
        for (player, city) in changed {
            let _ = self.updates.send((player, self.to_view(&city)));
        }
        self.last_tick.store(now, Ordering::SeqCst);
        Ok(())
    }

    /// Apply a pure rule while holding the storage lock; publish only after commit.
    pub fn change_city(
        &self,
        player: PlayerId,
        action: impl FnOnce(&mut City, u64, &GameData) -> Result<(), game_core::CityError>,
    ) -> Result<(), (ErrorCode, String)> {
        let _publication = self.city_updates.lock().unwrap_or_else(|e| e.into_inner());
        let internal = || (ErrorCode::Internal, "city unavailable".to_owned());
        let store = self.store.lock().unwrap_or_else(|e| e.into_inner());
        let mut city = store
            .city(player)
            .map_err(|_| internal())?
            .ok_or_else(internal)?;
        let now = self.now();
        let completed = city.collect(now, &self.data);
        let result = action(&mut city, now, &self.data);
        store.save_city(player, &city).map_err(|_| internal())?;
        drop(store);
        if result.is_ok() || completed {
            let _ = self.updates.send((player, self.to_view(&city)));
        }
        result.map_err(|e| (ErrorCode::InvalidAction, e.to_string()))
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
        let account = self
            .store
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .account(name)
            .map_err(|_| ErrorCode::Internal)?;
        // Reject overload rather than accumulating unbounded blocking-pool jobs.
        let _permit = self
            .security
            .hashes
            .try_acquire()
            .map_err(|_| ErrorCode::RateLimited)?;
        let id = if let Some(account) = account {
            verify_password(password, &account.password_hash)?;
            account.id
        } else {
            let salt = SaltString::generate(&mut OsRng);
            let hash = Argon2::default()
                .hash_password(password.as_bytes(), &salt)
                .map_err(|_| ErrorCode::Internal)?
                .to_string();
            let mut store = self.store.lock().unwrap_or_else(|e| e.into_inner());
            // Another registration may have won while this password was hashing.
            if let Some(winner) = store.account(name).map_err(|_| ErrorCode::Internal)? {
                drop(store);
                verify_password(password, &winner.password_hash)?;
                winner.id
            } else {
                store
                    .register(name, &hash, &City::new_starting(&self.data, self.now()))
                    .map_err(|_| ErrorCode::Internal)?
            }
        };
        let mut bytes = [0; 32];
        OsRng
            .try_fill_bytes(&mut bytes)
            .map_err(|_| ErrorCode::Internal)?;
        let token = URL_SAFE_NO_PAD.encode(bytes);
        self.store
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .save_session(
                &token,
                id,
                self.now(),
                self.data.limits.session_ttl_s,
                self.data.limits.sessions_per_player,
            )
            .map_err(|_| ErrorCode::Internal)?;
        Ok(ServerMsg::LoggedIn {
            player_id: id,
            name: name.to_owned(),
            token,
        })
    }

    /// Apply shared IP/account and registration budgets before expensive hashing.
    pub(crate) fn login_from(
        &self,
        ip: std::net::IpAddr,
        name: &str,
        password: &str,
    ) -> Result<ServerMsg, ErrorCode> {
        if !valid_name(name) || !(8..=128).contains(&password.chars().count()) {
            return Err(ErrorCode::InvalidCredentials);
        }
        let limits = &self.data.limits;
        if !self
            .security
            .attempt(format!("ip:{ip}"), limits.logins_per_ip, limits)
            || !self
                .security
                .attempt(format!("account:{name}"), limits.logins_per_account, limits)
        {
            return Err(ErrorCode::RateLimited);
        }
        let is_new = self
            .store
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .account(name)
            .map_err(|_| ErrorCode::Internal)?
            .is_none();
        if is_new
            && !self.security.attempt(
                format!("register:{ip}"),
                limits.registrations_per_ip,
                limits,
            )
        {
            return Err(ErrorCode::RateLimited);
        }
        self.login(name, password)
    }

    /// Resolve an opaque bearer token without accepting a client player id.
    pub fn resume(&self, token: &str) -> Result<ServerMsg, ErrorCode> {
        let store = self.store.lock().unwrap_or_else(|e| e.into_inner());
        let (id, name) = store
            .session(token, self.now())
            .map_err(|_| ErrorCode::Internal)?
            .ok_or(ErrorCode::InvalidCredentials)?;
        Ok(ServerMsg::LoggedIn {
            player_id: id,
            name,
            token: token.to_owned(),
        })
    }

    /// Fetch the authoritative persisted city snapshot.
    pub fn city_view(&self, player: PlayerId) -> Result<CityView, ErrorCode> {
        let _publication = self.city_updates.lock().unwrap_or_else(|e| e.into_inner());
        let store = self.store.lock().unwrap_or_else(|e| e.into_inner());
        let mut city = store
            .city(player)
            .map_err(|_| ErrorCode::Internal)?
            .ok_or(ErrorCode::NotLoggedIn)?;
        let completed = city.collect(self.now(), &self.data);
        store
            .save_city(player, &city)
            .map_err(|_| ErrorCode::Internal)?;
        drop(store);
        let view = self.to_view(&city);
        if completed {
            let _ = self.updates.send((player, view.clone()));
        }
        Ok(view)
    }

    fn to_view(&self, city: &City) -> CityView {
        let r = city.resources;
        CityView {
            size: city.size,
            builder_slots: self.data.construction.builder_slots,
            as_of: city.as_of.unwrap_or_else(|| self.now()),
            rates_per_hour: resource_view(city.rates_per_hour(&self.data)),
            capacity: resource_view(city.capacity(&self.data)),
            resources: ResourcesView {
                food: r.food,
                wood: r.wood,
                stone: r.stone,
                gold: r.gold,
            },
            buildings: city
                .buildings
                .iter()
                .filter_map(|b| {
                    let Some(def) = self.data.building(&b.kind) else {
                        tracing::warn!(kind = %b.kind, "skipping unknown persisted building kind");
                        return None;
                    };
                    Some(BuildingView {
                        id: b.id,
                        kind: b.kind.clone(),
                        name: def.name.clone(),
                        level: b.level,
                        x: b.x,
                        y: b.y,
                        footprint: def.footprint,
                        state: if b.level == 0 {
                            BuildingState::UnderConstruction
                        } else if b.upgrade.is_some() {
                            BuildingState::Upgrading
                        } else {
                            BuildingState::Ready
                        },
                        started_at: b.upgrade.as_ref().map(|u| u.started_at),
                        completes_at: b.upgrade.as_ref().map(|u| u.completes_at),
                    })
                })
                .collect(),
        }
    }
}

fn verify_password(password: &str, encoded: &str) -> Result<(), ErrorCode> {
    let hash = PasswordHash::new(encoded).map_err(|_| ErrorCode::Internal)?;
    Argon2::default()
        .verify_password(password.as_bytes(), &hash)
        .map_err(|e| {
            if matches!(e, argon2::password_hash::Error::Password) {
                ErrorCode::InvalidCredentials
            } else {
                ErrorCode::Internal
            }
        })
}

/// Player names: 3-16 chars of ASCII letters, digits or underscore.
pub fn valid_name(name: &str) -> bool {
    (3..=16).contains(&name.len()) && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

fn resource_view(r: data::Resources) -> ResourcesView {
    ResourcesView {
        food: r.food,
        wood: r.wood,
        stone: r.stone,
        gold: r.gold,
    }
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

#[cfg(test)]
mod hardening_tests {
    use super::*;
    #[test]
    fn unknown_kind_and_poisoned_lock_do_not_disable_the_kingdom() {
        let data = GameData::load(GameData::repo_data_dir()).unwrap();
        let mut city = City::new_starting(&data, 100);
        city.buildings[1].kind = "removed_kind".into();
        let mut store = SqliteStore::open(":memory:").unwrap();
        let id = store.register("alice", "unused", &city).unwrap();
        let k = Kingdom::with_store(data, Box::new(store));
        let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _guard = k.store.lock().unwrap();
            panic!("simulate a failed worker");
        }));
        let view = k.city_view(id).unwrap();
        assert_eq!(view.buildings.len(), city.buildings.len() - 1);
        assert!(k.tick().is_ok());
        assert!(k.login("another", "password123").is_ok());
    }
    #[test]
    fn hashing_does_not_hold_store_lock_and_registration_race_verifies_winner() {
        let k = Arc::new(Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap()).unwrap());
        let worker = k.clone();
        let t = std::thread::spawn(move || worker.login("racer", "password123"));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(5);
        while k.security.hashes.available_permits() == k.data.limits.concurrent_hashes as usize {
            assert!(std::time::Instant::now() < deadline);
            std::thread::yield_now();
        }
        // Hash admission happens after the read and before registration's write.
        assert!(k.store.try_lock().is_ok());
        let other = k.login("racer", "different_password");
        let first = t.join().unwrap();
        assert!(matches!(
            (&first, &other),
            (Ok(_), Err(ErrorCode::InvalidCredentials))
                | (Err(ErrorCode::InvalidCredentials), Ok(_))
        ));
        assert_eq!(k.store.lock().unwrap().player_ids().unwrap().len(), 1);
    }
    #[test]
    fn concurrent_city_reads_never_repeat_production() {
        let data = GameData::load(GameData::repo_data_dir()).unwrap();
        let clock = Arc::new(crate::clock::ManualClock::new(100));
        let k = Arc::new(Kingdom::with_clock(
            data,
            Box::new(SqliteStore::open(":memory:").unwrap()),
            clock.clone(),
        ));
        let ServerMsg::LoggedIn { player_id, .. } = k.login("alice", "password123").unwrap() else {
            panic!()
        };
        clock.set(3700);
        let threads: Vec<_> = (0..8)
            .map(|_| {
                let k = k.clone();
                std::thread::spawn(move || k.city_view(player_id).unwrap())
            })
            .collect();
        let views: Vec<_> = threads.into_iter().map(|t| t.join().unwrap()).collect();
        assert!(views.iter().all(|v| v == &views[0]));
        assert_eq!(views[0].resources.food, 1600);
    }
}
