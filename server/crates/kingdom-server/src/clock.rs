//! Injected time source. Every game timestamp is Unix seconds.
use std::{
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

/// A thread-safe source of Unix seconds; game-core never reads this directly.
pub trait Clock: Send + Sync {
    /// Current Unix time in whole seconds.
    fn now(&self) -> u64;
}

/// Production wall clock. Pre-epoch system times safely clamp to zero.
#[derive(Default)]
pub struct RealClock;
impl Clock for RealClock {
    fn now(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }
}

/// Explicitly controlled clock for deterministic simulations and integration tests.
pub struct ManualClock(AtomicU64);
impl ManualClock {
    /// Start at the supplied Unix second.
    pub fn new(now: u64) -> Self {
        Self(AtomicU64::new(now))
    }
    /// Set time, including backwards jumps when testing clock corrections.
    pub fn set(&self, now: u64) {
        self.0.store(now, Ordering::SeqCst);
    }
}
impl Clock for ManualClock {
    fn now(&self) -> u64 {
        self.0.load(Ordering::SeqCst)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn manual_clock_is_exact_and_can_move_backwards() {
        let clock = ManualClock::new(123);
        assert_eq!(clock.now(), 123);
        clock.set(5);
        assert_eq!(clock.now(), 5);
        clock.set(u64::MAX);
        assert_eq!(clock.now(), u64::MAX);
    }
    #[test]
    fn real_clock_uses_unix_seconds() {
        let before = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        assert!((before..=before + 1).contains(&RealClock.now()));
    }
}
