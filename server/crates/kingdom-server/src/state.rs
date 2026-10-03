use std::collections::HashMap;
use std::sync::Mutex;

use data::GameData;
use game_core::{City, PlayerId};
use protocol::{BuildingView, CityView, ResourcesView};

/// All mutable state of one kingdom. In-memory for now; persistence is a
/// roadmap item (see docs/ROADMAP.md).
pub struct Kingdom {
    pub data: GameData,
    players: Mutex<Players>,
}

#[derive(Default)]
struct Players {
    next_id: PlayerId,
    by_name: HashMap<String, PlayerId>,
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

    /// Return the player with this name, creating them (and their starting
    /// city) if they don't exist yet.
    pub fn login_or_register(&self, name: &str) -> PlayerId {
        let mut players = self.players.lock().unwrap();
        if let Some(&id) = players.by_name.get(name) {
            return id;
        }
        let id = players.next_id;
        players.next_id += 1;
        players.by_name.insert(name.to_owned(), id);
        players.cities.insert(id, City::new_starting(&self.data));
        tracing::info!(player_id = id, name, "registered new player");
        id
    }

    pub fn city_view(&self, player: PlayerId) -> Option<CityView> {
        let players = self.players.lock().unwrap();
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
    fn same_name_logs_into_same_player() {
        let k = Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap());
        let a = k.login_or_register("alice");
        let b = k.login_or_register("bob");
        assert_ne!(a, b);
        assert_eq!(k.login_or_register("alice"), a);
        assert!(k.city_view(a).is_some());
    }
}
