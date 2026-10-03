//! Pure game rules. Nothing in this crate does I/O, reads clocks, or uses
//! randomness directly: callers pass in the current time and game data, which
//! keeps every rule deterministic and unit-testable.

pub mod city;

pub use city::{Building, City, CityError, Upgrade};

/// Unique id of a player within a kingdom.
pub type PlayerId = u64;
