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
    /// In-progress job, including the paid cost for deterministic refunds.
    #[serde(default)]
    pub upgrade: Option<Upgrade>,
}

/// Persisted construction/upgrade reservation; timestamps are Unix seconds.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct Upgrade {
    pub started_at: u64,
    pub completes_at: u64,
    pub paid: Resources,
}

/// Rejected city requests never partially spend resources or reserve a builder.
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum CityError {
    #[error("unknown building")]
    UnknownBuilding,
    #[error("building is already at its maximum level")]
    MaxLevel,
    #[error("upgrade City Hall first")]
    CityHallRequired,
    #[error("upgrade prerequisites are not met")]
    Prerequisite,
    #[error("building already has a job")]
    Busy,
    #[error("all builders are busy")]
    BuildersBusy,
    #[error("insufficient resources")]
    InsufficientResources,
    #[error("timer exceeds the supported time range")]
    TimeOverflow,
    #[error("building has no cancellable job")]
    NothingToCancel,
    #[error("building footprint lies outside the city")]
    OutOfBounds,
    #[error("building footprint overlaps another building")]
    Overlap,
    #[error("maximum count for this building kind reached")]
    CountLimit,
    #[error("building requires a higher City Hall level")]
    Locked,
    #[error("building id space exhausted")]
    IdExhausted,
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
    pub fn collect(&mut self, now: u64, data: &GameData) -> bool {
        let target = now.max(self.as_of.unwrap_or(now));
        let mut completed = false;
        while let Some(deadline) = self
            .buildings
            .iter()
            .filter_map(|b| b.upgrade.as_ref().map(|u| u.completes_at))
            .filter(|t| *t <= target)
            .min()
        {
            self.accrue(deadline, data);
            for building in &mut self.buildings {
                if building
                    .upgrade
                    .as_ref()
                    .is_some_and(|u| u.completes_at <= deadline)
                {
                    building.level = building.level.saturating_add(1);
                    building.upgrade = None;
                    completed = true;
                }
            }
        }
        self.accrue(target, data);
        completed
    }

    fn accrue(&mut self, now: u64, data: &GameData) {
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

    /// Reserve a legal footprint, pay construction cost, and queue level one.
    /// Pending buildings occupy tiles and count toward their kind's maximum.
    pub fn build_building(
        &mut self,
        kind: &str,
        x: u32,
        y: u32,
        now: u64,
        data: &GameData,
    ) -> Result<u32, CityError> {
        self.collect(now, data);
        let now = self.as_of.unwrap_or(now);
        let def = data.building(kind).ok_or(CityError::UnknownBuilding)?;
        if self.city_hall_level() < def.requires_city_hall {
            return Err(CityError::Locked);
        }
        if self.buildings.iter().filter(|b| b.kind == kind).count() >= def.max_count as usize {
            return Err(CityError::CountLimit);
        }
        let right = x
            .checked_add(def.footprint)
            .filter(|n| *n <= self.size)
            .ok_or(CityError::OutOfBounds)?;
        let bottom = y
            .checked_add(def.footprint)
            .filter(|n| *n <= self.size)
            .ok_or(CityError::OutOfBounds)?;
        for building in &self.buildings {
            let other = data
                .building(&building.kind)
                .ok_or(CityError::UnknownBuilding)?;
            if x < building.x.saturating_add(other.footprint)
                && right > building.x
                && y < building.y.saturating_add(other.footprint)
                && bottom > building.y
            {
                return Err(CityError::Overlap);
            }
        }
        let next_id = self
            .next_building_id
            .checked_add(1)
            .ok_or(CityError::IdExhausted)?;
        let (remaining, upgrade) = self.prepare_job(def, 1, now, data)?;
        let id = self.next_building_id;
        self.resources = remaining;
        self.next_building_id = next_id;
        self.buildings.push(Building {
            id,
            kind: kind.to_owned(),
            level: 0,
            x,
            y,
            upgrade: Some(upgrade),
        });
        Ok(id)
    }

    /// Reserve a free builder and atomically pay the next-level cost.
    pub fn upgrade_building(
        &mut self,
        building_id: u32,
        now: u64,
        data: &GameData,
    ) -> Result<(), CityError> {
        self.collect(now, data);
        let now = self.as_of.unwrap_or(now);
        let index = self
            .buildings
            .iter()
            .position(|b| b.id == building_id)
            .ok_or(CityError::UnknownBuilding)?;
        let building = &self.buildings[index];
        let def = data
            .building(&building.kind)
            .ok_or(CityError::UnknownBuilding)?;
        if building.upgrade.is_some() {
            return Err(CityError::Busy);
        }
        if building.level >= def.max_level {
            return Err(CityError::MaxLevel);
        }
        let target = building.level + 1;
        if building.kind != "city_hall" && target > self.city_hall_level() {
            return Err(CityError::CityHallRequired);
        }
        for requirement in &def.upgrade_requirements {
            let level = target.saturating_sub(requirement.levels_below_target);
            if level > 0
                && !self
                    .buildings
                    .iter()
                    .any(|b| b.kind == requirement.kind && b.level >= level)
            {
                return Err(CityError::Prerequisite);
            }
        }
        let (remaining, upgrade) = self.prepare_job(def, target, now, data)?;
        self.resources = remaining;
        self.buildings[index].upgrade = Some(upgrade);
        Ok(())
    }

    fn prepare_job(
        &self,
        def: &data::BuildingDef,
        target: u32,
        now: u64,
        data: &GameData,
    ) -> Result<(Resources, Upgrade), CityError> {
        if self
            .buildings
            .iter()
            .filter(|b| b.upgrade.is_some())
            .count()
            >= data.construction.builder_slots as usize
        {
            return Err(CityError::BuildersBusy);
        }
        let cost = def.cost_for_level(target);
        let owned = self.resources.values();
        let price = cost.values();
        if owned.iter().zip(price).any(|(a, b)| *a < b) {
            return Err(CityError::InsufficientResources);
        }
        let completes_at = now
            .checked_add(def.time_for_level(target))
            .ok_or(CityError::TimeOverflow)?;
        Ok((
            Resources::from_values(std::array::from_fn(|i| owned[i] - price[i])),
            Upgrade {
                started_at: now,
                completes_at,
                paid: cost,
            },
        ))
    }

    /// Cancel an unfinished job, refunding the YAML-configured share of paid cost.
    pub fn cancel_upgrade(
        &mut self,
        building_id: u32,
        now: u64,
        data: &GameData,
    ) -> Result<(), CityError> {
        self.collect(now, data);
        let building = self
            .buildings
            .iter_mut()
            .find(|b| b.id == building_id)
            .ok_or(CityError::UnknownBuilding)?;
        let upgrade = building.upgrade.take().ok_or(CityError::NothingToCancel)?;
        let paid = upgrade.paid.values();
        let refund = Resources::from_values(std::array::from_fn(|i| {
            (u128::from(paid[i]) * u128::from(data.construction.cancellation_refund_percent) / 100)
                as u64
        }));
        self.resources = self.resources.saturating_add(refund);
        if building.level == 0 {
            self.buildings.retain(|b| b.id != building_id);
        }
        Ok(())
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
            upgrade: None,
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
    #[test]
    fn upgrades_validate_identity_max_level_hall_and_prerequisites() {
        let (data, mut city) = fixture();
        assert_eq!(
            city.upgrade_building(999, 100, &data),
            Err(CityError::UnknownBuilding)
        );
        assert_eq!(
            city.upgrade_building(2, 100, &data),
            Err(CityError::CityHallRequired)
        );
        city.buildings[0].level = 2;
        assert_eq!(
            city.upgrade_building(1, 100, &data),
            Err(CityError::Prerequisite)
        );
        city.buildings[1].level = 25;
        assert_eq!(
            city.upgrade_building(2, 100, &data),
            Err(CityError::MaxLevel)
        );
        city.buildings[0].level = 25;
        assert_eq!(
            city.upgrade_building(1, 100, &data),
            Err(CityError::MaxLevel)
        );
    }
    #[test]
    fn failed_cost_and_timer_validation_do_not_partially_mutate() {
        let (data, mut city) = fixture();
        city.resources = Resources::default();
        let before = city.clone();
        assert_eq!(
            city.upgrade_building(1, 100, &data),
            Err(CityError::InsufficientResources)
        );
        assert_eq!(city, before);
        city.collect(u64::MAX, &data);
        let before = city.clone();
        assert_eq!(
            city.upgrade_building(1, u64::MAX, &data),
            Err(CityError::TimeOverflow)
        );
        assert_eq!(city, before);
    }
    #[test]
    fn two_builders_and_duplicate_job_checks_are_atomic() {
        let (data, mut city) = fixture();
        city.buildings[0].level = 2;
        city.upgrade_building(2, 100, &data).unwrap();
        city.upgrade_building(3, 100, &data).unwrap();
        let before = city.clone();
        assert_eq!(city.upgrade_building(2, 100, &data), Err(CityError::Busy));
        assert_eq!(
            city.upgrade_building(4, 100, &data),
            Err(CityError::BuildersBusy)
        );
        assert_eq!(city, before);
        city.cancel_upgrade(2, 100, &data).unwrap();
        assert_eq!(city.resources.wood, data.start.resources.wood);
        city.upgrade_building(4, 100, &data).unwrap();
    }
    #[test]
    fn exact_completion_deadline_and_cancellation_refund() {
        let (data, mut city) = fixture();
        let before = city.resources;
        city.upgrade_building(1, 100, &data).unwrap();
        assert_eq!(city.resources.food, before.food - 300);
        assert_eq!(
            city.buildings[0].upgrade.as_ref().unwrap().completes_at,
            220
        );
        assert!(!city.collect(219, &data));
        assert_eq!(city.city_hall_level(), 1);
        assert!(city.collect(220, &data));
        assert_eq!(city.city_hall_level(), 2);
        assert!(!city.collect(221, &data));
        assert_eq!(
            city.cancel_upgrade(1, 220, &data),
            Err(CityError::NothingToCancel)
        );
        assert_eq!(
            city.cancel_upgrade(999, 220, &data),
            Err(CityError::UnknownBuilding)
        );
        let (_, mut cancelled) = fixture();
        cancelled.upgrade_building(1, 100, &data).unwrap();
        cancelled.cancel_upgrade(1, 100, &data).unwrap();
        assert_eq!(cancelled.resources, before);
        assert!(cancelled.buildings[0].upgrade.is_none());
        assert_eq!(
            cancelled.cancel_upgrade(1, 100, &data),
            Err(CityError::NothingToCancel)
        );
    }
    #[test]
    fn refunds_preserve_recorded_cost_even_over_capacity() {
        let (data, mut city) = fixture();
        city.upgrade_building(1, 100, &data).unwrap();
        city.resources = city.capacity(&data);
        let before = city.resources;
        city.cancel_upgrade(1, 100, &data).unwrap();
        assert_eq!(city.resources.food, before.food + 300);
        city.collect(200, &data);
        assert_eq!(city.resources.food, before.food + 300);
    }
    #[test]
    fn offline_completion_splits_income_at_job_boundaries() {
        let (data, mut once) = fixture();
        once.buildings[0].level = 2;
        once.upgrade_building(2, 100, &data).unwrap();
        once.upgrade_building(3, 100, &data).unwrap();
        let mut frequent = once.clone();
        assert!(once.collect(220, &data));
        for now in 101..=220 {
            frequent.collect(now, &data);
        }
        assert_eq!(once, frequent);
        assert_eq!(once.resources.food, 945);
        assert_eq!(once.resources.wood, 945);
        assert_eq!(once.rates_per_hour(&data).food, 900);
        assert!(once.buildings.iter().all(|b| b.upgrade.is_none()));
    }
    #[test]
    fn backwards_clock_cannot_backdate_an_upgrade() {
        let (data, mut city) = fixture();
        city.collect(200, &data);
        city.upgrade_building(1, 150, &data).unwrap();
        assert_eq!(city.buildings[0].upgrade.as_ref().unwrap().started_at, 200);
        assert_eq!(
            city.buildings[0].upgrade.as_ref().unwrap().completes_at,
            320
        );
    }
    #[test]
    fn new_buildings_reserve_tiles_and_produce_only_after_completion() {
        let (data, mut city) = fixture();
        let initial_rate = city.rates_per_hour(&data);
        let id = city.build_building("farm", 0, 0, 100, &data).unwrap();
        assert_eq!(city.resources.wood, 950);
        let building = city.buildings.iter().find(|b| b.id == id).unwrap();
        assert_eq!(building.level, 0);
        assert_eq!(building.upgrade.as_ref().unwrap().completes_at, 145);
        assert_eq!(city.rates_per_hour(&data), initial_rate);
        assert_eq!(
            city.build_building("lumber_mill", 1, 1, 100, &data),
            Err(CityError::Overlap)
        );
        assert_eq!(city.upgrade_building(id, 100, &data), Err(CityError::Busy));
        city.collect(144, &data);
        assert_eq!(city.buildings.iter().find(|b| b.id == id).unwrap().level, 0);
        city.collect(160, &data);
        assert_eq!(city.buildings.iter().find(|b| b.id == id).unwrap().level, 1);
        assert_eq!(city.resources.food, 1012);
        assert_eq!(city.rates_per_hour(&data).food, 1200);
    }
    #[test]
    fn construction_validates_kind_unlock_bounds_overlap_and_count() {
        let (data, mut city) = fixture();
        let before = city.clone();
        assert_eq!(
            city.build_building("unknown", 0, 0, 100, &data),
            Err(CityError::UnknownBuilding)
        );
        assert_eq!(
            city.build_building("quarry", 0, 0, 100, &data),
            Err(CityError::Locked)
        );
        assert_eq!(
            city.build_building("city_hall", 0, 0, 100, &data),
            Err(CityError::CountLimit)
        );
        for (x, y) in [(39, 0), (0, 39), (u32::MAX, 0), (0, u32::MAX)] {
            assert_eq!(
                city.build_building("farm", x, y, 100, &data),
                Err(CityError::OutOfBounds)
            );
        }
        for (x, y) in [(18, 18), (17, 18), (21, 21)] {
            assert_eq!(
                city.build_building("farm", x, y, 100, &data),
                Err(CityError::Overlap)
            );
        }
        assert_eq!(city, before);
        city.build_building("farm", 38, 38, 100, &data).unwrap();
        city.build_building("farm", 36, 38, 100, &data).unwrap();
        city.collect(145, &data);
        city.build_building("farm", 34, 38, 145, &data).unwrap();
        assert_eq!(
            city.build_building("farm", 32, 38, 145, &data),
            Err(CityError::CountLimit)
        );
    }
    #[test]
    fn construction_cost_builder_and_id_failures_are_atomic() {
        let (data, mut city) = fixture();
        city.resources.wood = 49;
        let before = city.clone();
        assert_eq!(
            city.build_building("farm", 0, 0, 100, &data),
            Err(CityError::InsufficientResources)
        );
        assert_eq!(city, before);
        city.resources = data.start.resources;
        city.upgrade_building(1, 100, &data).unwrap();
        city.build_building("farm", 0, 0, 100, &data).unwrap();
        let before = city.clone();
        assert_eq!(
            city.build_building("lumber_mill", 2, 0, 100, &data),
            Err(CityError::BuildersBusy)
        );
        assert_eq!(city, before);
        let (_, mut exhausted) = fixture();
        exhausted.next_building_id = u32::MAX;
        let before = exhausted.clone();
        assert_eq!(
            exhausted.build_building("farm", 0, 0, 100, &data),
            Err(CityError::IdExhausted)
        );
        assert_eq!(exhausted, before);
        let (_, mut future) = fixture();
        future.collect(u64::MAX, &data);
        let before = future.clone();
        assert_eq!(
            future.build_building("farm", 0, 0, u64::MAX, &data),
            Err(CityError::TimeOverflow)
        );
        assert_eq!(future, before);
    }
    #[test]
    fn cancellation_removes_pending_building_and_releases_footprint() {
        let (data, mut city) = fixture();
        let before = city.resources;
        let id = city.build_building("farm", 0, 0, 100, &data).unwrap();
        city.cancel_upgrade(id, 100, &data).unwrap();
        assert_eq!(city.resources, before);
        assert!(!city.buildings.iter().any(|b| b.id == id));
        let replacement = city.build_building("farm", 0, 0, 100, &data).unwrap();
        assert!(replacement > id);
        assert_eq!(
            city.cancel_upgrade(replacement, 145, &data),
            Err(CityError::NothingToCancel)
        );
        assert_eq!(
            city.buildings
                .iter()
                .find(|b| b.id == replacement)
                .unwrap()
                .level,
            1
        );
    }
    #[test]
    fn construction_offline_and_frequent_collection_match() {
        let (data, mut once) = fixture();
        once.build_building("farm", 0, 0, 100, &data).unwrap();
        once.build_building("lumber_mill", 2, 0, 105, &data)
            .unwrap();
        let mut frequent = once.clone();
        once.collect(400, &data);
        for now in 106..=400 {
            frequent.collect(now, &data);
        }
        assert_eq!(once, frequent);
    }
}
