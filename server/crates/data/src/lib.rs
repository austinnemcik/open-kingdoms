//! Loads and validates the YAML balance files in the repository's `data/`
//! directory. Everything tunable about the game lives in those files; Rust code
//! should never hard-code balance numbers.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use serde::Deserialize;

#[derive(Debug, thiserror::Error)]
pub enum DataError {
    #[error("reading {path}: {source}")]
    Io {
        path: PathBuf,
        source: std::io::Error,
    },
    #[error("parsing {path}: {source}")]
    Parse {
        path: PathBuf,
        source: serde_yaml::Error,
    },
    #[error("invalid data: {0}")]
    Invalid(String),
}

/// The four city resources.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, serde::Serialize)]
pub struct Resources {
    pub food: u64,
    pub wood: u64,
    pub stone: u64,
    pub gold: u64,
}

impl Resources {
    /// Stable wire/economy order: food, wood, stone, gold.
    pub fn values(self) -> [u64; 4] {
        [self.food, self.wood, self.stone, self.gold]
    }
    /// Build a resource bundle in the stable economy order.
    pub fn from_values(v: [u64; 4]) -> Self {
        Self {
            food: v[0],
            wood: v[1],
            stone: v[2],
            gold: v[3],
        }
    }
    /// Saturating resource-wise addition for aggregation.
    pub fn saturating_add(self, other: Self) -> Self {
        let a = self.values();
        let b = other.values();
        Self::from_values(std::array::from_fn(|i| a[i].saturating_add(b[i])))
    }

    fn scaled(self, factor: f64) -> Self {
        let s = |v: u64| (v as f64 * factor).round() as u64;
        Self {
            food: s(self.food),
            wood: s(self.wood),
            stone: s(self.stone),
            gold: s(self.gold),
        }
    }
}

#[derive(Debug, Clone, Copy, Deserialize)]
pub struct CostCurve {
    pub base: Resources,
    pub growth: f64,
}

#[derive(Debug, Clone, Copy, Deserialize)]
pub struct TimeCurve {
    pub base_s: u64,
    pub growth: f64,
}

/// A building that must reach target level minus this offset before upgrading.
#[derive(Debug, Clone, Deserialize)]
pub struct LevelRequirement {
    pub kind: String,
    pub levels_below_target: u32,
}

/// Free builder slots and cancellation policy; all economy knobs live in YAML.
#[derive(Debug, Clone, Deserialize)]
pub struct ConstructionConfig {
    pub builder_slots: u32,
    pub cancellation_refund_percent: u32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BuildingDef {
    /// Prerequisites for the target upgrade level, expressed relative to it.
    #[serde(default)]
    pub upgrade_requirements: Vec<LevelRequirement>,
    /// Units produced per hour at level one, with per-level growth.
    #[serde(default)]
    pub production: Option<CostCurve>,
    /// Storage contributed by this building, with per-level growth.
    #[serde(default)]
    pub capacity: Option<CostCurve>,
    pub id: String,
    pub name: String,
    pub footprint: u32,
    pub max_level: u32,
    pub max_count: u32,
    pub requires_city_hall: u32,
    /// Cost to construct (reach level 1).
    pub cost: CostCurve,
    /// Cost to go from `level - 1` to `level`, for `level >= 2`.
    pub upgrade_cost: CostCurve,
    pub build_time: TimeCurve,
    pub upgrade_time: TimeCurve,
}

impl BuildingDef {
    /// Production per hour; unfinished level-zero buildings contribute nothing.
    pub fn production_for_level(&self, level: u32) -> Resources {
        Self::curve_at(self.production, level)
    }
    /// Storage capacity; unfinished level-zero buildings contribute nothing.
    pub fn capacity_for_level(&self, level: u32) -> Resources {
        Self::curve_at(self.capacity, level)
    }
    fn curve_at(curve: Option<CostCurve>, level: u32) -> Resources {
        if level == 0 {
            return Resources::default();
        }
        curve.map_or(Resources::default(), |c| {
            c.base.scaled(c.growth.powf(f64::from(level - 1)))
        })
    }

    /// Resources needed to reach `level` (1 = construction).
    pub fn cost_for_level(&self, level: u32) -> Resources {
        if level <= 1 {
            self.cost.base
        } else {
            let c = self.upgrade_cost;
            c.base.scaled(c.growth.powi(level as i32 - 2))
        }
    }

    /// Seconds needed to reach `level` (1 = construction).
    pub fn time_for_level(&self, level: u32) -> u64 {
        if level <= 1 {
            self.build_time.base_s
        } else {
            let t = self.upgrade_time;
            (t.base_s as f64 * t.growth.powi(level as i32 - 2)).round() as u64
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct StartBuilding {
    pub kind: String,
    pub level: u32,
    pub x: u32,
    pub y: u32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct StartConfig {
    pub city_size: u32,
    pub resources: Resources,
    pub buildings: Vec<StartBuilding>,
}

#[derive(Debug, Deserialize)]
struct BuildingsFile {
    construction: ConstructionConfig,
    buildings: Vec<BuildingDef>,
}

/// All loaded game data.
#[derive(Debug, Clone)]
pub struct GameData {
    pub construction: ConstructionConfig,
    buildings: HashMap<String, BuildingDef>,
    pub start: StartConfig,
}

impl GameData {
    /// Load every data file from `dir` (normally the repo's `data/`) and validate.
    pub fn load(dir: impl AsRef<Path>) -> Result<Self, DataError> {
        let dir = dir.as_ref();
        let buildings: BuildingsFile = read_yaml(&dir.join("buildings.yaml"))?;
        let start: StartConfig = read_yaml(&dir.join("start.yaml"))?;
        let mut ids = std::collections::HashSet::new();
        if buildings.buildings.iter().any(|b| !ids.insert(&b.id)) {
            return Err(DataError::Invalid("duplicate building id".into()));
        }
        let data = Self {
            construction: buildings.construction,
            buildings: buildings
                .buildings
                .into_iter()
                .map(|b| (b.id.clone(), b))
                .collect(),
            start,
        };
        data.validate()?;
        Ok(data)
    }

    /// Path of the repo's `data/` directory, for tests and local runs.
    pub fn repo_data_dir() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../data")
    }

    pub fn building(&self, id: &str) -> Option<&BuildingDef> {
        self.buildings.get(id)
    }

    pub fn buildings(&self) -> impl Iterator<Item = &BuildingDef> {
        self.buildings.values()
    }

    fn validate(&self) -> Result<(), DataError> {
        let invalid = |msg: String| Err(DataError::Invalid(msg));
        if self.building("city_hall").is_none() {
            return invalid("buildings.yaml must define city_hall".into());
        }
        if self.construction.builder_slots == 0
            || self.construction.cancellation_refund_percent > 100
        {
            return invalid("invalid construction slots/refund policy".into());
        }
        for b in self.buildings() {
            for requirement in &b.upgrade_requirements {
                if self.building(&requirement.kind).is_none()
                    || requirement.levels_below_target == 0
                    || requirement.levels_below_target > b.max_level
                {
                    return invalid(format!("{}: invalid upgrade requirement", b.id));
                }
            }
            if b.upgrade_time.base_s == 0 || (b.id != "city_hall" && b.build_time.base_s == 0) {
                return invalid(format!(
                    "{}: construction/upgrade timers must be positive",
                    b.id
                ));
            }
            for (base, growth) in [
                (b.upgrade_time.base_s, b.upgrade_time.growth),
                (b.build_time.base_s, b.build_time.growth),
            ] {
                let max = base as f64 * growth.powf(f64::from(b.max_level.saturating_sub(1)));
                if !max.is_finite() || max >= u64::MAX as f64 {
                    return invalid(format!("{}: timer curve overflows", b.id));
                }
            }
            for curve in [b.cost, b.upgrade_cost] {
                for base in curve.base.values() {
                    let max =
                        base as f64 * curve.growth.powf(f64::from(b.max_level.saturating_sub(1)));
                    if !max.is_finite() || max >= u64::MAX as f64 {
                        return invalid(format!("{}: cost curve overflows", b.id));
                    }
                }
            }
            if b.footprint == 0 || b.max_level == 0 || b.max_count == 0 {
                return invalid(format!(
                    "{}: footprint, max_level, max_count must be > 0",
                    b.id
                ));
            }
            if b.max_level > 100 {
                return invalid(format!("{}: max_level exceeds supported limit 100", b.id));
            }
            for curve in [b.production, b.capacity].into_iter().flatten() {
                if !curve.growth.is_finite()
                    || curve.growth < 1.0
                    || curve.base.values().iter().all(|v| *v == 0)
                {
                    return invalid(format!("{}: invalid production/capacity curve", b.id));
                }
                for base in curve.base.values() {
                    let max = base as f64 * curve.growth.powf(f64::from(b.max_level - 1));
                    if !max.is_finite() || max >= u64::MAX as f64 {
                        return invalid(format!("{}: economy curve overflows", b.id));
                    }
                }
            }
            for g in [
                b.cost.growth,
                b.upgrade_cost.growth,
                b.build_time.growth,
                b.upgrade_time.growth,
            ] {
                if !(g.is_finite() && g >= 1.0) {
                    return invalid(format!("{}: growth factors must be >= 1.0", b.id));
                }
            }
        }
        let size = self.start.city_size;
        if size == 0 || size > 1024 {
            return invalid("city_size must be 1..=1024".into());
        }
        let mut occupied = vec![false; (size * size) as usize];
        for sb in &self.start.buildings {
            let Some(def) = self.building(&sb.kind) else {
                return invalid(format!("start.yaml: unknown building {}", sb.kind));
            };
            if sb.level == 0 || sb.level > def.max_level {
                return invalid(format!("start.yaml: {} level out of range", sb.kind));
            }
            if sb.x.checked_add(def.footprint).is_none_or(|v| v > size)
                || sb.y.checked_add(def.footprint).is_none_or(|v| v > size)
            {
                return invalid(format!("start.yaml: {} lies outside the city", sb.kind));
            }
            for dy in 0..def.footprint {
                for dx in 0..def.footprint {
                    let cell = &mut occupied[((sb.y + dy) * size + sb.x + dx) as usize];
                    if *cell {
                        return invalid(format!(
                            "start.yaml: {} overlaps another building",
                            sb.kind
                        ));
                    }
                    *cell = true;
                }
            }
        }
        Ok(())
    }
}

fn read_yaml<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T, DataError> {
    let text = std::fs::read_to_string(path).map_err(|source| DataError::Io {
        path: path.to_owned(),
        source,
    })?;
    serde_yaml::from_str(&text).map_err(|source| DataError::Parse {
        path: path.to_owned(),
        source,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn data() -> GameData {
        GameData::load(GameData::repo_data_dir()).expect("repo data must load and validate")
    }

    #[test]
    fn repo_data_is_valid() {
        let d = data();
        assert!(d.building("city_hall").is_some());
        assert!(!d.start.buildings.is_empty());
    }

    #[test]
    fn upgrade_costs_grow_with_level() {
        let d = data();
        let farm = d.building("farm").unwrap();
        assert_eq!(farm.cost_for_level(1).wood, 50);
        assert_eq!(farm.cost_for_level(2).wood, 80);
        assert!(farm.cost_for_level(10).wood > farm.cost_for_level(9).wood);
        assert!(farm.time_for_level(10) > farm.time_for_level(2));
    }
    #[test]
    fn economy_curves_and_invalid_data() {
        let d = data();
        let farm = d.building("farm").unwrap();
        assert_eq!(farm.production_for_level(0), Resources::default());
        assert_eq!(farm.production_for_level(1).food, 600);
        assert_eq!(farm.production_for_level(2).food, 900);
        assert!(farm.capacity_for_level(2).food > farm.capacity_for_level(1).food);
        for growth in [f64::NAN, f64::INFINITY, 0.5, f64::MAX] {
            let mut bad = data();
            bad.buildings
                .get_mut("farm")
                .unwrap()
                .production
                .as_mut()
                .unwrap()
                .growth = growth;
            assert!(bad.validate().is_err());
        }
        let mut bad = data();
        bad.buildings
            .get_mut("farm")
            .unwrap()
            .capacity
            .as_mut()
            .unwrap()
            .base = Resources::default();
        assert!(bad.validate().is_err());
        bad = data();
        bad.start.buildings[0].x = u32::MAX;
        assert!(bad.validate().is_err());
    }
    #[test]
    fn construction_config_rejects_invalid_rules() {
        let mut d = data();
        d.construction.builder_slots = 0;
        assert!(d.validate().is_err());
        let mut d = data();
        d.construction.cancellation_refund_percent = 101;
        assert!(d.validate().is_err());
        for kind in ["missing", ""] {
            let mut d = data();
            d.buildings
                .get_mut("city_hall")
                .unwrap()
                .upgrade_requirements[0]
                .kind = kind.into();
            assert!(d.validate().is_err());
        }
        let mut d = data();
        d.buildings.get_mut("farm").unwrap().upgrade_time.base_s = 0;
        assert!(d.validate().is_err());
        let mut d = data();
        d.buildings.get_mut("farm").unwrap().upgrade_cost.growth = f64::MAX;
        assert!(d.validate().is_err());
    }
}
