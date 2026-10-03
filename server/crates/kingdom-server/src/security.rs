//! Bounded admission control shared by all sockets.
use data::ServerLimits;
use std::{
    collections::HashMap,
    net::IpAddr,
    sync::{Arc, Mutex},
    time::Instant,
};

#[derive(Default)]
struct Counts {
    total: u32,
    ips: HashMap<IpAddr, u32>,
}
/// A reservation is released even when upgrade, processing, or sending fails.
pub struct ConnectionPermit {
    counts: Arc<Mutex<Counts>>,
    ip: IpAddr,
}
impl Drop for ConnectionPermit {
    fn drop(&mut self) {
        let mut counts = self.counts.lock().unwrap_or_else(|e| e.into_inner());
        counts.total -= 1;
        if let Some(count) = counts.ips.get_mut(&self.ip) {
            *count -= 1;
            if *count == 0 {
                counts.ips.remove(&self.ip);
            }
        }
    }
}
/// Operational counters use monotonic time, independently of the game clock.
pub struct Security {
    counts: Arc<Mutex<Counts>>,
    attempts: Mutex<HashMap<String, (Instant, u32)>>,
    pub hashes: tokio::sync::Semaphore,
}
impl Security {
    pub fn new(limits: &ServerLimits) -> Self {
        Self {
            counts: Default::default(),
            attempts: Default::default(),
            hashes: tokio::sync::Semaphore::new(limits.concurrent_hashes as usize),
        }
    }
    pub fn connect(&self, ip: IpAddr, limits: &ServerLimits) -> Option<ConnectionPermit> {
        let mut counts = self.counts.lock().unwrap_or_else(|e| e.into_inner());
        if counts.total >= limits.max_connections
            || counts.ips.get(&ip).copied().unwrap_or(0) >= limits.max_connections_per_ip
        {
            return None;
        }
        counts.total += 1;
        *counts.ips.entry(ip).or_default() += 1;
        Some(ConnectionPermit {
            counts: self.counts.clone(),
            ip,
        })
    }
    pub fn attempt(&self, key: String, cap: u32, limits: &ServerLimits) -> bool {
        let now = Instant::now();
        let mut attempts = self.attempts.lock().unwrap_or_else(|e| e.into_inner());
        attempts.retain(|_, (start, _)| {
            now.duration_since(*start).as_millis() < u128::from(limits.auth_window_ms)
        });
        if !attempts.contains_key(&key) && attempts.len() >= limits.max_rate_entries as usize {
            return false;
        }
        let (_, count) = attempts.entry(key).or_insert((now, 0));
        if *count >= cap {
            return false;
        }
        *count += 1;
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn global_and_ip_caps_and_bounded_auth_table() {
        let mut limits = data::GameData::load(data::GameData::repo_data_dir())
            .unwrap()
            .limits;
        limits.max_connections = 2;
        limits.max_connections_per_ip = 1;
        limits.max_rate_entries = 1;
        let security = Security::new(&limits);
        let first: IpAddr = "127.0.0.1".parse().unwrap();
        let second: IpAddr = "127.0.0.2".parse().unwrap();
        let third: IpAddr = "127.0.0.3".parse().unwrap();
        let one = security.connect(first, &limits).unwrap();
        assert!(security.connect(first, &limits).is_none());
        let _two = security.connect(second, &limits).unwrap();
        assert!(security.connect(third, &limits).is_none());
        drop(one);
        assert!(security.connect(third, &limits).is_some());
        assert!(security.attempt("one".into(), 1, &limits));
        assert!(!security.attempt("one".into(), 1, &limits));
        assert!(!security.attempt("two".into(), 1, &limits));
        let permits: Vec<_> = (0..limits.concurrent_hashes)
            .map(|_| security.hashes.try_acquire().unwrap())
            .collect();
        assert!(security.hashes.try_acquire().is_err());
        drop(permits);
        assert!(security.hashes.try_acquire().is_ok());
    }
}
