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
    /// Last resource accounting time in Unix seconds; None denotes a legacy city.
    #[serde(default)]
    pub as_of: Option<u64>,
    pub resources: Resources,
    /// Fractional resource numerators (denominator 3600), persisted across access.
    #[serde(default)]
    production_remainder: [u64; 4],
    pub buildings: Vec<Building>,
    next_building_id: u32,
}

impl City {
    /// The starting city defined in `data/start.yaml`.
    pub fn new_starting(data: &GameData, now: u64) -> Self {
        let start = &data.start;
        let mut city = Self {
            size: start.city_size,
            as_of: Some(now),
            resources: start.resources,
            production_remainder: [0; 4],
            buildings: Vec::new(),
            next_building_id: 1,
        };
        for sb in &start.buildings {
            city.push_building(sb.kind.clone(), sb.level, sb.x, sb.y);
        }
        city
    }

    /// Aggregate per-hour output of completed building levels.
    pub fn rates_per_hour(&self, data: &GameData) -> Resources {
        self.buildings
            .iter()
            .filter_map(|b| {
                data.building(&b.kind)
                    .map(|d| d.production_for_level(b.level))
            })
            .fold(Resources::default(), Resources::saturating_add)
    }

    /// Aggregate resource storage from completed buildings.
    pub fn capacity(&self, data: &GameData) -> Resources {
        self.buildings
            .iter()
            .filter_map(|b| {
                data.building(&b.kind)
                    .map(|d| d.capacity_for_level(b.level))
            })
            .fold(Resources::default(), Resources::saturating_add)
    }

    /// Lazily accrue production up to `now` (Unix seconds), retaining fractions.
    /// Backwards clocks cannot repeat income. A legacy city starts accounting now.
    pub fn collect(&mut self, now: u64, data: &GameData) {
        let previous = self.as_of.unwrap_or(now);
        let elapsed = now.saturating_sub(previous);
        self.as_of = Some(previous.max(now));
        let rate = self.rates_per_hour(data).values();
        let capacity = self.capacity(data).values();
        let mut stored = self.resources.values();
        for i in 0..4 {
            let total = u128::from(rate[i]) * u128::from(elapsed)
                + u128::from(self.production_remainder[i]);
            let room = capacity[i].saturating_sub(stored[i]);
            let gained = (total / 3600).min(u128::from(room)) as u64;
            stored[i] = stored[i].saturating_add(gained);
            self.production_remainder[i] = if stored[i] >= capacity[i] {
                0
            } else {
                (total % 3600) as u64
            };
        }
        self.resources = Resources::from_values(stored);
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
        let city = City::new_starting(&data, 123);
        assert_eq!(city.buildings.len(), data.start.buildings.len());
        assert_eq!(city.city_hall_level(), 1);
        assert_eq!(city.as_of, Some(123));
        assert_eq!(city.resources, data.start.resources);
        let mut ids: Vec<_> = city.buildings.iter().map(|b| b.id).collect();
        ids.dedup();
        assert_eq!(ids.len(), city.buildings.len(), "building ids are unique");
    }
    fn fixture() -> (GameData, City) {
        let data = GameData::load(GameData::repo_data_dir()).unwrap();
        let city = City::new_starting(&data, 100);
        (data, city)
    }
    #[test]
    fn production_is_independent_of_collection_frequency() {
        let (data, mut once) = fixture();
        let mut frequent = once.clone();
        once.collect(3700, &data);
        for now in 101..=3700 {
            frequent.collect(now, &data);
        }
        assert_eq!(once, frequent);
        assert_eq!(once.resources.food, 1600);
        assert_eq!(once.resources.wood, 1600);
        assert_eq!(once.resources.stone, 0);
    }
    #[test]
    fn production_caps_and_huge_elapsed_times_are_safe() {
        let (data, mut city) = fixture();
        city.collect(u64::MAX, &data);
        assert_eq!(city.resources.food, city.capacity(&data).food);
        let snapshot = city.clone();
        city.collect(u64::MAX, &data);
        assert_eq!(city, snapshot);
        city.resources.food += 1;
        let stored = city.resources.food;
        city.collect(u64::MAX, &data);
        assert_eq!(
            city.resources.food, stored,
            "do not destroy over-cap rewards"
        );
    }
    #[test]
    fn backwards_time_and_legacy_cities_do_not_create_income() {
        let (data, mut city) = fixture();
        city.collect(160, &data);
        let snapshot = city.clone();
        city.collect(110, &data);
        city.collect(160, &data);
        assert_eq!(city, snapshot);
        city.as_of = None;
        city.collect(1_000_000, &data);
        assert_eq!(city.resources, snapshot.resources);
        assert_eq!(city.as_of, Some(1_000_000));
    }
    #[test]
    fn completed_levels_and_multiple_producers_sum() {
        let (data, mut city) = fixture();
        city.push_building("farm".into(), 2, 0, 0);
        city.push_building("farm".into(), 0, 2, 0);
        city.push_building("storehouse".into(), 1, 4, 0);
        assert_eq!(city.rates_per_hour(&data).food, 1500);
        assert_eq!(city.capacity(&data).food, 8250);
        city.resources = Resources::default();
        city.collect(3700, &data);
        assert_eq!(city.resources.food, 1500);
    }
}
