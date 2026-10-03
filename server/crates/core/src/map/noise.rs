//! The seeded primitives shared by map generation and later world spawning.

/// SplitMix64 with explicitly wrapping arithmetic (spec 06 §2.1).
pub fn splitmix64(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9E3779B97F4A7C15);
    let z = (x ^ (x >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    let z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

/// Stable seed plus two-coordinate hash.
pub fn hash3(seed: u64, a: u64, b: u64) -> u64 {
    splitmix64(seed ^ splitmix64(a.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(b)))
}

/// Convert a hash to a uniform value in `[0, 1)` using its upper 53 bits.
pub fn unit(hash: u64) -> f64 {
    (hash >> 11) as f64 / 9_007_199_254_740_992.0
}

/// Smooth bilinear lattice noise. Coordinates and cell size are nonnegative,
/// with a positive cell size, as ensured by world data validation.
pub fn value_noise(seed: u64, cell: u32, x: u32, y: u32) -> f64 {
    let fx = f64::from(x) / f64::from(cell);
    let fy = f64::from(y) / f64::from(cell);
    let ix = fx.floor() as u64;
    let iy = fy.floor() as u64;
    let tx = fx - fx.floor();
    let ty = fy - fy.floor();
    let sx = tx * tx * (3.0 - 2.0 * tx);
    let sy = ty * ty * (3.0 - 2.0 * ty);
    let lattice = |x, y| unit(hash3(seed ^ u64::from(cell), x, y));
    let blend = |a: f64, b: f64, t: f64| a * (1.0 - t) + b * t;
    blend(
        blend(lattice(ix, iy), lattice(ix + 1, iy), sx),
        blend(lattice(ix, iy + 1), lattice(ix + 1, iy + 1), sx),
        sy,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn primitive_vectors() {
        assert_eq!(splitmix64(0), 0xe220a8397b1dcdaf);
        assert_eq!(splitmix64(1), 0x910a2dec89025cc1);
        assert_eq!(unit(0), 0.0);
        assert_eq!(unit(u64::MAX), 1.0 - 2.0_f64.powi(-53));
        assert_eq!(value_noise(1, 64, 64, 128), unit(hash3(1 ^ 64, 1, 2)));
        let _ = hash3(u64::MAX, u64::MAX, u64::MAX);
    }
}
