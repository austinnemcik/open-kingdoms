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

#[derive(Debug, Clone, Deserialize)]
pub struct BuildingDef {
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
    buildings: Vec<BuildingDef>,
}

/// All loaded game data.
#[derive(Debug, Clone)]
pub struct GameData {
    buildings: HashMap<String, BuildingDef>,
    pub start: StartConfig,
}

impl GameData {
    /// Load every data file from `dir` (normally the repo's `data/`) and validate.
    pub fn load(dir: impl AsRef<Path>) -> Result<Self, DataError> {
        let dir = dir.as_ref();
        let buildings: BuildingsFile = read_yaml(&dir.join("buildings.yaml"))?;
        let start: StartConfig = read_yaml(&dir.join("start.yaml"))?;
        let data = Self {
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
        for b in self.buildings() {
            if b.footprint == 0 || b.max_level == 0 || b.max_count == 0 {
                return invalid(format!(
                    "{}: footprint, max_level, max_count must be > 0",
                    b.id
                ));
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
        let mut occupied = vec![false; (size * size) as usize];
        for sb in &self.start.buildings {
            let Some(def) = self.building(&sb.kind) else {
                return invalid(format!("start.yaml: unknown building {}", sb.kind));
            };
            if sb.level == 0 || sb.level > def.max_level {
                return invalid(format!("start.yaml: {} level out of range", sb.kind));
            }
            if sb.x + def.footprint > size || sb.y + def.footprint > size {
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
}
