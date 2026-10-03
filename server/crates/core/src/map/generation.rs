use data::world::WorldConfig;

use super::{Map, Pass, Site, Terrain, Tile, noise::value_noise};

/// Generate a kingdom using compile-time YAML defaults, without I/O, clocks or
/// global RNG. Generation treats all pass gates as open for connectivity.
pub fn generate_map(seed: u64) -> Map {
    generate_map_with_config(seed, &WorldConfig::bundled()).expect("valid bundled world")
}

/// Generate with explicitly supplied and validated balance data.
pub fn generate_map_with_config(seed: u64, c: &WorldConfig) -> Result<Map, data::DataError> {
    c.validate()?;
    let len = (c.size * c.size) as usize;
    let chunks = c.size / c.chunk_size;
    let mut map = Map {
        size: c.size,
        center: Tile {
            x: c.center[0],
            y: c.center[1],
        },
        chunk_size: c.chunk_size,
        terrain: vec![Terrain::Plains; len],
        moisture: vec![0.0; len],
        pass_ids: vec![None; len],
        passes: Vec::new(),
        sites: Vec::new(),
        chunk_walkable: vec![0; (chunks * chunks) as usize],
        zone_radii: [
            c.rings[0].r_min,
            c.rings[0].r_max,
            c.rings[1].r_min,
            c.rings[1].r_max,
        ],
        astar_max_expansions: c.march.astar_max_expansions,
    };
    let vector = |a: f64| {
        match a.rem_euclid(360.0) {
            0.0 => return (1.0, 0.0),
            90.0 => return (0.0, 1.0),
            180.0 => return (-1.0, 0.0),
            270.0 => return (0.0, -1.0),
            _ => {}
        }
        let (sin, cos) = a.to_radians().sin_cos();
        (cos, sin)
    };
    let position = |r: f64, a: f64| {
        let (cos, sin) = vector(a);
        Tile {
            x: (f64::from(c.center[0]) + r * cos).round() as u32,
            y: (f64::from(c.center[1]) + r * sin).round() as u32,
        }
    };
    let mut ring_passes = Vec::new();
    for ring in &c.rings {
        let mut passes = Vec::new();
        for &angle in &ring.pass_angles_deg {
            let id = map.passes.len() as u16;
            map.passes.push(Pass {
                id,
                level: ring.pass_level,
                center: position((ring.r_min + ring.r_max) / 2.0, angle),
            });
            passes.push((id, vector(angle)));
        }
        ring_passes.push(passes);
    }
    let spokes: Vec<_> = c
        .spokes
        .angles_deg
        .iter()
        .map(|&angle| {
            let id = map.passes.len() as u16;
            map.passes.push(Pass {
                id,
                level: c.spokes.pass_level,
                center: position(c.spokes.pass_r, angle),
            });
            (id, vector(angle))
        })
        .collect();
    for kind in &c.sanctums.kinds {
        let mut angles = kind.angles_deg.clone();
        angles.sort_by(|a, b| a.rem_euclid(360.0).total_cmp(&b.rem_euclid(360.0)));
        for angle in angles {
            map.sites.push(Site {
                kind: kind.id.clone(),
                level: kind.level,
                center: position(kind.r, angle),
            });
        }
    }
    let fbm = |salt, x, y| {
        c.terrain
            .noise_octaves
            .iter()
            .map(|o| o.weight * value_noise(seed ^ salt, o.cell, x, y))
            .sum::<f64>()
    };
    // Retain the geometric barrier mask: noise mountains may be cleared, but
    // ring/spoke mountains never may (including at a pass mouth).
    let mut barrier = vec![false; len];
    for y in 0..c.size {
        for x in 0..c.size {
            let i = (y * c.size + x) as usize;
            let dx = f64::from(x) - f64::from(c.center[0]);
            let dy = f64::from(y) - f64::from(c.center[1]);
            let r2 = dx * dx + dy * dy;
            let mut pass = None;
            for (ring, passes) in c.rings.iter().zip(&ring_passes) {
                if r2 >= ring.r_min * ring.r_min && r2 < ring.r_max * ring.r_max {
                    barrier[i] = true;
                    pass = passes
                        .iter()
                        .find(|(_, (cos, sin))| {
                            dx * cos + dy * sin > 0.0
                                && (dx * sin - dy * cos).abs() <= c.pass_gap_width / 2.0
                        })
                        .map(|p| p.0);
                    break;
                }
            }
            if r2 >= c.spokes.r_min * c.spokes.r_min {
                for &(id, (cos, sin)) in &spokes {
                    let along = dx * cos + dy * sin;
                    if along >= 0.0 && (dx * sin - dy * cos).abs() <= c.spokes.width / 2.0 {
                        barrier[i] = true;
                        if (along - c.spokes.pass_r).abs() <= c.pass_gap_width / 2.0 {
                            pass = Some(id);
                        }
                        break;
                    }
                }
            }
            let moisture = fbm(0x3015, x, y);
            map.moisture[i] = moisture as f32;
            map.terrain[i] = if pass.is_some() {
                Terrain::Pass
            } else if barrier[i] {
                Terrain::Mountain
            } else {
                let elevation = fbm(0xE1E7, x, y);
                if elevation < c.terrain.water_below {
                    Terrain::Water
                } else if elevation > c.terrain.mountain_above {
                    Terrain::Mountain
                } else if elevation > c.terrain.hills_above {
                    Terrain::Hills
                } else if moisture > c.terrain.forest_moisture_above {
                    Terrain::Forest
                } else {
                    Terrain::Plains
                }
            };
            map.pass_ids[i] = pass;
        }
    }
    let clearings: Vec<_> = map
        .passes
        .iter()
        .map(|p| p.center)
        .chain(map.sites.iter().map(|s| s.center))
        .collect();
    let radius = c.terrain.clear_radius.ceil() as i32;
    for center in clearings {
        for dy in -radius..=radius {
            for dx in -radius..=radius {
                if f64::from(dx * dx + dy * dy) > c.terrain.clear_radius.powi(2) {
                    continue;
                }
                let x = center.x as i32 + dx;
                let y = center.y as i32 + dy;
                if x < 0 || y < 0 || x >= c.size as i32 || y >= c.size as i32 {
                    continue;
                }
                let i = (y as u32 * c.size + x as u32) as usize;
                if !barrier[i] {
                    map.terrain[i] = Terrain::Plains;
                }
            }
        }
    }
    let reached = reachable(&map);
    for (i, &reached) in reached.iter().enumerate() {
        if map.terrain[i].is_walkable() && !reached {
            map.terrain[i] = Terrain::Mountain;
            map.pass_ids[i] = None;
        }
        if map.terrain[i].is_walkable() {
            let x = i as u32 % c.size;
            let y = i as u32 / c.size;
            map.chunk_walkable[((y / c.chunk_size) * chunks + x / c.chunk_size) as usize] += 1;
        }
    }
    Ok(map)
}

fn reachable(map: &Map) -> Vec<bool> {
    let mut reached = vec![false; map.terrain.len()];
    let start = map.index(map.center).unwrap();
    let mut queue = Vec::with_capacity(map.terrain.len());
    if map.terrain[start].is_walkable() {
        reached[start] = true;
        queue.push(start);
    }
    let mut head = 0;
    while head < queue.len() {
        let i = queue[head];
        head += 1;
        let x = (i % map.size as usize) as i32;
        let y = (i / map.size as usize) as i32;
        for dy in -1..=1 {
            for dx in -1..=1 {
                if (dx == 0 && dy == 0)
                    || x + dx < 0
                    || y + dy < 0
                    || x + dx >= map.size as i32
                    || y + dy >= map.size as i32
                {
                    continue;
                }
                let j = ((y + dy) as u32 * map.size + (x + dx) as u32) as usize;
                if reached[j] || !map.terrain[j].is_walkable() {
                    continue;
                }
                if dx != 0
                    && dy != 0
                    && (!map.terrain[(y as u32 * map.size + (x + dx) as u32) as usize]
                        .is_walkable()
                        || !map.terrain[((y + dy) as u32 * map.size + x as u32) as usize]
                            .is_walkable())
                {
                    continue;
                }
                reached[j] = true;
                queue.push(j);
            }
        }
    }
    reached
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seed_one_contract() {
        let map = generate_map(1);
        let count = map.terrain.iter().filter(|t| t.is_walkable()).count();
        let share = count as f64 / map.terrain.len() as f64;
        println!(
            "checksum={:016x}, walkable={count}, share={share:.8}",
            map.checksum()
        );
        assert_eq!(map.checksum(), 0x66ed2f8a48d8e987);
        assert_eq!(count, 1_343_387);
        assert_eq!(map.passes.len(), 16);
        for p in &map.passes {
            assert_eq!(map.terrain_at(p.center), Some(Terrain::Pass), "{p:?}");
            assert_eq!(map.pass_ids[map.index(p.center).unwrap()], Some(p.id));
        }
        for s in &map.sites {
            assert_eq!(map.terrain_at(s.center), Some(Terrain::Plains), "{s:?}");
        }
        // Independent four-neighbour traversal: no-corner-cutting diagonals
        // cannot add connectivity that is absent from this cardinal graph.
        let mut seen = vec![false; map.terrain.len()];
        let start = map.index(map.center).unwrap();
        let mut stack = vec![start];
        seen[start] = true;
        while let Some(i) = stack.pop() {
            let x = i % map.size as usize;
            let y = i / map.size as usize;
            for (dx, dy) in [(-1, 0), (1, 0), (0, -1), (0, 1)] {
                let nx = x as i32 + dx;
                let ny = y as i32 + dy;
                if nx < 0 || ny < 0 {
                    continue;
                }
                if let Some(j) = map.index(Tile {
                    x: nx as u32,
                    y: ny as u32,
                }) && !seen[j]
                    && map.terrain[j].is_walkable()
                {
                    seen[j] = true;
                    stack.push(j);
                }
            }
        }
        assert_eq!(seen.iter().filter(|&&v| v).count(), count);
        assert_eq!(map.chunk_walkable.iter().sum::<u32>() as usize, count);
        for cy in 0..map.size / map.chunk_size {
            for cx in 0..map.size / map.chunk_size {
                let actual = (cy * map.chunk_size..(cy + 1) * map.chunk_size)
                    .flat_map(|y| {
                        (cx * map.chunk_size..(cx + 1) * map.chunk_size).map(move |x| Tile { x, y })
                    })
                    .filter(|&t| map.terrain_at(t).unwrap().is_walkable())
                    .count();
                assert_eq!(
                    map.chunk_walkable[(cy * (map.size / map.chunk_size) + cx) as usize] as usize,
                    actual
                );
            }
        }
        // Cardinal spoke boundaries are mathematically exact, not shifted by
        // floating-point cos(pi/2) residues.
        for x in 597..=603 {
            assert_eq!(map.terrain_at(Tile { x, y: 1100 }), Some(Terrain::Mountain));
            assert_eq!(map.terrain_at(Tile { x, y: 1120 }), Some(Terrain::Pass));
        }
        assert!((0.90..=0.96).contains(&share));
    }

    #[test]
    fn deterministic_and_seed_sensitive() {
        let a = generate_map(0);
        let b = generate_map(0);
        let c = generate_map(u64::MAX);
        assert_eq!(a.terrain, b.terrain);
        assert_eq!(a.pass_ids, b.pass_ids);
        assert_eq!(a.moisture, b.moisture);
        assert_ne!(a.checksum(), c.checksum());
        assert!(
            a.terrain
                .iter()
                .zip(&a.pass_ids)
                .all(|(&t, p)| (t == Terrain::Pass) == p.is_some())
        );
        assert_eq!(a.zone(a.center), Some(super::super::Zone::Crown));
        assert_eq!(a.province(Tile { x: 1199, y: 600 }), Some(0));
        assert_eq!(a.terrain_at(Tile { x: 1200, y: 0 }), None);
    }

    #[test]
    #[ignore = "release performance acceptance; run explicitly with --release --ignored --nocapture"]
    fn generation_under_two_seconds() {
        if cfg!(debug_assertions) {
            panic!("run this acceptance test in release mode");
        }
        let start = std::time::Instant::now();
        let map = std::hint::black_box(generate_map(1));
        let elapsed = start.elapsed();
        println!(
            "generate_map(1): {elapsed:?}; checksum {:016x}",
            map.checksum()
        );
        assert!(elapsed < std::time::Duration::from_secs(2));
    }
}
