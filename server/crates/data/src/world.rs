//! World generation data. Later systems retain their YAML sections in `systems`
//! until their own typed schemas are implemented.

use std::{collections::BTreeMap, path::Path};

use serde::Deserialize;

use crate::DataError;

/// Validated geometry and terrain inputs for a kingdom.
#[derive(Debug, Clone, Deserialize)]
pub struct WorldConfig {
    pub size: u32,
    pub center: [u32; 2],
    pub chunk_size: u32,
    pub fog_cell_size: u32,
    pub zones: Zones,
    pub rings: Vec<Ring>,
    pub spokes: Spokes,
    pub pass_gap_width: f64,
    pub provinces: Vec<Province>,
    pub terrain: TerrainConfig,
    pub sanctums: Sanctums,
    pub march: March,
    /// Balance sections owned by future world systems; not yet semantically validated.
    #[serde(flatten)]
    pub systems: BTreeMap<String, serde_yaml::Value>,
}

/// Radial zone boundaries; rings occupy the gaps.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Zones {
    pub crown: OuterBound,
    pub heartlands: Bounds,
    pub outlands: InnerBound,
}
/// Exclusive outer radius.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OuterBound {
    pub r_max: f64,
}
/// Inclusive inner radius.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InnerBound {
    pub r_min: f64,
}
/// Inclusive inner and exclusive outer radius.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Bounds {
    pub r_min: f64,
    pub r_max: f64,
}
/// Mountain ring and its radial openings.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ring {
    pub r_min: f64,
    pub r_max: f64,
    pub pass_level: u8,
    pub pass_angles_deg: Vec<f64>,
}
/// Province barriers and their transverse openings.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Spokes {
    pub angles_deg: Vec<f64>,
    pub width: f64,
    pub r_min: f64,
    pub pass_level: u8,
    pub pass_r: f64,
}
/// Stable province name and identifier, in sector order.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Province {
    pub id: String,
    pub name: String,
}
/// Value-noise octave.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Octave {
    pub cell: u32,
    pub weight: f64,
}
/// Terrain thresholds and clearing radius.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TerrainConfig {
    pub noise_octaves: Vec<Octave>,
    pub water_below: f64,
    pub mountain_above: f64,
    pub hills_above: f64,
    pub forest_moisture_above: f64,
    pub clear_radius: f64,
}
/// Static sites and balance information retained for their eventual capture system.
#[derive(Debug, Clone, Deserialize)]
pub struct Sanctums {
    pub kinds: Vec<SiteKind>,
    #[serde(flatten)]
    pub rules: BTreeMap<String, serde_yaml::Value>,
}
/// A family of sites positioned on a circle.
#[derive(Debug, Clone, Deserialize)]
pub struct SiteKind {
    pub id: String,
    pub level: u8,
    pub r: f64,
    pub angles_deg: Vec<f64>,
    #[serde(flatten)]
    pub rules: BTreeMap<String, serde_yaml::Value>,
}
/// March limits consumed by pathfinding and later movement systems.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct March {
    pub min_travel_s: u32,
    pub chase_timeout_s: u32,
    pub chase_repath_ticks: u32,
    pub astar_max_expansions: usize,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct WorldFile {
    world: WorldConfig,
}

impl WorldConfig {
    /// Read and validate a world's generation configuration.
    pub fn load(path: impl AsRef<Path>) -> Result<Self, DataError> {
        let file: WorldFile = crate::read_yaml(path.as_ref())?;
        file.world.validate()?;
        Ok(file.world)
    }

    /// Parse the compile-time repository defaults without I/O or global state.
    pub fn bundled() -> Self {
        let file: WorldFile = serde_yaml::from_str(include_str!("../../../../data/world.yaml"))
            .expect("bundled world YAML must parse");
        file.world
            .validate()
            .expect("bundled world YAML must validate");
        file.world
    }

    /// Reject unsafe dimensions, invalid noise and inconsistent geometry.
    pub fn validate(&self) -> Result<(), DataError> {
        let fail =
            || DataError::Invalid("world.yaml: invalid generation geometry or terrain".into());
        let positive = |n: f64| n.is_finite() && n > 0.0;
        let angles = |a: &[f64]| {
            !a.is_empty()
                && a.iter()
                    .all(|v| v.is_finite() && (-360.0..360.0).contains(v))
                && !a.iter().enumerate().any(|(i, x)| {
                    a[..i]
                        .iter()
                        .any(|y| x.rem_euclid(360.0) == y.rem_euclid(360.0))
                })
        };
        if self.size == 0
            || self.size > 4096
            || self.center.iter().any(|&c| c >= self.size)
            || self.chunk_size == 0
            || !self.size.is_multiple_of(self.chunk_size)
            || self.fog_cell_size == 0
            || !self.size.is_multiple_of(self.fog_cell_size)
            || self.rings.len() != 2
            || self.provinces.len() != 6
            || self.spokes.angles_deg.len() != self.provinces.len()
            || !positive(self.pass_gap_width)
            || !positive(self.terrain.clear_radius)
            || self.terrain.clear_radius > f64::from(self.size)
        {
            return Err(fail());
        }
        let edge = self
            .center
            .iter()
            .map(|&c| c.min(self.size - 1 - c))
            .min()
            .unwrap() as f64;
        if self.rings.iter().any(|r| {
            !positive(r.r_min)
                || !positive(r.r_max)
                || r.r_min >= r.r_max
                || r.r_max >= edge
                || !(1..=3).contains(&r.pass_level)
                || !angles(&r.pass_angles_deg)
        }) || self.rings[0].r_max >= self.rings[1].r_min
            || self.zones.crown.r_max != self.rings[0].r_min
            || self.zones.heartlands.r_min != self.rings[0].r_max
            || self.zones.heartlands.r_max != self.rings[1].r_min
            || self.zones.outlands.r_min != self.rings[1].r_max
            || self.spokes.r_min != self.zones.outlands.r_min
            || !positive(self.spokes.width)
            || !positive(self.spokes.pass_r)
            || self.spokes.pass_r <= self.spokes.r_min
            || self.spokes.pass_r >= edge
            || self.spokes.width >= self.spokes.r_min
            || !angles(&self.spokes.angles_deg)
            || !(1..=3).contains(&self.spokes.pass_level)
            || self.pass_gap_width >= self.terrain.clear_radius * 2.0
        {
            return Err(fail());
        }
        let t = &self.terrain;
        if [
            t.water_below,
            t.mountain_above,
            t.hills_above,
            t.forest_moisture_above,
        ]
        .iter()
        .any(|v| !v.is_finite() || !(0.0..=1.0).contains(v))
            || t.water_below >= t.hills_above
            || t.hills_above >= t.mountain_above
            || t.noise_octaves.is_empty()
            || t.noise_octaves.len() > 16
            || t.noise_octaves
                .iter()
                .any(|o| o.cell == 0 || o.cell > self.size || !positive(o.weight))
            || (t.noise_octaves.iter().map(|o| o.weight).sum::<f64>() - 1.0).abs() > 1e-12
        {
            return Err(fail());
        }
        let mut ids = std::collections::HashSet::new();
        if self
            .provinces
            .iter()
            .any(|p| p.id.is_empty() || p.name.is_empty() || !ids.insert(&p.id))
        {
            return Err(fail());
        }
        let mut ids = std::collections::HashSet::new();
        let mut positions = std::collections::HashSet::new();
        if self.sanctums.kinds.iter().any(|s| {
            s.id.is_empty()
                || !ids.insert(&s.id)
                || !s.r.is_finite()
                || s.r < 0.0
                || s.r + t.clear_radius >= edge
                || !angles(&s.angles_deg)
                || s.angles_deg.iter().any(|a| {
                    let x = (s.r * a.to_radians().cos()).round() as i32;
                    let y = (s.r * a.to_radians().sin()).round() as i32;
                    !positions.insert((x, y))
                })
                || self
                    .rings
                    .iter()
                    .any(|r| s.r + t.clear_radius >= r.r_min && s.r - t.clear_radius < r.r_max)
        }) || !self
            .sanctums
            .kinds
            .iter()
            .any(|s| s.id == "throne" && s.r == 0.0 && s.angles_deg.len() == 1)
            || self.march.astar_max_expansions == 0
            || self.march.min_travel_s == 0
            || self.march.chase_timeout_s == 0
            || self.march.chase_repath_ticks == 0
        {
            return Err(fail());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_matches_loaded_world() {
        let d = WorldConfig::load(crate::GameData::repo_data_dir().join("world.yaml")).unwrap();
        assert_eq!(d.size, 1200);
        assert_eq!(
            d.rings
                .iter()
                .map(|r| r.pass_angles_deg.len())
                .sum::<usize>()
                + d.spokes.angles_deg.len(),
            16
        );
        assert_eq!(
            d.sanctums
                .kinds
                .iter()
                .map(|s| s.angles_deg.len())
                .sum::<usize>(),
            23
        );
        assert_eq!(format!("{d:?}"), format!("{:?}", WorldConfig::bundled()));
    }

    #[test]
    fn rejects_invalid_generation_inputs() {
        let base = WorldConfig::bundled();
        let mutations: &[fn(&mut WorldConfig)] = &[
            |d| d.size = u32::MAX,
            |d| d.chunk_size = 0,
            |d| d.fog_cell_size = 17,
            |d| d.center[0] = d.size,
            |d| d.rings[0].r_max = f64::NAN,
            |d| d.rings[0].pass_angles_deg.push(45.0),
            |d| d.spokes.pass_r = 100.0,
            |d| d.pass_gap_width = -1.0,
            |d| d.terrain.noise_octaves[0].cell = 0,
            |d| d.terrain.noise_octaves[0].weight = 0.8,
            |d| d.terrain.water_below = f64::NAN,
            |d| d.terrain.hills_above = 0.9,
            |d| d.sanctums.kinds[0].r = 140.0,
            |d| d.sanctums.kinds[0].angles_deg.push(f64::INFINITY),
            |d| d.march.astar_max_expansions = 0,
        ];
        for mutate in mutations {
            let mut bad = base.clone();
            mutate(&mut bad);
            assert!(bad.validate().is_err(), "{bad:?}");
        }
    }
}
