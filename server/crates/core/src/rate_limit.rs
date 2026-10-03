//! Deterministic token bucket, with caller-supplied monotonic milliseconds.
#[derive(Debug)]
pub struct TokenBucket {
    credit: u128,
    last: u64,
}
impl TokenBucket {
    /// Start with a full burst allowance.
    pub fn new(burst: u32, now: u64) -> Self {
        Self {
            credit: u128::from(burst) * 1000,
            last: now,
        }
    }
    /// Consume one message; backwards clocks do not replenish credit.
    pub fn allow(&mut self, now: u64, rate: u32, burst: u32) -> bool {
        self.credit = (self.credit + u128::from(now.saturating_sub(self.last)) * u128::from(rate))
            .min(u128::from(burst) * 1000);
        self.last = self.last.max(now);
        if self.credit < 1000 {
            return false;
        }
        self.credit -= 1000;
        true
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn burst_refill_backwards_and_extreme_time() {
        let mut b = TokenBucket::new(2, 100);
        assert!(b.allow(100, 2, 2));
        assert!(b.allow(100, 2, 2));
        assert!(!b.allow(100, 2, 2));
        assert!(!b.allow(0, 2, 2));
        assert!(!b.allow(599, 2, 2));
        assert!(b.allow(600, 2, 2));
        assert!(b.allow(u64::MAX, u32::MAX, 2));
        assert!(b.allow(u64::MAX, 2, 2));
        assert!(!b.allow(u64::MAX, 2, 2));
    }
}
