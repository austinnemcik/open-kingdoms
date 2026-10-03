//! Pure deterministic world geometry and terrain (spec 06 §1–2).

mod generation;
pub mod noise;

pub use generation::{generate_map, generate_map_with_config};

/// Integer tile centre. Tile and chunk arrays are row-major (y, then x).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Tile {
    pub x: u32,
    pub y: u32,
}

/// Stable terrain byte values for persistence and map chunks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Terrain {
    Plains = 0,
    Forest = 1,
    Hills = 2,
    Water = 3,
    Mountain = 4,
    Pass = 5,
}

impl Terrain {
    /// Geometric connectivity, treating every pass as open. Gameplay must also
    /// check pass ownership when this returns true for a pass.
    pub fn is_walkable(self) -> bool {
        !matches!(self, Self::Water | Self::Mountain)
    }
}

/// Geographic zone, including the two mountain bands.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Zone {
    Crown,
    InnerRing,
    Heartlands,
    OuterRing,
    Outlands,
}

/// Static pass definition. IDs are zero-based: rings in YAML order, then spokes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pass {
    pub id: u16,
    pub level: u8,
    pub center: Tile,
}

/// Static sanctum or Throne centre; dynamic ownership belongs to a later system.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Site {
    pub kind: String,
    pub level: u8,
    pub center: Tile,
}

/// Immutable generated terrain. Use accessors for checked coordinates. Terrain,
/// moisture and pass-ID arrays share the same row-major index.
#[derive(Debug, Clone)]
pub struct Map {
    pub(super) size: u32,
    pub(super) center: Tile,
    pub(super) chunk_size: u32,
    pub(super) terrain: Vec<Terrain>,
    pub(super) moisture: Vec<f32>,
    pub(super) pass_ids: Vec<Option<u16>>,
    pub(super) passes: Vec<Pass>,
    pub(super) sites: Vec<Site>,
    pub(super) chunk_walkable: Vec<u32>,
    pub(super) zone_radii: [f64; 4],
    pub(super) astar_max_expansions: usize,
}

impl Map {
    /// Map side length in tiles.
    pub fn size(&self) -> u32 {
        self.size
    }
    /// Throne tile and radial origin.
    pub fn center(&self) -> Tile {
        self.center
    }
    /// Side length of each chunk in tiles.
    pub fn chunk_size(&self) -> u32 {
        self.chunk_size
    }
    /// Configured A* request work limit.
    pub fn astar_max_expansions(&self) -> usize {
        self.astar_max_expansions
    }
    /// Terrain in row-major order. Cast enum entries to `u8` for wire bytes.
    pub fn terrain(&self) -> &[Terrain] {
        &self.terrain
    }
    /// Moisture in `[0,1)`, rounded to f32 for visual tint only.
    pub fn moisture(&self) -> &[f32] {
        &self.moisture
    }
    /// Pass ID per tile, absent on every non-pass tile.
    pub fn pass_ids(&self) -> &[Option<u16>] {
        &self.pass_ids
    }
    /// Stable pass centres and levels.
    pub fn passes(&self) -> &[Pass] {
        &self.passes
    }
    /// Sites in YAML kind order, then ascending normalized angle.
    pub fn sites(&self) -> &[Site] {
        &self.sites
    }
    /// Open-pass walkable counts in row-major chunk order.
    pub fn chunk_walkable(&self) -> &[u32] {
        &self.chunk_walkable
    }
    /// Convert a tile to a checked row-major index.
    pub fn index(&self, tile: Tile) -> Option<usize> {
        (tile.x < self.size && tile.y < self.size).then(|| (tile.y * self.size + tile.x) as usize)
    }
    /// Terrain at a tile, or `None` outside the map.
    pub fn terrain_at(&self, tile: Tile) -> Option<Terrain> {
        self.index(tile).map(|i| self.terrain[i])
    }
    /// Zone at a tile; ring terrain is classified separately from playable zones.
    pub fn zone(&self, tile: Tile) -> Option<Zone> {
        self.index(tile)?;
        let r = (f64::from(tile.x) - f64::from(self.center.x))
            .hypot(f64::from(tile.y) - f64::from(self.center.y));
        Some(match self.zone_radii.iter().position(|&bound| r < bound) {
            Some(0) => Zone::Crown,
            Some(1) => Zone::InnerRing,
            Some(2) => Zone::Heartlands,
            Some(3) => Zone::OuterRing,
            _ => Zone::Outlands,
        })
    }
    /// Outlands sector `k`, spanning `[60k-30,60k+30)` degrees.
    pub fn province(&self, tile: Tile) -> Option<usize> {
        if self.zone(tile)? != Zone::Outlands {
            return None;
        }
        let angle = (f64::from(tile.y) - f64::from(self.center.y))
            .atan2(f64::from(tile.x) - f64::from(self.center.x))
            .to_degrees();
        Some(((angle + 30.0).rem_euclid(360.0) / 60.0).floor() as usize)
    }
    /// Seed-independent checksum definition: start at zero and fold each terrain
    /// byte with `splitmix64(acc ^ byte)` in row-major order.
    pub fn checksum(&self) -> u64 {
        self.terrain
            .iter()
            .fold(0, |acc, &t| noise::splitmix64(acc ^ t as u64))
    }
}
