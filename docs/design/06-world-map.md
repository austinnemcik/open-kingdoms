# 06 — World map

Conventions: [00](00-overview.md). Combat: [05](05-combat.md). Alliance territory: [07 §7](07-alliances.md).
Data: [`data/world.yaml`](data/world.yaml) (copy to `data/world.yaml`). Every number below is in that file.

## 1. Layout

A kingdom is a 1200×1200 tile grid, centre `C = (600, 600)`. For a tile `(x, y)`:
`dx = x − 600`, `dy = y − 600`, `r = sqrt(dx² + dy²)`, `θ = atan2(dy, dx)` in degrees, normalised to `[0, 360)`.

| Zone | Where | Content |
|---|---|---|
| **Crown** | `r < 140` | Level 5–6 nodes, barbarians 18–25, 4 Great Sanctums, the Throne, level-5 Warcamps |
| ring 1 (mountain) | `140 ≤ r < 146` | 4 level-3 passes at θ = 45°, 135°, 225°, 315° |
| **Heartlands** | `146 ≤ r < 340` | Level 3–6 nodes, barbarians 10–20, 6 Sanctums, level 3–4 Warcamps |
| ring 2 (mountain) | `340 ≤ r < 346` | 6 level-2 passes at θ = 0°, 60°, … 300° |
| **Outlands** | `r ≥ 346` | 6 provinces, level 1–5 nodes, barbarians 1–12, 12 Shrines, level 1–2 Warcamps, all new cities |
| spokes (mountain) | Outlands tiles within 3 tiles of the ray θ = 30° + 60°k | 6 level-1 passes, one per spoke at `r = 520` |

Province `k` (0–5) = Outlands tiles with `θ ∈ [60k − 30, 60k + 30)`.
Names in `world.yaml` (`Sunder Coast`, `Greenmere`, `Stonewold`, `Ashfall Reach`, `Hollow Vale`, `Frostmarch`).
22 Sanctum-type sites + the Throne and 16 passes in total; exact positions:
`(round(600 + r·cos θ), round(600 + r·sin θ))` with `r`, `θ` from `world.yaml`.

## 2. Terrain generation

`fn generate_map(seed: u64) -> Map` in `game-core`; pure; the same seed always
gives the same map. Run once at kingdom creation and stored; regenerated
identically for tests.

### 2.1 Hash and noise primitives

```text
splitmix64(x):  x = x + 0x9E3779B97F4A7C15            (all arithmetic wrapping u64)
                z = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9
                z = (z ^ (z >> 27)) * 0x94D049BB133111EB
                return z ^ (z >> 31)
hash3(s, a, b) = splitmix64(s ^ splitmix64(a * 0x9E3779B97F4A7C15 + b))       a, b as u64
unit(h)        = (h >> 11) as f64 / 2^53                                        in [0, 1)
lattice(s, cell, ix, iy) = unit(hash3(s ^ cell, ix, iy))
value_noise(s, cell, x, y):
    fx = x / cell, fy = y / cell; ix = floor(fx), iy = floor(fy); tx = fx − ix, ty = fy − iy
    sx = tx² (3 − 2tx), sy = ty² (3 − 2ty)                                      (smoothstep)
    bilinear blend of lattice at (ix,iy), (ix+1,iy), (ix,iy+1), (ix+1,iy+1) with sx, sy
fbm(s, x, y)   = 0.5·value_noise(s,64,x,y) + 0.3·value_noise(s,32,x,y) + 0.2·value_noise(s,16,x,y)
elevation(x,y) = fbm(seed ^ 0xE1E7, x, y)        moisture(x,y) = fbm(seed ^ 0x3015, x, y)
```

This is the only "randomness" primitive in the game. Every seeded choice in any
spec is `unit(hash3(seed, a, b))` with the stated `a`, `b`; to pick from weights,
walk the cumulative weights in listed order.

### 2.2 Algorithm (in this order)

1. For every tile: `mountain` if in a ring or spoke (§1). Else by noise:
   `water` if `elevation < 0.27`; `mountain` if `elevation > 0.80`;
   `hills` if `elevation > 0.68`; else `forest` if `moisture > 0.58`; else `plains`.
2. **Passes**: for each pass, the gap is every ring/spoke tile within 3.5 tiles
   of the pass centre line (gap width 7); set those tiles to `pass` and record the pass id per tile.
   Ring pass centres use the midpoint radius `(r_min + r_max) / 2`; their
   centre lines are outward radial rays at the listed angles, restricted to
   that ring. Spoke gaps use the perpendicular line at distance `pass_r`
   along that spoke, restricted to that spoke. IDs are zero-based in YAML
   ring/angle order, followed by spoke/angle order. Cardinal directions use
   exact unit vectors to avoid trigonometric residue moving boundary tiles.
3. **Clearings**: set every non-ring, non-spoke tile within 8 tiles of a pass
   centre, a Sanctum-type site centre or the Throne to `plains`.
4. **Connectivity**: treat `plains/forest/hills/pass` as walkable (8-neighbour,
   diagonal only if both orthogonal neighbours are walkable). Flood-fill from
   the Throne tile treating passes as open. Every walkable tile not reached
   becomes `mountain`. (Guarantees no unreachable pockets.)
5. Compute per-chunk walkable tile counts (used by spawning, §4.3).

Terrain enum (`u8`): `0 plains, 1 forest, 2 hills, 3 water, 4 mountain, 5 pass`.
`water` and `mountain` are impassable; `pass` is conditional (§8); the rest are
walkable at the same speed (forest/hills are visual only). Biome tint for the
client: `moisture` and `y/1200` (north = colder); not gameplay.

Unit test: for seed `1`, assert checksum `0x66ed2f8a48d8e987` (start at zero,
fold row-major tile bytes with `acc = splitmix64(acc ^ byte)`), that all 16
pass centres are `pass`, all sanctum centres are `plains`, and walkable share
is between 90 % and 96 %. The specified noise thresholds produce 1,343,387
walkable tiles (93.2908 %); the earlier 55–80 % acceptance range contradicted
the algorithm. Keep the noise thresholds unchanged. Site order is YAML kind
order, then ascending angle normalized to `[0,360)` (including negative angles).

## 3. Map objects

Every object has `id`, `kind`, anchor tile and a square footprint (anchor =
centre tile for odd sizes). Footprints may not overlap each other, nor
impassable terrain, nor pass tiles. Marches are **not** blocked by objects.

| Kind | Footprint | Notes |
|---|---|---|
| `city` | 3×3 | one per player |
| `node` | 1×1 | resource deposit (§4) |
| `barbarian` | 1×1 | PvE army (§5) |
| `warcamp` | 3×3 | rally-only PvE (§6) |
| `pass` | gap tiles | §8 |
| `shrine` / `sanctum` / `great_sanctum` | 5×5 | §9 |
| `throne` | 7×7 | §9 |
| `banner` | 1×1 | alliance flag (07 §7) |
| `stronghold` | 3×3 | alliance fort (07 §7) |
| `army` | point (f64 position) | not an obstacle; any number may share a tile |

A tile is **free** for placement if walkable, not `pass`, not within the
footprint of any object, and not within 1 tile (Chebyshev) of another object's footprint.

## 4. Resource nodes and gathering

### 4.1 Node data

| Level | Food / wood amount | Stone | Gold | Outlands weight | Heartlands | Crown |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40,000 | 30,000 | 20,000 | 25 | 0 | 0 |
| 2 | 100,000 | 75,000 | 50,000 | 30 | 0 | 0 |
| 3 | 200,000 | 150,000 | 100,000 | 25 | 20 | 0 |
| 4 | 400,000 | 300,000 | 200,000 | 15 | 35 | 0 |
| 5 | 700,000 | 525,000 | 350,000 | 5 | 30 | 40 |
| 6 | 1,200,000 | 900,000 | 600,000 | 0 | 15 | 60 |

Type weights: food 35, wood 35, stone 20, gold 10. Node display names:
Cropland, Timber Stand, Stone Outcrop, Gold Vein.

### 4.2 Gathering

- `march { kind: gather, target: node_id, army }`. Rejected at request time if the
  node is occupied by another army (`invalid_target`). On arrival: if free →
  state `gathering`; if now occupied by a non-allied army and the order was sent
  with `attack_if_occupied: true` → attack it; otherwise the army becomes stationed next to the node and the owner is notified.
- One gathering army per node.
- ```text
  rate_per_hour = base_rate[res] × (1 + (gather_speed_pct + gather_speed_<res>_pct) / 100)   # Army scope, when: gathering true
  load_units    = Σ healthy × load × (1 + troop_load_pct/100)
  max_amount    = floor(min(node.remaining, load_units / load_weight[res]))
  finishes_at   = arrived_at + ceil(max_amount / rate_per_hour × 3600) s
  gathered(t)   = min(max_amount, floor(rate_per_hour × (t − arrived_at) / 3600))
  ```
  Base rates per hour: food 18,000, wood 18,000, stone 13,500, gold 9,000.
  Load weight: food 1, wood 1, stone 1.33, gold 2. Rate modifiers are sampled on arrival.
- At `finishes_at` (or on recall, or after surviving an attack and being
  recalled) the army returns home carrying `gathered`; `node.remaining −= gathered`.
  The resources are added to the stockpile when the army enters the city.
- If the gathering army is attacked: gathering pauses (`gathered` frozen) while
  it is engaged; if it survives it resumes with `load_units` recomputed from
  remaining healthy troops (excess over the new load is dropped back into the node).
  If routed, everything it gathered at this node is dropped back into the node; the attacker gets no resources from it.
- A node with `remaining == 0` is removed when the gatherer leaves.
  A partially gathered, unoccupied node is removed 8 h after it was last gathered.
- Alliance territory bonus: gathering inside your own alliance's territory gets `gather_speed_pct +10` (07 §7.3).

### 4.3 Spawning (nodes, barbarians, warcamps)

The map is divided into 30×30-tile chunks (40×40 chunks). The chunk's zone is the zone of its centre tile.

```text
target_nodes(chunk)      = round(walkable_tiles(chunk) × node_density[zone] / 1000)
target_barbarians(chunk) = round(walkable_tiles(chunk) × barbarian_density[zone] / 1000)
```

Every 60 s (and once at kingdom creation, repeated until full) a sweep visits
chunks in index order; for each chunk below a target it spawns **one** object:

```text
n     = chunk.spawn_counter++                       (persisted per chunk)
h     = hash3(kingdom_seed ^ KIND_SALT, chunk_index, n)      # KIND_SALT: 0x6E6F6465 nodes, 0x62617262 barbarians
tile  = try up to 20 candidates: (chunk.x0 + unit(hash3(h, i, 0))×30, chunk.y0 + unit(hash3(h, i, 1))×30), first free one
type/level = weighted picks using unit(hash3(h, 100, 0)) and unit(hash3(h, 101, 0))
```

Chunks whose centre is inside alliance territory spawn as usual. Chunks with no free tile skip.
Warcamps are global, not per chunk: keep `count` of each level alive in its zone;
when one is destroyed, respawn it 2 h later at a seeded free 3×3 spot in that zone
(`hash3(kingdom_seed ^ 0x77617263, level, respawn_counter)`, up to 200 candidates).

## 5. Barbarians

Static PvE armies ("Raider camps"). No commander.

### 5.1 Stats

- Levels 1–25. Troop tier: levels 1–5 T1, 6–10 T2, 11–15 T3, 16–20 T4, 21–25 T5.
- Troops: `round_to_100(500 × level^1.7)` split 34 % infantry / 33 % cavalry / 33 % archer
  (remainder to infantry). Examples: L1 500, L5 7,700, L10 25,100, L15 49,900, L20 81,400, L25 119,000.
- Skill: every 8th normal attack, an extra `damage` of potency 300 (05 §6.3).
- Level range by zone: Outlands 1–12, Heartlands 10–20, Crown 18–25, uniform (seeded).

### 5.2 Rules

- `march { kind: attack, target: barbarian_id, army }`. Requirements: stamina ≥ 36
  (deducted when the order is issued; refunded if the march is recalled before
  engaging); `barbarian.level ≤ player.max_barbarian_level + 1`
  (`max_barbarian_level` starts at 0 and rises on each first victory).
- A barbarian can be fought by several armies of different players at once;
  each engaged player who dealt damage gets the full rewards when it dies.
- If no army is engaged with it for 30 s, its troops reset to full.
- Player losses use `severe_ratio` 0.10, and lightly wounded recover on victory (02 §7).
- On death the barbarian is removed; the spawn sweep replaces it elsewhere in the chunk.

### 5.3 Rewards (per player, per kill)

```text
commander_xp = round(30 × level^1.8) to each commander in the army (× commander_xp_pct)   L1 30, L10 1,893, L25 9,860
resources    = round_to_10(200 × level^1.8) of one type; type by unit(hash3(drop_seed, 0, 0)) over food/wood/stone/gold
               (stone only if player CH ≥ 4, gold only if CH ≥ 10; otherwise re-map to food)
drop_seed    = hash3(kingdom_seed ^ player_id, 0x64726F70, player.barbarian_kills)        (then barbarian_kills += 1)
each row i of `drops` (world.yaml): if level ≥ min_level and unit(hash3(drop_seed, 1, i)) < chance → grant
               count = `count`, or `count_per_10_levels` × (1 + level / 10 rounded down)
```

Drop rows: 30 % a 5-minute speedup of a seeded type (`speedup_any_5m`, 08 §2.2);
2 % a 60-minute one (level ≥ 10); 10 % XP tomes; 3 % a veteran universal sculpture
(level ≥ 5); 1 % a renowned one (level ≥ 15). Rewards are added to the inventory
immediately (not carried home) and listed in the battle report.

## 6. Stamina and Warcamps

**Stamina**: `cap = 600 + stamina_cap_flat`; regenerates 1 point every
`120 / (1 + stamina_regen_pct/100)` s, lazily computed, never above the cap
(items may push it above the cap; regen then pauses). Starts full. Costs:
barbarian 36, Warcamp rally 60 per participant (deducted when the participant's
army joins/launches; refunded if the rally is cancelled).
At 720 regenerated per day this is ~20 barbarians per day before items.

**Warcamps** (rally-only PvE strongholds):

| Level | Zone | Alive at once | Troops | Tier |
|---:|---|---:|---:|---:|
| 1 | Outlands | 30 | 150,000 | T3 |
| 2 | Outlands | 18 | 300,000 | T3 |
| 3 | Heartlands | 12 | 500,000 | T4 |
| 4 | Heartlands | 6 | 800,000 | T4 |
| 5 | Crown | 4 | 1,200,000 | T5 |

Composition and skill as barbarians. Only a rally can attack a Warcamp
(05 §8). It resets to full 30 s after a failed rally. On victory every
participant gets the level's item rewards (`world.yaml`), barbarian-formula XP
with `level × 5` as the level, and the alliance receives a gift of `gift_tier` (07 §6).

## 7. (reserved)

Section number kept free so later sections keep stable references.

## 8. Passes

- 16 passes: 6 level-1 (between provinces), 6 level-2 (Outlands ↔ Heartlands), 4 level-3 (Heartlands ↔ Crown).
- States: `sealed` (before `opens_day`; impassable for everyone) →
  `guarded` (neutral, PvE guardians present, impassable) → `held(alliance_id)`.
- Opening days (kingdom day = whole days since kingdom epoch): level 1 day 3, level 2 day 14, level 3 day 28.
- Guardians are a PvE garrison (`troops`, `tier`, barbarian composition and skill)
  that can be attacked by normal marches or rallies; they reset after 30 s without combat.
  When they are defeated the attackers continue against the pass durability (05 §10);
  the alliance that dealt the most durability damage captures it.
- A held pass: durability resets to max; members of the holding alliance can
  garrison it (stationed armies inside). Other alliances capture it by routing
  the garrison and reducing durability to 0 (05 §10). No guardians return.
- **Passage**: pass tiles are walkable only for marches of players in the
  holding alliance. Everyone else must path around (which, for ring passes,
  means they cannot cross). Scouts obey the same rule.
- A player without an alliance can never cross a pass.
- After capture a pass cannot be attacked for 24 h (`protect_after_capture_s`).

## 9. Sanctums and the Throne

| Kind | Count | Opens (day) | Guardians | Durability | Buff to holding alliance's members (Account scope) |
|---|---:|---:|---|---:|---|
| Shrine | 12 (2 per province) | 7 | 150k T3 | 400,000 | cycles: `gather_speed_pct +5` / `build_speed_pct +2` / `research_speed_pct +2` / `train_speed_pct +5` |
| Sanctum | 6 | 21 | 500k T4 | 900,000 | cycles: `infantry_defense_pct +3` / `cavalry_defense_pct +3` / `archer_defense_pct +3` |
| Great Sanctum | 4 | 35 | 900k T5 | 1,500,000 | cycles: `attack_pct +3` / `health_pct +3` |
| Throne | 1 | 49 | 1.5M T5 | 3,000,000 | `march_speed_pct +5, attack_pct +2, defense_pct +2`; holder's leader becomes Sovereign (09 §3) |

- Same state machine and capture rules as passes (§8), including the 24 h protection.
- "Cycles" = the i-th site of that kind (in ascending angle order) gets buff `i mod len`.
- An alliance may hold any number of sites; buffs from different sites add (03 §1.1).
- Buffs apply only while held; recompute members' Account modifiers on capture/loss/join/leave.
- First capture of each site grants every member online in the last 24 h a mail reward (08 §5.3).

## 10. Scouting and fog of war

### 10.1 Fog

- Per player: a bitset of 80×80 fog cells (15×15 tiles each), 800 bytes.
- Explored at start: cells within 3 cells (Chebyshev) of the city's cell.
  Explored later by: a scout's path (cells within 1 cell of every cell the path
  crosses, applied when the scout **arrives**), any own army's path (the cells it
  crosses, radius 0), city teleport (radius 3), and every cell touching own
  alliance territory (dynamic: visible while it is territory).
- **Unexplored** cells: the server sends neither terrain nor objects; the client draws cloud cover.
  **Explored** cells: terrain and all objects are visible live (there is no line-of-sight radius).
- Marching armies are visible to any player whose current view (§14) contains them and whose fog cell there is explored.
- `scout_explore { }`: sends a free scout to the nearest unexplored cell centre
  within `scout_range` tiles of the city (ties: lowest cell index). Each newly
  explored cell counts for quests (08 §4).

### 10.2 Scouts

- `scouts(scout_camp level)` scouts; each is busy from dispatch until it is back home.
- Speed: `scout_speed × (1 + scout_speed_pct/100)` tiles/min. Range: target must be within `scout_range` path tiles. Scouts cannot be attacked or seen by others.
- `scout { target: MapTarget }` on a city, army, structure, pass, sanctum or node.
  Not allowed on shielded cities (`invalid_target`). Scouting a player removes the scout owner's own peace shield (§12).
- On arrival a **scout report** is mailed (category `scout`), and the target's
  owner gets a "scouted by <name>" notice mail.

Report contents:

| Field | Shown |
|---|---|
| Owner, alliance, coordinates, City Hall level, wall durability / structure durability | always |
| Lootable resources (01 §7) | always (cities) |
| Troop table (garrison incl. reinforcements, or the army) | exact if `scout_camp level ≥ target watchtower level` (armies/structures: target owner's watchtower); otherwise each count rounded to 1 significant digit and prefixed "~" |
| Commanders (ids, levels, stars) | only in the "exact" case |
| Reinforcing armies / garrison members | owner names always; troops per the same rule |
| Incoming rally at the target | never |

## 11. Marches

### 11.1 Army states

```text
in_city → marching(order) → { engaged | gathering | stationed | garrisoned | rally_waiting } → returning → in_city
```

`order.kind ∈ attack, gather, reinforce, rally_join, rally, move, scout (scouts only), return`.

### 11.2 Speed and travel time

```text
speed (tiles/min) = min(speed of every troop kind present, healthy or lightly wounded) × (1 + march_speed_pct / 100)
travel_s          = max(5, ceil(path_length / speed × 60))
```

Unit speeds (02 §2): infantry 36, archer 39, cavalry 54, siege 27. A cavalry
army crosses the whole kingdom (1,200 tiles) in ~22 minutes; a typical
gathering trip of 40 tiles takes ~1 minute. `march_speed_pct` is sampled when
the order is issued and when a battle ends (timed skill buffs to `march_speed_pct`
apply only while their ticks last and only to chase/escape movement resolved per tick, §11.4).

### 11.3 Pathfinding

`fn find_path(map, from, to, mover) -> Option<Vec<Point>>` in `game-core`:

1. Walkability for `mover`: §2.2, with `pass` tiles walkable only if held by the mover's alliance.
2. If the straight segment `from → to` crosses only walkable tiles (supercover
   line: every tile the segment touches) → path = `[from, to]`.
3. Else A* on the 8-connected grid: step cost 1 (orthogonal) or √2 (diagonal;
   allowed only when both adjacent orthogonal tiles are walkable); heuristic =
   octile distance; ties broken by lower `f`, then lower `h`, then lower tile index `y·1200 + x`.
   Abort with `None` after 400,000 expansions (request fails with `invalid_target`, "no route").
4. Smooth: from the first waypoint, repeatedly jump to the farthest later
   waypoint with a clear supercover line.
5. `path_length = Σ Euclidean segment lengths`.

Target points: for an object, the nearest free-standing walkable tile adjacent
to its footprint (lowest distance to `from`, ties by tile index); for an army, its current position.
Positions along the path are computed analytically from `departed_at` and speed
(no per-tick stepping) except while chasing.

### 11.4 Interception, chase, recall

- Any army outside a city/structure can be targeted by `attack`. Cities under a peace shield cannot (§12).
- **Chase**: while the target army is moving, the attacker's path is recomputed
  every 5 ticks (every tick if within 10 tiles) toward the target's current
  position; each tick both advance by `speed/60` tiles. Engagement at distance ≤ 1.5 tiles (05 §2).
  The chase is abandoned (attacker becomes stationed) after 600 s, or when the target enters a city/structure or disappears.
- An engaged target stops (05 §2), so two armies ordered at each other meet in the middle.
- **Recall** (`recall_army`): any army outside the city that is not engaged
  receives a `return` order from its current position (engaged armies: this is a retreat, 05 §7.2).
- **Redirect**: a marching or stationed army can be given any new order; the path starts at its current position.
- Arrival at a target that no longer exists (node gone, barbarian dead, city teleported): the army becomes stationed and the owner is notified; armies with `gather` orders return home instead.

## 12. Who can attack whom, shields

- Never: members of your own alliance; cities under a peace shield; PvE you lack requirements for.
- Armies outside a city are **never** protected by a shield.
- **Peace shield**: `shield_until` on the city. Sources: new-player shield (72 h from account
  creation), shield items (8 h / 24 h / 72 h, 08 §2), raze shield (4 h, 05 §9.4).
  A new shield replaces the current one only if it ends later.
- The shield is removed immediately when the player issues an `attack`, `rally`,
  `rally_join` or `scout` order against another **player's** city, army or
  held structure. (PvE, neutral guardians and gathering do not remove it.)
- **War frenzy**: for 900 s after such an order, and while any own army is engaged
  with a player or the city is in battle, shield items cannot be used (`cooldown`).
- Incoming marches already en route when a shield goes up are turned around on arrival.

## 13. City placement and teleports

- **Spawn** (new account): province with the fewest cities (ties: lowest index);
  candidates `i = 0..200`: `θ` uniform in the province, `r` uniform in `[400, 700]`,
  from `hash3(kingdom_seed ^ player_id, 0x7370776E, i)`; first position whose 3×3
  footprint is free (§3) and not inside any alliance territory. Fallback: scan the province's tiles in index order.
- **Teleport** (`teleport { item_id, x?, y? }`) requirements: every army is in
  the city; the city is not in battle; no rally led. Effects: city moves, fog
  explored around it, incoming marches turn around, scouts in flight return to the new position.

| Item | Destination | Extra rule |
|---|---|---|
| `teleport_novice` | chosen free spot anywhere in the Outlands | only while City Hall ≤ 7 **and** account age ≤ 7 days |
| `teleport_random` | seeded random free spot in the city's current zone (and province) | `hash3(kingdom_seed ^ player_id, 0x74656C65, teleports_used)` |
| `teleport_territory` | chosen free spot inside own alliance territory | — |
| `teleport_targeted` | chosen free spot in an unlocked zone: Outlands always; Heartlands if own alliance holds a level-2 pass; Crown if it holds a level-3 pass | not inside another alliance's territory |

A "chosen free spot" = 3×3 footprint free per §3. Razed cities use the `teleport_random` rule restricted to the Outlands.

## 14. Protocol

`MapTarget = { kind: "city"|"army"|"node"|"barbarian"|"warcamp"|"pass"|"sanctum"|"banner"|"stronghold"|"tile", id?: u64, x?, y? }`.

| Request | Fields | Notes |
|---|---|---|
| `map_view` | `x, y, w, h, lod` | Sets the player's area of interest (tile rect, max 150×150 at lod 0). Server answers `ok` then streams. |
| `get_map_overview` | — | `ok { zones, provinces, passes[], sanctums[], territory_rle, own_city, alliance_cities[] }` for the kingdom map screen |
| `march` | `kind, target: MapTarget, army: ArmySpec, attack_if_occupied?` | new army leaves the city (04 §7) |
| `order_army` | `army_id, kind, target: MapTarget` | redirect an army already outside |
| `recall_army` | `army_id` | |
| `scout` | `target: MapTarget` | |
| `scout_explore` | — | |
| `teleport` | `item_id, x?, y?` | |
| `use_shield` | `item_id` | |
| `search_map` | `what: "node"\|"barbarian", res?, level` | nearest matching free object in explored cells → `ok { x, y, id }` or `not_found` |

| Push | Fields |
|---|---|
| `map_chunk` | `cx, cy, version, terrain: base64(900 bytes)` — sent once per chunk per session for explored chunks intersecting the view (partially explored chunks: unexplored tiles as `255`) |
| `map_objects` | `objects: [MapObject]` full list for newly visible chunks |
| `map_object_update` / `map_object_remove` | one object / `id` |
| `army_update` | `army: { id, owner, alliance_tag, state, path: [[x,y]…], departed_at, arrives_at, speed, x, y, troops_total?, commander_primary? }` — own armies get full detail (`troops`, `light`, `load`, `gathered`, `finishes_at`) |
| `fog_update` | `cells: [index…]` newly explored |
| `stamina_update` | `stamina, stamina_at, cap` |

`MapObject = { id, kind, x, y, level?, owner?: {player_id, name, alliance_tag, power}, res?, remaining?, state?, durability?, shield_until?, burning_until?, occupied_by? }`.

**Level of detail**: `lod 0` (zoomed in): everything in view. `lod 1` (view up
to 400×400): no nodes/barbarians, armies only of own alliance and those
targeting own alliance. `lod 2` (whole map): only passes, sanctums, strongholds,
territory (from `get_map_overview`) and own/alliance cities; no streaming.
Updates are sent only for objects inside the current view; the server keeps an
index chunk → subscribed sessions.

## 15. Edge cases

- Two gather marches for the same free node arrive in the same tick: lower army id gets it.
- City teleports while its owner's scout is out: scout returns to the new position.
- Pass captured while enemy marches are inside the gap: they finish their current path (no eviction); new paths obey the new owner.
- Pass lost while own armies are beyond it: paths obey the new passability. If `find_path` home fails, the army arrives home after its straight-line travel time, ignoring terrain (stranded-army rule), so troops are never lost to geometry.
- Object spawn on a tile where an army is stationed: allowed (armies are not obstacles).
- Player quits alliance while garrisoning a structure or reinforcing: those armies are sent home.
- Stamina refund on recall happens only if the army never engaged.
- Barbarian killed while a second player's march is en route: that march's stamina is refunded and the army becomes stationed.
- Kingdom day used for openings is computed from the kingdom epoch stored at creation, not from server uptime.
