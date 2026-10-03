use std::collections::HashMap;
use std::sync::Mutex;

use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier, password_hash::SaltString};
use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
use data::GameData;
use game_core::{City, PlayerId};
use protocol::{BuildingView, CityView, ResourcesView};
use protocol::{ErrorCode, ServerMsg};
use rand::{RngCore, rngs::OsRng};

/// All mutable state of one kingdom. In-memory for now; persistence is a
/// roadmap item (see docs/ROADMAP.md).
pub struct Kingdom {
    pub data: GameData,
    players: Mutex<Players>,
}

#[derive(Default)]
struct Players {
    next_id: PlayerId,
    by_name: HashMap<String, (PlayerId, String)>,
    sessions: HashMap<String, (PlayerId, String)>,
    cities: HashMap<PlayerId, City>,
}

impl Kingdom {
    pub fn new(data: GameData) -> Self {
        Self {
            data,
            players: Mutex::new(Players {
                next_id: 1,
                ..Default::default()
            }),
        }
    }

    /// Verify credentials with Argon2id, registering only previously unused names.
    /// Call on a blocking worker: hashing is intentionally expensive.
    pub fn login(&self, name: &str, password: &str) -> Result<ServerMsg, ErrorCode> {
        if !valid_name(name) || !(8..=128).contains(&password.chars().count()) {
            return Err(ErrorCode::InvalidCredentials);
        }
        let mut players = self.players.lock().map_err(|_| ErrorCode::Internal)?;
        let id = if let Some((id, hash)) = players.by_name.get(name) {
            let hash = PasswordHash::new(hash).map_err(|_| ErrorCode::Internal)?;
            Argon2::default()
                .verify_password(password.as_bytes(), &hash)
                .map_err(|_| ErrorCode::InvalidCredentials)?;
            *id
        } else {
            let salt = SaltString::generate(&mut OsRng);
            let hash = Argon2::default()
                .hash_password(password.as_bytes(), &salt)
                .map_err(|_| ErrorCode::Internal)?
                .to_string();
            let id = players.next_id;
            players.next_id = id.checked_add(1).ok_or(ErrorCode::Internal)?;
            players.by_name.insert(name.to_owned(), (id, hash));
            players.cities.insert(id, City::new_starting(&self.data));
            id
        };
        let mut bytes = [0; 32];
        OsRng
            .try_fill_bytes(&mut bytes)
            .map_err(|_| ErrorCode::Internal)?;
        let token = URL_SAFE_NO_PAD.encode(bytes);
        players
            .sessions
            .insert(token.clone(), (id, name.to_owned()));
        Ok(ServerMsg::LoggedIn {
            player_id: id,
            name: name.to_owned(),
            token,
        })
    }

    /// Resolve an opaque bearer token without accepting a client player id.
    pub fn resume(&self, token: &str) -> Result<ServerMsg, ErrorCode> {
        let players = self.players.lock().map_err(|_| ErrorCode::Internal)?;
        let (id, name) = players
            .sessions
            .get(token)
            .ok_or(ErrorCode::InvalidCredentials)?;
        Ok(ServerMsg::LoggedIn {
            player_id: *id,
            name: name.clone(),
            token: token.to_owned(),
        })
    }

    pub fn city_view(&self, player: PlayerId) -> Option<CityView> {
        let players = self.players.lock().ok()?;
        players.cities.get(&player).map(|c| self.to_view(c))
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
        let k = Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap());
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
        let players = k.players.lock().unwrap();
        assert!(players.by_name["alice"].1.starts_with("$argon2id$"));
        assert!(!players.by_name["alice"].1.contains("password123"));
    }
}
