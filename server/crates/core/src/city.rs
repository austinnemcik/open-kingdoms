use data::{GameData, Resources};

/// A building placed in a city.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct Building {
    /// Unique within its city.
    pub id: u32,
    pub kind: String,
    pub level: u32,
    pub x: u32,
    pub y: u32,
}

/// A player's city.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct City {
    pub size: u32,
    pub resources: Resources,
    pub buildings: Vec<Building>,
    next_building_id: u32,
}

impl City {
    /// The starting city defined in `data/start.yaml`.
    pub fn new_starting(data: &GameData) -> Self {
        let start = &data.start;
        let mut city = Self {
            size: start.city_size,
            resources: start.resources,
            buildings: Vec::new(),
            next_building_id: 1,
        };
        for sb in &start.buildings {
            city.push_building(sb.kind.clone(), sb.level, sb.x, sb.y);
        }
        city
    }

    pub fn city_hall_level(&self) -> u32 {
        self.buildings
            .iter()
            .find(|b| b.kind == "city_hall")
            .map_or(0, |b| b.level)
    }

    fn push_building(&mut self, kind: String, level: u32, x: u32, y: u32) -> u32 {
        let id = self.next_building_id;
        self.next_building_id += 1;
        self.buildings.push(Building {
            id,
            kind,
            level,
            x,
            y,
        });
        id
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starting_city_matches_start_yaml() {
        let data = GameData::load(GameData::repo_data_dir()).unwrap();
        let city = City::new_starting(&data);
        assert_eq!(city.buildings.len(), data.start.buildings.len());
        assert_eq!(city.city_hall_level(), 1);
        assert_eq!(city.resources, data.start.resources);
        let mut ids: Vec<_> = city.buildings.iter().map(|b| b.id).collect();
        ids.dedup();
        assert_eq!(ids.len(), city.buildings.len(), "building ids are unique");
    }
}
