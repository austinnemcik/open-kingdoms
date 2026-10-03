# 01 — City and economy

Conventions: [00-overview.md](00-overview.md). Modifier keys: [03 §1](03-research.md).
Data: [`data/buildings.yaml`](data/buildings.yaml) (generated; copy to `data/buildings.yaml`).

## 1. Resources

| Resource | Usable from | Produced by | Gathered from |
|---|---|---|---|
| `food` | CH 1 | `farm` | Cropland nodes |
| `wood` | CH 1 | `lumber_mill` | Timber nodes |
| `stone` | CH 4 (quarry unlock) | `quarry` | Stone nodes |
| `gold` | CH 10 (goldmine unlock) | `goldmine` | Gold nodes |

- The city **stockpile** has no upper limit. `u64`, never negative.
- No cost in the game contains stone before level 5 or gold before level 11
  of the thing being bought, so a resource is never demanded before it is obtainable.
- Resources enter the stockpile from: collecting production buildings (§6),
  returning gathering marches (06 §4), loot, rewards and resource items (08 §2),
  caravans (07 §9). They leave through costs, being looted (§7) and caravans.

## 2. Data schema

`data/buildings.yaml` (replaces the old `cost`/`upgrade_cost` growth curves):

```yaml
buildings:
  - id: farm                # snake_case, unique
    name: Farm              # display name (English; l10n key = "building.<id>")
    footprint: 2            # square edge in city tiles
    max_level: 25
    max_count: 4            # copies a city may own
    requires_city_hall: 1   # CH level needed to construct the first copy
    levels:                 # exactly max_level entries, level ascending from 1
      - level: 1
        cost: { food: 0, wood: 30, stone: 0, gold: 0 }   # to REACH this level
        time_s: 1                                        # to REACH this level (before speed bonuses)
        requires: { city_hall: 1 }                       # other buildings: highest copy must be >= value
        power: 10                                        # cumulative power AT this level
        production_per_hour: 360                         # ...then building-specific stat columns (see §3)
        buffer_capacity: 3600
```

Rust shape (in `server/crates/data`): `BuildingDef { id, name, footprint, max_level,
max_count, requires_city_hall, levels: Vec<BuildingLevel> }`, `BuildingLevel { level,
cost: Resources, time_s: u64, requires: BTreeMap<String,u32>, power: u64,
#[serde(flatten)] stats: BTreeMap<String, f64> }`. Accessors:
`def.level(n) -> &BuildingLevel`, `level.stat("train_batch") -> f64` (0 if absent).

Validation (in addition to the current checks): `levels.len() == max_level`;
`levels[i].level == i+1`; every `requires` key is a known building id and its
value ≤ that building's `max_level`; `power` non-decreasing; no stone cost below
level 5 and no gold cost below level 11 unless the building's
`requires_city_hall` is ≥ 4 / ≥ 10 respectively; `city_hall` level `L` never
requires another building above `L-1`; every non-City-Hall level requires
`city_hall ≥ level` (this is how "no building may exceed City Hall" is enforced —
there is no separate rule in code).

### 2.1 Starting city (`data/start.yaml`)

```yaml
city_size: 40
resources: { food: 1000, wood: 1000, stone: 0, gold: 0 }
buildings:
  - { kind: city_hall, level: 1, x: 18, y: 18 }
  - { kind: farm, level: 1, x: 12, y: 22 }
  - { kind: lumber_mill, level: 1, x: 24, y: 12 }
  - { kind: barracks, level: 1, x: 12, y: 13 }
  - { kind: wall, level: 1, x: 19, y: 37 }      # gatehouse on the south edge
troops: { infantry_t1: 100 }
items: { speedup_build_5m: 10, speedup_universal_5m: 10, teleport_novice: 2 }
shield_s: 259200                                 # 3-day new-player peace shield (06 §12)
```

## 3. Building catalogue

All 19 buildings. "Factor" is the fraction of the City Hall cost/time at the same
level that the building costs (see `okdata.py`); every cell below is generated
from it and then rounded, and **the table values are authoritative**, not the factor.

<!-- GEN:building_summary -->
| id | Name | Footprint | Max count | Unlock CH | Factor | Total time 1-25 (one copy) | Total cost 1-25 (one copy) |
|---|---|---:|---:|---:|---:|---:|---:|
| `city_hall` | City Hall | 4x4 | 1 | 0 | 1.0 | 44d 20h 31m | 107,311,200 |
| `wall` | City Wall | 2x2 | 1 | 1 | 0.6 | 26d 21h 56m | 64,376,630 |
| `farm` | Farm | 2x2 | 4 | 1 | 0.2 | 8d 23h 16m | 21,472,650 |
| `lumber_mill` | Lumber Mill | 2x2 | 4 | 1 | 0.2 | 8d 23h 16m | 21,472,650 |
| `quarry` | Quarry | 2x2 | 4 | 4 | 0.2 | 8d 23h 16m | 21,465,330 |
| `goldmine` | Goldmine | 2x2 | 4 | 10 | 0.2 | 8d 23h 16m | 21,470,510 |
| `storehouse` | Storehouse | 2x2 | 1 | 2 | 0.4 | 17d 22h 32m | 42,936,640 |
| `barracks` | Barracks | 3x3 | 1 | 1 | 0.55 | 24d 16h 6m | 59,011,953 |
| `archery_range` | Archery Range | 3x3 | 1 | 3 | 0.55 | 24d 16h 6m | 59,011,953 |
| `stable` | Stable | 3x3 | 1 | 5 | 0.55 | 24d 16h 6m | 59,011,953 |
| `siege_workshop` | Siege Workshop | 3x3 | 1 | 7 | 0.55 | 24d 16h 6m | 59,011,953 |
| `hospital` | Hospital | 2x2 | 4 | 2 | 0.3 | 13d 11h 0m | 32,182,024 |
| `academy` | Academy | 3x3 | 1 | 3 | 0.7 | 31d 9h 32m | 75,130,204 |
| `scout_camp` | Scout Camp | 2x2 | 1 | 2 | 0.35 | 15d 16h 52m | 37,549,263 |
| `watchtower` | Watchtower | 2x2 | 1 | 5 | 0.45 | 20d 4h 23m | 48,289,895 |
| `alliance_hall` | Alliance Hall | 3x3 | 1 | 3 | 0.5 | 22d 10h 15m | 53,653,374 |
| `hall_of_heroes` | Hall of Heroes | 3x3 | 1 | 4 | 0.5 | 22d 10h 15m | 53,653,374 |
| `war_hall` | War Hall | 3x3 | 1 | 8 | 0.55 | 24d 16h 6m | 59,011,953 |
| `caravan_post` | Caravan Post | 2x2 | 1 | 9 | 0.4 | 17d 22h 32m | 42,936,640 |
<!-- /GEN:building_summary -->

Roles and stat columns (column name = YAML key):

| Building | What it does | Stat keys |
|---|---|---|
| `city_hall` | Gates every other building (their level ≤ CH). Grants march slots and base troops per march. To reach level `L ≥ 3` it requires `wall` at `L-1` and one rotating second building at `L-1` (see its table). | `march_slots`, `march_capacity` |
| `wall` | City durability and garrison defence (05 §9). Its 2×2 "gatehouse" is the clickable building; the perimeter wall mesh is cosmetic and scales with tier. Cannot be moved. | `wall_durability`, `garrison_defense_pct` (modifier, garrison only) |
| `farm`, `lumber_mill`, `quarry`, `goldmine` | Produce a resource into a per-building buffer (§6). | `production_per_hour`, `buffer_capacity` (= 10 h of production) |
| `storehouse` | Protects resources from looting (§7). | `protect_food`, `protect_wood`, `protect_stone`, `protect_gold` |
| `barracks`, `archery_range`, `stable`, `siege_workshop` | Train infantry / archers / cavalry / siege (02 §4). Level gates troop tiers. | `train_batch` (max troops per queue entry) |
| `hospital` | Holds severely wounded troops (02 §6). Capacities of all copies add up. | `hospital_capacity` |
| `academy` | Runs the single research queue; its level gates research node levels (03). | — |
| `scout_camp` | Scouts for fog exploration and scouting reports (06 §10). | `scouts` (count), `scout_speed` (tiles/min), `scout_range` (max tiles from city) |
| `watchtower` | Shoots attackers of the city (05 §9.3) and determines how much the owner sees about incoming marches. | `tower_potency`, `intel_tier` |
| `alliance_hall` | Required (level 1) to join or create an alliance. Limits helps per timer and how many reinforcing troops the city can host. | `help_limit`, `reinforcement_capacity` |
| `hall_of_heroes` | Commander management; daily sculpture allowance and commander XP bonus (04 §5). Replaces the "tavern": nothing here is random. | `daily_sculptures`, `commander_xp_pct` (modifier) |
| `war_hall` | Required to start rallies; total troops in a rally you lead (05 §8). | `rally_capacity` |
| `caravan_post` | Send resources to alliance members (07 §9). | `caravan_load` (per shipment), `caravan_tax_pct` |

Watchtower `intel_tier` (what the defender's incoming-march warning shows):

| Tier | Watchtower lv | Warning shows |
|---:|---:|---|
| 0 | not built | "Your city is under attack" only when the battle starts |
| 1 | 1–4 | Incoming march exists, its type (attack/rally/scout/reinforce) and arrival time |
| 2 | 5–9 | + sender name, alliance tag and origin coordinates |
| 3 | 10–14 | + commander ids and levels |
| 4 | 15–19 | + total troop count rounded to the nearest 1,000 |
| 5 | 20–25 | + exact troop composition; for rallies also every participant |

### 3.1 Per-level tables

Columns Food…Gold and Time are what it takes to **reach** the level.

<!-- GEN:building_tables -->
#### `city_hall` - City Hall

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | March slots | March capacity |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | - | - | - | - | - | - | 50 | 1 | 500 |
| 2 | 200 | 200 | - | - | 10s | - | 246 | 1 | 1,700 |
| 3 | 450 | 450 | - | - | 1m | wall 2, farm 2 | 626 | 1 | 3,500 |
| 4 | 1,000 | 1,000 | - | - | 5m | wall 3, barracks 3 | 1,213 | 1 | 5,800 |
| 5 | 1,800 | 1,800 | 900 | - | 15m | wall 4, storehouse 4 | 2,026 | 1 | 8,600 |
| 6 | 4,000 | 4,000 | 2,000 | - | 40m | wall 5, hospital 5 | 3,081 | 2 | 11,900 |
| 7 | 8,000 | 8,000 | 4,000 | - | 1h 30m | wall 6, academy 6 | 4,392 | 2 | 15,700 |
| 8 | 15,200 | 15,200 | 7,600 | - | 3h | wall 7, archery_range 7 | 5,971 | 2 | 19,800 |
| 9 | 27,200 | 27,200 | 13,600 | - | 5h | wall 8, scout_camp 8 | 7,829 | 2 | 24,400 |
| 10 | 48,000 | 48,000 | 24,000 | - | 8h | wall 9, alliance_hall 9 | 9,976 | 2 | 29,400 |
| 11 | 60,800 | 60,800 | 45,600 | 22,800 | 12h | wall 10, stable 10 | 12,421 | 3 | 34,900 |
| 12 | 92,800 | 92,800 | 69,600 | 34,800 | 17h | wall 11, storehouse 11 | 15,174 | 3 | 40,700 |
| 13 | 141,000 | 141,000 | 106,000 | 52,800 | 23h | wall 12, war_hall 12 | 18,241 | 3 | 46,800 |
| 14 | 218,000 | 218,000 | 163,000 | 81,600 | 1d 6h | wall 13, siege_workshop 13 | 21,630 | 3 | 53,400 |
| 15 | 336,000 | 336,000 | 252,000 | 126,000 | 1d 14h | wall 14, watchtower 14 | 25,350 | 3 | 60,300 |
| 16 | 480,000 | 480,000 | 360,000 | 180,000 | 1d 12h | wall 15, academy 15 | 29,407 | 3 | 67,600 |
| 17 | 672,000 | 672,000 | 504,000 | 252,000 | 1d 20h | wall 16, hospital 16 | 33,807 | 4 | 75,300 |
| 18 | 960,000 | 960,000 | 720,000 | 360,000 | 2d 4h | wall 17, caravan_post 17 | 38,556 | 4 | 83,300 |
| 19 | 1,340,000 | 1,340,000 | 1,010,000 | 504,000 | 2d 15h | wall 18, barracks 18 | 43,662 | 4 | 91,700 |
| 20 | 1,890,000 | 1,890,000 | 1,420,000 | 708,000 | 3d 4h | wall 19, hall_of_heroes 19 | 49,129 | 4 | 100,400 |
| 21 | 2,620,000 | 2,620,000 | 1,970,000 | 984,000 | 3d 18h | wall 20, storehouse 20 | 54,964 | 4 | 109,500 |
| 22 | 3,680,000 | 3,680,000 | 2,760,000 | 1,380,000 | 4d 12h | wall 21, alliance_hall 21 | 61,171 | 5 | 118,900 |
| 23 | 5,120,000 | 5,120,000 | 3,840,000 | 1,920,000 | 5d 10h | wall 22, war_hall 22 | 67,755 | 5 | 128,600 |
| 24 | 7,040,000 | 7,040,000 | 5,280,000 | 2,640,000 | 6d 11h | wall 23, academy 23 | 74,723 | 5 | 138,700 |
| 25 | 9,600,000 | 9,600,000 | 7,200,000 | 3,600,000 | 7d 16h | wall 24, watchtower 24 | 82,079 | 5 | 149,000 |

#### `wall` - City Wall

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Durability | Garrison def % |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 45 | 45 | - | - | 3s | city_hall 1 | 30 | 5,000 | 0.4 |
| 2 | 120 | 120 | - | - | 6s | city_hall 2 | 148 | 14,000 | 0.8 |
| 3 | 270 | 270 | - | - | 36s | city_hall 3 | 375 | 26,000 | 1.2 |
| 4 | 600 | 600 | - | - | 3m | city_hall 4 | 728 | 40,000 | 1.6 |
| 5 | 540 | 1,080 | 1,080 | - | 9m | city_hall 5 | 1,215 | 56,000 | 2.0 |
| 6 | 1,200 | 2,400 | 2,400 | - | 24m | city_hall 6 | 1,849 | 73,500 | 2.4 |
| 7 | 2,400 | 4,800 | 4,800 | - | 54m | city_hall 7 | 2,635 | 92,500 | 2.8 |
| 8 | 4,560 | 9,120 | 9,120 | - | 1h 48m | city_hall 8 | 3,583 | 113,000 | 3.2 |
| 9 | 8,160 | 16,300 | 16,300 | - | 3h | city_hall 9 | 4,698 | 135,000 | 3.6 |
| 10 | 14,400 | 28,800 | 28,800 | - | 4h 48m | city_hall 10 | 5,986 | 158,000 | 4.0 |
| 11 | 18,200 | 36,500 | 45,600 | 13,700 | 7h 10m | city_hall 11 | 7,453 | 182,500 | 4.4 |
| 12 | 27,800 | 55,700 | 69,600 | 20,900 | 10h 10m | city_hall 12 | 9,104 | 208,000 | 4.8 |
| 13 | 42,200 | 84,500 | 106,000 | 31,700 | 13h 50m | city_hall 13 | 10,944 | 234,500 | 5.2 |
| 14 | 65,300 | 131,000 | 163,000 | 49,000 | 18h | city_hall 14 | 12,978 | 262,000 | 5.6 |
| 15 | 101,000 | 202,000 | 252,000 | 75,600 | 22h 50m | city_hall 15 | 15,210 | 290,500 | 6.0 |
| 16 | 144,000 | 288,000 | 360,000 | 108,000 | 21h 35m | city_hall 16 | 17,644 | 320,000 | 6.4 |
| 17 | 202,000 | 403,000 | 504,000 | 151,000 | 1d 2h 25m | city_hall 17 | 20,284 | 350,500 | 6.8 |
| 18 | 288,000 | 576,000 | 720,000 | 216,000 | 1d 7h 10m | city_hall 18 | 23,134 | 382,000 | 7.2 |
| 19 | 403,000 | 806,000 | 1,010,000 | 302,000 | 1d 13h 50m | city_hall 19 | 26,197 | 414,000 | 7.6 |
| 20 | 566,000 | 1,130,000 | 1,420,000 | 425,000 | 1d 21h 35m | city_hall 20 | 29,477 | 447,000 | 8.0 |
| 21 | 787,000 | 1,570,000 | 1,970,000 | 590,000 | 2d 6h | city_hall 21 | 32,978 | 481,000 | 8.4 |
| 22 | 1,100,000 | 2,210,000 | 2,760,000 | 828,000 | 2d 16h 50m | city_hall 22 | 36,702 | 516,000 | 8.8 |
| 23 | 1,540,000 | 3,070,000 | 3,840,000 | 1,150,000 | 3d 6h | city_hall 23 | 40,653 | 551,500 | 9.2 |
| 24 | 2,110,000 | 4,220,000 | 5,280,000 | 1,580,000 | 3d 21h | city_hall 24 | 44,834 | 588,000 | 9.6 |
| 25 | 2,880,000 | 5,760,000 | 7,200,000 | 2,160,000 | 4d 14h 25m | city_hall 25 | 49,247 | 625,000 | 10.0 |

#### `farm` - Farm

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Production/h | Buffer |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | - | 30 | - | - | 1s | city_hall 1 | 10 | 360 | 3,600 |
| 2 | - | 80 | - | - | 2s | city_hall 2 | 49 | 520 | 5,200 |
| 3 | - | 180 | - | - | 12s | city_hall 3 | 125 | 780 | 7,800 |
| 4 | - | 400 | - | - | 1m | city_hall 4 | 243 | 1,140 | 11,400 |
| 5 | - | 720 | 180 | - | 3m | city_hall 5 | 405 | 1,580 | 15,800 |
| 6 | - | 1,600 | 400 | - | 8m | city_hall 6 | 616 | 2,110 | 21,100 |
| 7 | - | 3,200 | 800 | - | 18m | city_hall 7 | 878 | 2,720 | 27,200 |
| 8 | - | 6,080 | 1,520 | - | 36m | city_hall 8 | 1,194 | 3,420 | 34,200 |
| 9 | - | 10,900 | 2,720 | - | 1h | city_hall 9 | 1,566 | 4,200 | 42,000 |
| 10 | - | 19,200 | 4,800 | - | 1h 36m | city_hall 10 | 1,995 | 5,070 | 50,700 |
| 11 | - | 24,300 | 9,120 | 4,560 | 2h 24m | city_hall 11 | 2,484 | 6,010 | 60,100 |
| 12 | - | 37,100 | 13,900 | 6,960 | 3h 24m | city_hall 12 | 3,035 | 7,040 | 70,400 |
| 13 | - | 56,300 | 21,100 | 10,600 | 4h 36m | city_hall 13 | 3,648 | 8,150 | 81,500 |
| 14 | - | 87,000 | 32,600 | 16,300 | 6h | city_hall 14 | 4,326 | 9,330 | 93,300 |
| 15 | - | 134,000 | 50,400 | 25,200 | 7h 35m | city_hall 15 | 5,070 | 10,600 | 106,000 |
| 16 | - | 192,000 | 72,000 | 36,000 | 7h 10m | city_hall 16 | 5,881 | 11,940 | 119,400 |
| 17 | - | 269,000 | 101,000 | 50,400 | 8h 50m | city_hall 17 | 6,761 | 13,360 | 133,600 |
| 18 | - | 384,000 | 144,000 | 72,000 | 10h 25m | city_hall 18 | 7,711 | 14,860 | 148,600 |
| 19 | - | 538,000 | 202,000 | 101,000 | 12h 35m | city_hall 19 | 8,732 | 16,440 | 164,400 |
| 20 | - | 755,000 | 283,000 | 142,000 | 15h 10m | city_hall 20 | 9,826 | 18,090 | 180,900 |
| 21 | - | 1,050,000 | 394,000 | 197,000 | 18h | city_hall 21 | 10,993 | 19,810 | 198,100 |
| 22 | - | 1,470,000 | 552,000 | 276,000 | 21h 35m | city_hall 22 | 12,234 | 21,620 | 216,200 |
| 23 | - | 2,050,000 | 768,000 | 384,000 | 1d 2h | city_hall 23 | 13,551 | 23,500 | 235,000 |
| 24 | - | 2,820,000 | 1,060,000 | 528,000 | 1d 7h | city_hall 24 | 14,945 | 25,450 | 254,500 |
| 25 | - | 3,840,000 | 1,440,000 | 720,000 | 1d 12h 50m | city_hall 25 | 16,416 | 27,480 | 274,800 |

#### `lumber_mill` - Lumber Mill

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Production/h | Buffer |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 30 | - | - | - | 1s | city_hall 1 | 10 | 360 | 3,600 |
| 2 | 80 | - | - | - | 2s | city_hall 2 | 49 | 520 | 5,200 |
| 3 | 180 | - | - | - | 12s | city_hall 3 | 125 | 780 | 7,800 |
| 4 | 400 | - | - | - | 1m | city_hall 4 | 243 | 1,140 | 11,400 |
| 5 | 720 | - | 180 | - | 3m | city_hall 5 | 405 | 1,580 | 15,800 |
| 6 | 1,600 | - | 400 | - | 8m | city_hall 6 | 616 | 2,110 | 21,100 |
| 7 | 3,200 | - | 800 | - | 18m | city_hall 7 | 878 | 2,720 | 27,200 |
| 8 | 6,080 | - | 1,520 | - | 36m | city_hall 8 | 1,194 | 3,420 | 34,200 |
| 9 | 10,900 | - | 2,720 | - | 1h | city_hall 9 | 1,566 | 4,200 | 42,000 |
| 10 | 19,200 | - | 4,800 | - | 1h 36m | city_hall 10 | 1,995 | 5,070 | 50,700 |
| 11 | 24,300 | - | 9,120 | 4,560 | 2h 24m | city_hall 11 | 2,484 | 6,010 | 60,100 |
| 12 | 37,100 | - | 13,900 | 6,960 | 3h 24m | city_hall 12 | 3,035 | 7,040 | 70,400 |
| 13 | 56,300 | - | 21,100 | 10,600 | 4h 36m | city_hall 13 | 3,648 | 8,150 | 81,500 |
| 14 | 87,000 | - | 32,600 | 16,300 | 6h | city_hall 14 | 4,326 | 9,330 | 93,300 |
| 15 | 134,000 | - | 50,400 | 25,200 | 7h 35m | city_hall 15 | 5,070 | 10,600 | 106,000 |
| 16 | 192,000 | - | 72,000 | 36,000 | 7h 10m | city_hall 16 | 5,881 | 11,940 | 119,400 |
| 17 | 269,000 | - | 101,000 | 50,400 | 8h 50m | city_hall 17 | 6,761 | 13,360 | 133,600 |
| 18 | 384,000 | - | 144,000 | 72,000 | 10h 25m | city_hall 18 | 7,711 | 14,860 | 148,600 |
| 19 | 538,000 | - | 202,000 | 101,000 | 12h 35m | city_hall 19 | 8,732 | 16,440 | 164,400 |
| 20 | 755,000 | - | 283,000 | 142,000 | 15h 10m | city_hall 20 | 9,826 | 18,090 | 180,900 |
| 21 | 1,050,000 | - | 394,000 | 197,000 | 18h | city_hall 21 | 10,993 | 19,810 | 198,100 |
| 22 | 1,470,000 | - | 552,000 | 276,000 | 21h 35m | city_hall 22 | 12,234 | 21,620 | 216,200 |
| 23 | 2,050,000 | - | 768,000 | 384,000 | 1d 2h | city_hall 23 | 13,551 | 23,500 | 235,000 |
| 24 | 2,820,000 | - | 1,060,000 | 528,000 | 1d 7h | city_hall 24 | 14,945 | 25,450 | 254,500 |
| 25 | 3,840,000 | - | 1,440,000 | 720,000 | 1d 12h 50m | city_hall 25 | 16,416 | 27,480 | 274,800 |

#### `quarry` - Quarry

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Production/h | Buffer |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 15 | 15 | - | - | 1s | city_hall 4 | 10 | 270 | 2,700 |
| 2 | 40 | 40 | - | - | 2s | city_hall 4 | 49 | 390 | 3,900 |
| 3 | 90 | 90 | - | - | 12s | city_hall 4 | 125 | 590 | 5,900 |
| 4 | 200 | 200 | - | - | 1m | city_hall 4 | 243 | 850 | 8,500 |
| 5 | 360 | 360 | 180 | - | 3m | city_hall 5 | 405 | 1,180 | 11,800 |
| 6 | 800 | 800 | 400 | - | 8m | city_hall 6 | 616 | 1,580 | 15,800 |
| 7 | 1,600 | 1,600 | 800 | - | 18m | city_hall 7 | 878 | 2,040 | 20,400 |
| 8 | 3,040 | 3,040 | 1,520 | - | 36m | city_hall 8 | 1,194 | 2,560 | 25,600 |
| 9 | 5,440 | 5,440 | 2,720 | - | 1h | city_hall 9 | 1,566 | 3,150 | 31,500 |
| 10 | 9,600 | 9,600 | 4,800 | - | 1h 36m | city_hall 10 | 1,995 | 3,800 | 38,000 |
| 11 | 12,200 | 12,200 | 9,120 | 4,560 | 2h 24m | city_hall 11 | 2,484 | 4,510 | 45,100 |
| 12 | 18,600 | 18,600 | 13,900 | 6,960 | 3h 24m | city_hall 12 | 3,035 | 5,280 | 52,800 |
| 13 | 28,200 | 28,200 | 21,100 | 10,600 | 4h 36m | city_hall 13 | 3,648 | 6,110 | 61,100 |
| 14 | 43,500 | 43,500 | 32,600 | 16,300 | 6h | city_hall 14 | 4,326 | 7,000 | 70,000 |
| 15 | 67,200 | 67,200 | 50,400 | 25,200 | 7h 35m | city_hall 15 | 5,070 | 7,950 | 79,500 |
| 16 | 96,000 | 96,000 | 72,000 | 36,000 | 7h 10m | city_hall 16 | 5,881 | 8,960 | 89,600 |
| 17 | 134,000 | 134,000 | 101,000 | 50,400 | 8h 50m | city_hall 17 | 6,761 | 10,020 | 100,200 |
| 18 | 192,000 | 192,000 | 144,000 | 72,000 | 10h 25m | city_hall 18 | 7,711 | 11,150 | 111,500 |
| 19 | 269,000 | 269,000 | 202,000 | 101,000 | 12h 35m | city_hall 19 | 8,732 | 12,330 | 123,300 |
| 20 | 378,000 | 378,000 | 283,000 | 142,000 | 15h 10m | city_hall 20 | 9,826 | 13,570 | 135,700 |
| 21 | 525,000 | 525,000 | 394,000 | 197,000 | 18h | city_hall 21 | 10,993 | 14,860 | 148,600 |
| 22 | 736,000 | 736,000 | 552,000 | 276,000 | 21h 35m | city_hall 22 | 12,234 | 16,210 | 162,100 |
| 23 | 1,020,000 | 1,020,000 | 768,000 | 384,000 | 1d 2h | city_hall 23 | 13,551 | 17,620 | 176,200 |
| 24 | 1,410,000 | 1,410,000 | 1,060,000 | 528,000 | 1d 7h | city_hall 24 | 14,945 | 19,090 | 190,900 |
| 25 | 1,920,000 | 1,920,000 | 1,440,000 | 720,000 | 1d 12h 50m | city_hall 25 | 16,416 | 20,610 | 206,100 |

#### `goldmine` - Goldmine

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Production/h | Buffer |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 15 | 15 | - | - | 1s | city_hall 10 | 10 | 180 | 1,800 |
| 2 | 40 | 40 | - | - | 2s | city_hall 10 | 49 | 260 | 2,600 |
| 3 | 90 | 90 | - | - | 12s | city_hall 10 | 125 | 390 | 3,900 |
| 4 | 200 | 200 | - | - | 1m | city_hall 10 | 243 | 570 | 5,700 |
| 5 | 360 | 360 | 180 | - | 3m | city_hall 10 | 405 | 790 | 7,900 |
| 6 | 800 | 800 | 400 | - | 8m | city_hall 10 | 616 | 1,050 | 10,500 |
| 7 | 1,600 | 1,600 | 800 | - | 18m | city_hall 10 | 878 | 1,360 | 13,600 |
| 8 | 3,040 | 3,040 | 1,520 | - | 36m | city_hall 10 | 1,194 | 1,710 | 17,100 |
| 9 | 5,440 | 5,440 | 2,720 | - | 1h | city_hall 10 | 1,566 | 2,100 | 21,000 |
| 10 | 9,600 | 9,600 | 4,800 | - | 1h 36m | city_hall 10 | 1,995 | 2,530 | 25,300 |
| 11 | 14,400 | 14,400 | 9,120 | - | 2h 24m | city_hall 11 | 2,484 | 3,010 | 30,100 |
| 12 | 22,000 | 22,000 | 13,900 | - | 3h 24m | city_hall 12 | 3,035 | 3,520 | 35,200 |
| 13 | 33,400 | 33,400 | 21,100 | - | 4h 36m | city_hall 13 | 3,648 | 4,070 | 40,700 |
| 14 | 51,700 | 51,700 | 32,600 | - | 6h | city_hall 14 | 4,326 | 4,670 | 46,700 |
| 15 | 79,800 | 79,800 | 50,400 | - | 7h 35m | city_hall 15 | 5,070 | 5,300 | 53,000 |
| 16 | 114,000 | 114,000 | 72,000 | - | 7h 10m | city_hall 16 | 5,881 | 5,970 | 59,700 |
| 17 | 160,000 | 160,000 | 101,000 | - | 8h 50m | city_hall 17 | 6,761 | 6,680 | 66,800 |
| 18 | 228,000 | 228,000 | 144,000 | - | 10h 25m | city_hall 18 | 7,711 | 7,430 | 74,300 |
| 19 | 319,000 | 319,000 | 202,000 | - | 12h 35m | city_hall 19 | 8,732 | 8,220 | 82,200 |
| 20 | 448,000 | 448,000 | 283,000 | - | 15h 10m | city_hall 20 | 9,826 | 9,040 | 90,400 |
| 21 | 623,000 | 623,000 | 394,000 | - | 18h | city_hall 21 | 10,993 | 9,910 | 99,100 |
| 22 | 874,000 | 874,000 | 552,000 | - | 21h 35m | city_hall 22 | 12,234 | 10,810 | 108,100 |
| 23 | 1,220,000 | 1,220,000 | 768,000 | - | 1d 2h | city_hall 23 | 13,551 | 11,750 | 117,500 |
| 24 | 1,670,000 | 1,670,000 | 1,060,000 | - | 1d 7h | city_hall 24 | 14,945 | 12,730 | 127,300 |
| 25 | 2,280,000 | 2,280,000 | 1,440,000 | - | 1d 12h 50m | city_hall 25 | 16,416 | 13,740 | 137,400 |

#### `storehouse` - Storehouse

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Protect food | Protect wood | Protect stone | Protect gold |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 30 | 30 | - | - | 2s | city_hall 2 | 20 | 2,000 | 2,000 | 1,500 | 1,000 |
| 2 | 80 | 80 | - | - | 4s | city_hall 2 | 98 | 9,200 | 9,200 | 6,900 | 4,600 |
| 3 | 180 | 180 | - | - | 24s | city_hall 3 | 250 | 22,400 | 22,400 | 16,800 | 11,200 |
| 4 | 400 | 400 | - | - | 2m | city_hall 4 | 485 | 42,200 | 42,200 | 31,600 | 21,100 |
| 5 | 720 | 720 | 360 | - | 6m | city_hall 5 | 810 | 69,000 | 69,000 | 51,800 | 34,500 |
| 6 | 1,600 | 1,600 | 800 | - | 16m | city_hall 6 | 1,232 | 103,000 | 103,000 | 77,200 | 51,500 |
| 7 | 3,200 | 3,200 | 1,600 | - | 36m | city_hall 7 | 1,757 | 144,600 | 144,600 | 108,400 | 72,300 |
| 8 | 6,080 | 6,080 | 3,040 | - | 1h 12m | city_hall 8 | 2,389 | 194,000 | 194,000 | 145,500 | 97,000 |
| 9 | 10,900 | 10,900 | 5,440 | - | 2h | city_hall 9 | 3,132 | 251,400 | 251,400 | 188,600 | 125,700 |
| 10 | 19,200 | 19,200 | 9,600 | - | 3h 12m | city_hall 10 | 3,991 | 317,000 | 317,000 | 237,800 | 158,500 |
| 11 | 24,300 | 24,300 | 18,200 | 9,120 | 4h 48m | city_hall 11 | 4,969 | 390,900 | 390,900 | 293,200 | 195,400 |
| 12 | 37,100 | 37,100 | 27,800 | 13,900 | 6h 50m | city_hall 12 | 6,069 | 473,400 | 473,400 | 355,000 | 236,700 |
| 13 | 56,300 | 56,300 | 42,200 | 21,100 | 9h 10m | city_hall 13 | 7,296 | 564,600 | 564,600 | 423,400 | 282,300 |
| 14 | 87,000 | 87,000 | 65,300 | 32,600 | 12h | city_hall 14 | 8,652 | 664,500 | 664,500 | 498,400 | 332,200 |
| 15 | 134,000 | 134,000 | 101,000 | 50,400 | 15h 10m | city_hall 15 | 10,140 | 773,400 | 773,400 | 580,000 | 386,700 |
| 16 | 192,000 | 192,000 | 144,000 | 72,000 | 14h 25m | city_hall 16 | 11,763 | 891,400 | 891,400 | 668,600 | 445,700 |
| 17 | 269,000 | 269,000 | 202,000 | 101,000 | 17h 35m | city_hall 17 | 13,523 | 1,018,600 | 1,018,600 | 764,000 | 509,300 |
| 18 | 384,000 | 384,000 | 288,000 | 144,000 | 20h 50m | city_hall 18 | 15,423 | 1,155,100 | 1,155,100 | 866,300 | 577,600 |
| 19 | 538,000 | 538,000 | 403,000 | 202,000 | 1d 1h 10m | city_hall 19 | 17,465 | 1,301,000 | 1,301,000 | 975,800 | 650,500 |
| 20 | 755,000 | 755,000 | 566,000 | 283,000 | 1d 6h 25m | city_hall 20 | 19,652 | 1,456,500 | 1,456,500 | 1,092,400 | 728,200 |
| 21 | 1,050,000 | 1,050,000 | 787,000 | 394,000 | 1d 12h | city_hall 21 | 21,985 | 1,621,500 | 1,621,500 | 1,216,100 | 810,800 |
| 22 | 1,470,000 | 1,470,000 | 1,100,000 | 552,000 | 1d 19h 10m | city_hall 22 | 24,468 | 1,796,200 | 1,796,200 | 1,347,200 | 898,100 |
| 23 | 2,050,000 | 2,050,000 | 1,540,000 | 768,000 | 2d 4h | city_hall 23 | 27,102 | 1,980,800 | 1,980,800 | 1,485,600 | 990,400 |
| 24 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 14h | city_hall 24 | 29,889 | 2,175,200 | 2,175,200 | 1,631,400 | 1,087,600 |
| 25 | 3,840,000 | 3,840,000 | 2,880,000 | 1,440,000 | 3d 1h 35m | city_hall 25 | 32,832 | 2,379,600 | 2,379,600 | 1,784,700 | 1,189,800 |

#### `barracks` - Barracks

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Train batch |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 41 | 41 | - | - | 3s | city_hall 1 | 28 | 50 |
| 2 | 110 | 110 | - | - | 6s | city_hall 2 | 135 | 140 |
| 3 | 248 | 248 | - | - | 33s | city_hall 3 | 344 | 250 |
| 4 | 550 | 550 | - | - | 2m 45s | city_hall 4 | 667 | 370 |
| 5 | 990 | 990 | 495 | - | 8m 15s | city_hall 5 | 1,114 | 520 |
| 6 | 2,200 | 2,200 | 1,100 | - | 22m | city_hall 6 | 1,695 | 670 |
| 7 | 4,400 | 4,400 | 2,200 | - | 50m | city_hall 7 | 2,416 | 840 |
| 8 | 8,360 | 8,360 | 4,180 | - | 1h 39m | city_hall 8 | 3,284 | 1,020 |
| 9 | 15,000 | 15,000 | 7,480 | - | 2h 45m | city_hall 9 | 4,306 | 1,210 |
| 10 | 26,400 | 26,400 | 13,200 | - | 4h 24m | city_hall 10 | 5,487 | 1,410 |
| 11 | 33,400 | 33,400 | 25,100 | 12,500 | 6h 35m | city_hall 11 | 6,832 | 1,620 |
| 12 | 51,000 | 51,000 | 38,300 | 19,100 | 9h 20m | city_hall 12 | 8,345 | 1,840 |
| 13 | 77,400 | 77,400 | 58,100 | 29,000 | 12h 40m | city_hall 13 | 10,032 | 2,060 |
| 14 | 120,000 | 120,000 | 89,800 | 44,900 | 16h 30m | city_hall 14 | 11,897 | 2,300 |
| 15 | 185,000 | 185,000 | 139,000 | 69,300 | 20h 55m | city_hall 15 | 13,943 | 2,540 |
| 16 | 264,000 | 264,000 | 198,000 | 99,000 | 19h 50m | city_hall 16 | 16,174 | 2,790 |
| 17 | 370,000 | 370,000 | 277,000 | 139,000 | 1d 10m | city_hall 17 | 18,594 | 3,040 |
| 18 | 528,000 | 528,000 | 396,000 | 198,000 | 1d 4h 35m | city_hall 18 | 21,206 | 3,300 |
| 19 | 739,000 | 739,000 | 554,000 | 277,000 | 1d 10h 40m | city_hall 19 | 24,014 | 3,570 |
| 20 | 1,040,000 | 1,040,000 | 779,000 | 389,000 | 1d 17h 50m | city_hall 20 | 27,021 | 3,850 |
| 21 | 1,440,000 | 1,440,000 | 1,080,000 | 541,000 | 2d 1h 30m | city_hall 21 | 30,230 | 4,130 |
| 22 | 2,020,000 | 2,020,000 | 1,520,000 | 759,000 | 2d 11h 25m | city_hall 22 | 33,644 | 4,420 |
| 23 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 23h 30m | city_hall 23 | 37,265 | 4,710 |
| 24 | 3,870,000 | 3,870,000 | 2,900,000 | 1,450,000 | 3d 13h 15m | city_hall 24 | 41,098 | 5,020 |
| 25 | 5,280,000 | 5,280,000 | 3,960,000 | 1,980,000 | 4d 5h 10m | city_hall 25 | 45,143 | 5,320 |

#### `archery_range` - Archery Range

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Train batch |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 41 | 41 | - | - | 3s | city_hall 3 | 28 | 50 |
| 2 | 110 | 110 | - | - | 6s | city_hall 3 | 135 | 140 |
| 3 | 248 | 248 | - | - | 33s | city_hall 3 | 344 | 250 |
| 4 | 550 | 550 | - | - | 2m 45s | city_hall 4 | 667 | 370 |
| 5 | 990 | 990 | 495 | - | 8m 15s | city_hall 5 | 1,114 | 520 |
| 6 | 2,200 | 2,200 | 1,100 | - | 22m | city_hall 6 | 1,695 | 670 |
| 7 | 4,400 | 4,400 | 2,200 | - | 50m | city_hall 7 | 2,416 | 840 |
| 8 | 8,360 | 8,360 | 4,180 | - | 1h 39m | city_hall 8 | 3,284 | 1,020 |
| 9 | 15,000 | 15,000 | 7,480 | - | 2h 45m | city_hall 9 | 4,306 | 1,210 |
| 10 | 26,400 | 26,400 | 13,200 | - | 4h 24m | city_hall 10 | 5,487 | 1,410 |
| 11 | 33,400 | 33,400 | 25,100 | 12,500 | 6h 35m | city_hall 11 | 6,832 | 1,620 |
| 12 | 51,000 | 51,000 | 38,300 | 19,100 | 9h 20m | city_hall 12 | 8,345 | 1,840 |
| 13 | 77,400 | 77,400 | 58,100 | 29,000 | 12h 40m | city_hall 13 | 10,032 | 2,060 |
| 14 | 120,000 | 120,000 | 89,800 | 44,900 | 16h 30m | city_hall 14 | 11,897 | 2,300 |
| 15 | 185,000 | 185,000 | 139,000 | 69,300 | 20h 55m | city_hall 15 | 13,943 | 2,540 |
| 16 | 264,000 | 264,000 | 198,000 | 99,000 | 19h 50m | city_hall 16 | 16,174 | 2,790 |
| 17 | 370,000 | 370,000 | 277,000 | 139,000 | 1d 10m | city_hall 17 | 18,594 | 3,040 |
| 18 | 528,000 | 528,000 | 396,000 | 198,000 | 1d 4h 35m | city_hall 18 | 21,206 | 3,300 |
| 19 | 739,000 | 739,000 | 554,000 | 277,000 | 1d 10h 40m | city_hall 19 | 24,014 | 3,570 |
| 20 | 1,040,000 | 1,040,000 | 779,000 | 389,000 | 1d 17h 50m | city_hall 20 | 27,021 | 3,850 |
| 21 | 1,440,000 | 1,440,000 | 1,080,000 | 541,000 | 2d 1h 30m | city_hall 21 | 30,230 | 4,130 |
| 22 | 2,020,000 | 2,020,000 | 1,520,000 | 759,000 | 2d 11h 25m | city_hall 22 | 33,644 | 4,420 |
| 23 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 23h 30m | city_hall 23 | 37,265 | 4,710 |
| 24 | 3,870,000 | 3,870,000 | 2,900,000 | 1,450,000 | 3d 13h 15m | city_hall 24 | 41,098 | 5,020 |
| 25 | 5,280,000 | 5,280,000 | 3,960,000 | 1,980,000 | 4d 5h 10m | city_hall 25 | 45,143 | 5,320 |

#### `stable` - Stable

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Train batch |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 41 | 41 | - | - | 3s | city_hall 5 | 28 | 50 |
| 2 | 110 | 110 | - | - | 6s | city_hall 5 | 135 | 140 |
| 3 | 248 | 248 | - | - | 33s | city_hall 5 | 344 | 250 |
| 4 | 550 | 550 | - | - | 2m 45s | city_hall 5 | 667 | 370 |
| 5 | 990 | 990 | 495 | - | 8m 15s | city_hall 5 | 1,114 | 520 |
| 6 | 2,200 | 2,200 | 1,100 | - | 22m | city_hall 6 | 1,695 | 670 |
| 7 | 4,400 | 4,400 | 2,200 | - | 50m | city_hall 7 | 2,416 | 840 |
| 8 | 8,360 | 8,360 | 4,180 | - | 1h 39m | city_hall 8 | 3,284 | 1,020 |
| 9 | 15,000 | 15,000 | 7,480 | - | 2h 45m | city_hall 9 | 4,306 | 1,210 |
| 10 | 26,400 | 26,400 | 13,200 | - | 4h 24m | city_hall 10 | 5,487 | 1,410 |
| 11 | 33,400 | 33,400 | 25,100 | 12,500 | 6h 35m | city_hall 11 | 6,832 | 1,620 |
| 12 | 51,000 | 51,000 | 38,300 | 19,100 | 9h 20m | city_hall 12 | 8,345 | 1,840 |
| 13 | 77,400 | 77,400 | 58,100 | 29,000 | 12h 40m | city_hall 13 | 10,032 | 2,060 |
| 14 | 120,000 | 120,000 | 89,800 | 44,900 | 16h 30m | city_hall 14 | 11,897 | 2,300 |
| 15 | 185,000 | 185,000 | 139,000 | 69,300 | 20h 55m | city_hall 15 | 13,943 | 2,540 |
| 16 | 264,000 | 264,000 | 198,000 | 99,000 | 19h 50m | city_hall 16 | 16,174 | 2,790 |
| 17 | 370,000 | 370,000 | 277,000 | 139,000 | 1d 10m | city_hall 17 | 18,594 | 3,040 |
| 18 | 528,000 | 528,000 | 396,000 | 198,000 | 1d 4h 35m | city_hall 18 | 21,206 | 3,300 |
| 19 | 739,000 | 739,000 | 554,000 | 277,000 | 1d 10h 40m | city_hall 19 | 24,014 | 3,570 |
| 20 | 1,040,000 | 1,040,000 | 779,000 | 389,000 | 1d 17h 50m | city_hall 20 | 27,021 | 3,850 |
| 21 | 1,440,000 | 1,440,000 | 1,080,000 | 541,000 | 2d 1h 30m | city_hall 21 | 30,230 | 4,130 |
| 22 | 2,020,000 | 2,020,000 | 1,520,000 | 759,000 | 2d 11h 25m | city_hall 22 | 33,644 | 4,420 |
| 23 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 23h 30m | city_hall 23 | 37,265 | 4,710 |
| 24 | 3,870,000 | 3,870,000 | 2,900,000 | 1,450,000 | 3d 13h 15m | city_hall 24 | 41,098 | 5,020 |
| 25 | 5,280,000 | 5,280,000 | 3,960,000 | 1,980,000 | 4d 5h 10m | city_hall 25 | 45,143 | 5,320 |

#### `siege_workshop` - Siege Workshop

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Train batch |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 41 | 41 | - | - | 3s | city_hall 7 | 28 | 50 |
| 2 | 110 | 110 | - | - | 6s | city_hall 7 | 135 | 140 |
| 3 | 248 | 248 | - | - | 33s | city_hall 7 | 344 | 250 |
| 4 | 550 | 550 | - | - | 2m 45s | city_hall 7 | 667 | 370 |
| 5 | 990 | 990 | 495 | - | 8m 15s | city_hall 7 | 1,114 | 520 |
| 6 | 2,200 | 2,200 | 1,100 | - | 22m | city_hall 7 | 1,695 | 670 |
| 7 | 4,400 | 4,400 | 2,200 | - | 50m | city_hall 7 | 2,416 | 840 |
| 8 | 8,360 | 8,360 | 4,180 | - | 1h 39m | city_hall 8 | 3,284 | 1,020 |
| 9 | 15,000 | 15,000 | 7,480 | - | 2h 45m | city_hall 9 | 4,306 | 1,210 |
| 10 | 26,400 | 26,400 | 13,200 | - | 4h 24m | city_hall 10 | 5,487 | 1,410 |
| 11 | 33,400 | 33,400 | 25,100 | 12,500 | 6h 35m | city_hall 11 | 6,832 | 1,620 |
| 12 | 51,000 | 51,000 | 38,300 | 19,100 | 9h 20m | city_hall 12 | 8,345 | 1,840 |
| 13 | 77,400 | 77,400 | 58,100 | 29,000 | 12h 40m | city_hall 13 | 10,032 | 2,060 |
| 14 | 120,000 | 120,000 | 89,800 | 44,900 | 16h 30m | city_hall 14 | 11,897 | 2,300 |
| 15 | 185,000 | 185,000 | 139,000 | 69,300 | 20h 55m | city_hall 15 | 13,943 | 2,540 |
| 16 | 264,000 | 264,000 | 198,000 | 99,000 | 19h 50m | city_hall 16 | 16,174 | 2,790 |
| 17 | 370,000 | 370,000 | 277,000 | 139,000 | 1d 10m | city_hall 17 | 18,594 | 3,040 |
| 18 | 528,000 | 528,000 | 396,000 | 198,000 | 1d 4h 35m | city_hall 18 | 21,206 | 3,300 |
| 19 | 739,000 | 739,000 | 554,000 | 277,000 | 1d 10h 40m | city_hall 19 | 24,014 | 3,570 |
| 20 | 1,040,000 | 1,040,000 | 779,000 | 389,000 | 1d 17h 50m | city_hall 20 | 27,021 | 3,850 |
| 21 | 1,440,000 | 1,440,000 | 1,080,000 | 541,000 | 2d 1h 30m | city_hall 21 | 30,230 | 4,130 |
| 22 | 2,020,000 | 2,020,000 | 1,520,000 | 759,000 | 2d 11h 25m | city_hall 22 | 33,644 | 4,420 |
| 23 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 23h 30m | city_hall 23 | 37,265 | 4,710 |
| 24 | 3,870,000 | 3,870,000 | 2,900,000 | 1,450,000 | 3d 13h 15m | city_hall 24 | 41,098 | 5,020 |
| 25 | 5,280,000 | 5,280,000 | 3,960,000 | 1,980,000 | 4d 5h 10m | city_hall 25 | 45,143 | 5,320 |

#### `hospital` - Hospital

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Capacity |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 22 | 22 | - | - | 2s | city_hall 2 | 15 | 150 |
| 2 | 60 | 60 | - | - | 3s | city_hall 2 | 74 | 450 |
| 3 | 135 | 135 | - | - | 18s | city_hall 3 | 188 | 900 |
| 4 | 300 | 300 | - | - | 1m 30s | city_hall 4 | 364 | 1,500 |
| 5 | 540 | 540 | 270 | - | 4m 30s | city_hall 5 | 608 | 2,150 |
| 6 | 1,200 | 1,200 | 600 | - | 12m | city_hall 6 | 924 | 2,900 |
| 7 | 2,400 | 2,400 | 1,200 | - | 27m | city_hall 7 | 1,318 | 3,700 |
| 8 | 4,560 | 4,560 | 2,280 | - | 54m | city_hall 8 | 1,791 | 4,650 |
| 9 | 8,160 | 8,160 | 4,080 | - | 1h 30m | city_hall 9 | 2,349 | 5,650 |
| 10 | 14,400 | 14,400 | 7,200 | - | 2h 24m | city_hall 10 | 2,993 | 6,700 |
| 11 | 18,200 | 18,200 | 13,700 | 6,840 | 3h 36m | city_hall 11 | 3,726 | 7,850 |
| 12 | 27,800 | 27,800 | 20,900 | 10,400 | 5h 6m | city_hall 12 | 4,552 | 9,050 |
| 13 | 42,200 | 42,200 | 31,700 | 15,800 | 6h 55m | city_hall 13 | 5,472 | 10,350 |
| 14 | 65,300 | 65,300 | 49,000 | 24,500 | 9h | city_hall 14 | 6,489 | 11,650 |
| 15 | 101,000 | 101,000 | 75,600 | 37,800 | 11h 25m | city_hall 15 | 7,605 | 13,100 |
| 16 | 144,000 | 144,000 | 108,000 | 54,000 | 10h 50m | city_hall 16 | 8,822 | 14,550 |
| 17 | 202,000 | 202,000 | 151,000 | 75,600 | 13h 10m | city_hall 17 | 10,142 | 16,100 |
| 18 | 288,000 | 288,000 | 216,000 | 108,000 | 15h 35m | city_hall 18 | 11,567 | 17,650 |
| 19 | 403,000 | 403,000 | 302,000 | 151,000 | 18h 55m | city_hall 19 | 13,099 | 19,300 |
| 20 | 566,000 | 566,000 | 425,000 | 212,000 | 22h 50m | city_hall 20 | 14,739 | 21,050 |
| 21 | 787,000 | 787,000 | 590,000 | 295,000 | 1d 3h | city_hall 21 | 16,489 | 22,800 |
| 22 | 1,100,000 | 1,100,000 | 828,000 | 414,000 | 1d 8h 25m | city_hall 22 | 18,351 | 24,600 |
| 23 | 1,540,000 | 1,540,000 | 1,150,000 | 576,000 | 1d 15h | city_hall 23 | 20,327 | 26,500 |
| 24 | 2,110,000 | 2,110,000 | 1,580,000 | 792,000 | 1d 22h 30m | city_hall 24 | 22,417 | 28,400 |
| 25 | 2,880,000 | 2,880,000 | 2,160,000 | 1,080,000 | 2d 7h 10m | city_hall 25 | 24,624 | 30,400 |

#### `academy` - Academy

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power |
|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | 52 | 52 | - | - | 4s | city_hall 3 | 35 |
| 2 | 140 | 140 | - | - | 7s | city_hall 3 | 172 |
| 3 | 315 | 315 | - | - | 42s | city_hall 3 | 438 |
| 4 | 700 | 700 | - | - | 3m 30s | city_hall 4 | 849 |
| 5 | 1,260 | 1,260 | 630 | - | 10m | city_hall 5 | 1,418 |
| 6 | 2,800 | 2,800 | 1,400 | - | 28m | city_hall 6 | 2,157 |
| 7 | 5,600 | 5,600 | 2,800 | - | 1h 3m | city_hall 7 | 3,075 |
| 8 | 10,600 | 10,600 | 5,320 | - | 2h 6m | city_hall 8 | 4,180 |
| 9 | 19,000 | 19,000 | 9,520 | - | 3h 30m | city_hall 9 | 5,481 |
| 10 | 33,600 | 33,600 | 16,800 | - | 5h 36m | city_hall 10 | 6,983 |
| 11 | 42,600 | 42,600 | 31,900 | 16,000 | 8h 25m | city_hall 11 | 8,695 |
| 12 | 65,000 | 65,000 | 48,700 | 24,400 | 11h 55m | city_hall 12 | 10,621 |
| 13 | 98,600 | 98,600 | 73,900 | 37,000 | 16h 5m | city_hall 13 | 12,768 |
| 14 | 152,000 | 152,000 | 114,000 | 57,100 | 21h | city_hall 14 | 15,141 |
| 15 | 235,000 | 235,000 | 176,000 | 88,200 | 1d 2h 35m | city_hall 15 | 17,745 |
| 16 | 336,000 | 336,000 | 252,000 | 126,000 | 1d 1h 10m | city_hall 16 | 20,585 |
| 17 | 470,000 | 470,000 | 353,000 | 176,000 | 1d 6h 50m | city_hall 17 | 23,665 |
| 18 | 672,000 | 672,000 | 504,000 | 252,000 | 1d 12h 25m | city_hall 18 | 26,989 |
| 19 | 941,000 | 941,000 | 706,000 | 353,000 | 1d 20h 5m | city_hall 19 | 30,563 |
| 20 | 1,320,000 | 1,320,000 | 991,000 | 496,000 | 2d 5h 10m | city_hall 20 | 34,390 |
| 21 | 1,840,000 | 1,840,000 | 1,380,000 | 689,000 | 2d 15h | city_hall 21 | 38,474 |
| 22 | 2,580,000 | 2,580,000 | 1,930,000 | 966,000 | 3d 3h 35m | city_hall 22 | 42,819 |
| 23 | 3,580,000 | 3,580,000 | 2,690,000 | 1,340,000 | 3d 19h | city_hall 23 | 47,429 |
| 24 | 4,930,000 | 4,930,000 | 3,700,000 | 1,850,000 | 4d 12h 30m | city_hall 24 | 52,306 |
| 25 | 6,720,000 | 6,720,000 | 5,040,000 | 2,520,000 | 5d 8h 50m | city_hall 25 | 57,455 |

#### `scout_camp` - Scout Camp

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Scouts | Scout speed | Scout range |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 | 26 | 26 | - | - | 2s | city_hall 2 | 18 | 1 | 126 | 340 |
| 2 | 70 | 70 | - | - | 4s | city_hall 2 | 86 | 1 | 132 | 380 |
| 3 | 158 | 158 | - | - | 21s | city_hall 3 | 219 | 1 | 138 | 420 |
| 4 | 350 | 350 | - | - | 1m 45s | city_hall 4 | 424 | 1 | 144 | 460 |
| 5 | 630 | 630 | 315 | - | 5m 15s | city_hall 5 | 709 | 1 | 150 | 500 |
| 6 | 1,400 | 1,400 | 700 | - | 14m | city_hall 6 | 1,078 | 1 | 156 | 540 |
| 7 | 2,800 | 2,800 | 1,400 | - | 31m | city_hall 7 | 1,537 | 1 | 162 | 580 |
| 8 | 5,320 | 5,320 | 2,660 | - | 1h 3m | city_hall 8 | 2,090 | 2 | 168 | 620 |
| 9 | 9,520 | 9,520 | 4,760 | - | 1h 45m | city_hall 9 | 2,740 | 2 | 174 | 660 |
| 10 | 16,800 | 16,800 | 8,400 | - | 2h 48m | city_hall 10 | 3,492 | 2 | 180 | 700 |
| 11 | 21,300 | 21,300 | 16,000 | 7,980 | 4h 12m | city_hall 11 | 4,348 | 2 | 186 | 740 |
| 12 | 32,500 | 32,500 | 24,400 | 12,200 | 5h 57m | city_hall 12 | 5,311 | 2 | 192 | 780 |
| 13 | 49,300 | 49,300 | 37,000 | 18,500 | 8h 5m | city_hall 13 | 6,384 | 2 | 198 | 820 |
| 14 | 76,200 | 76,200 | 57,100 | 28,600 | 10h 30m | city_hall 14 | 7,571 | 2 | 204 | 860 |
| 15 | 118,000 | 118,000 | 88,200 | 44,100 | 13h 20m | city_hall 15 | 8,873 | 2 | 210 | 900 |
| 16 | 168,000 | 168,000 | 126,000 | 63,000 | 12h 35m | city_hall 16 | 10,292 | 3 | 216 | 940 |
| 17 | 235,000 | 235,000 | 176,000 | 88,200 | 15h 25m | city_hall 17 | 11,832 | 3 | 222 | 980 |
| 18 | 336,000 | 336,000 | 252,000 | 126,000 | 18h 10m | city_hall 18 | 13,495 | 3 | 228 | 1,020 |
| 19 | 470,000 | 470,000 | 353,000 | 176,000 | 22h 5m | city_hall 19 | 15,282 | 3 | 234 | 1,060 |
| 20 | 661,000 | 661,000 | 496,000 | 248,000 | 1d 2h 35m | city_hall 20 | 17,195 | 3 | 240 | 1,100 |
| 21 | 918,000 | 918,000 | 689,000 | 344,000 | 1d 7h 30m | city_hall 21 | 19,237 | 3 | 246 | 1,140 |
| 22 | 1,290,000 | 1,290,000 | 966,000 | 483,000 | 1d 13h 50m | city_hall 22 | 21,410 | 3 | 252 | 1,180 |
| 23 | 1,790,000 | 1,790,000 | 1,340,000 | 672,000 | 1d 21h 30m | city_hall 23 | 23,714 | 3 | 258 | 1,220 |
| 24 | 2,460,000 | 2,460,000 | 1,850,000 | 924,000 | 2d 6h 15m | city_hall 24 | 26,153 | 3 | 264 | 1,260 |
| 25 | 3,360,000 | 3,360,000 | 2,520,000 | 1,260,000 | 2d 16h 25m | city_hall 25 | 28,728 | 3 | 270 | 1,300 |

#### `watchtower` - Watchtower

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Tower potency | Intel tier |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 33 | 33 | - | - | 2s | city_hall 5 | 22 | 24 | 1 |
| 2 | 90 | 90 | - | - | 4s | city_hall 5 | 111 | 28 | 1 |
| 3 | 202 | 202 | - | - | 27s | city_hall 5 | 282 | 32 | 1 |
| 4 | 450 | 450 | - | - | 2m 15s | city_hall 5 | 546 | 36 | 1 |
| 5 | 405 | 810 | 810 | - | 6m 45s | city_hall 5 | 912 | 40 | 2 |
| 6 | 900 | 1,800 | 1,800 | - | 18m | city_hall 6 | 1,387 | 44 | 2 |
| 7 | 1,800 | 3,600 | 3,600 | - | 40m | city_hall 7 | 1,977 | 48 | 2 |
| 8 | 3,420 | 6,840 | 6,840 | - | 1h 21m | city_hall 8 | 2,687 | 52 | 2 |
| 9 | 6,120 | 12,200 | 12,200 | - | 2h 15m | city_hall 9 | 3,523 | 56 | 2 |
| 10 | 10,800 | 21,600 | 21,600 | - | 3h 36m | city_hall 10 | 4,489 | 60 | 3 |
| 11 | 13,700 | 27,400 | 34,200 | 10,300 | 5h 24m | city_hall 11 | 5,590 | 64 | 3 |
| 12 | 20,900 | 41,800 | 52,200 | 15,700 | 7h 40m | city_hall 12 | 6,828 | 68 | 3 |
| 13 | 31,700 | 63,400 | 79,200 | 23,800 | 10h 20m | city_hall 13 | 8,208 | 72 | 3 |
| 14 | 49,000 | 97,900 | 122,000 | 36,700 | 13h 30m | city_hall 14 | 9,734 | 76 | 3 |
| 15 | 75,600 | 151,000 | 189,000 | 56,700 | 17h 5m | city_hall 15 | 11,408 | 80 | 4 |
| 16 | 108,000 | 216,000 | 270,000 | 81,000 | 16h 10m | city_hall 16 | 13,233 | 84 | 4 |
| 17 | 151,000 | 302,000 | 378,000 | 113,000 | 19h 50m | city_hall 17 | 15,213 | 88 | 4 |
| 18 | 216,000 | 432,000 | 540,000 | 162,000 | 23h 25m | city_hall 18 | 17,350 | 92 | 4 |
| 19 | 302,000 | 605,000 | 756,000 | 227,000 | 1d 4h 20m | city_hall 19 | 19,648 | 96 | 4 |
| 20 | 425,000 | 850,000 | 1,060,000 | 319,000 | 1d 10h 10m | city_hall 20 | 22,108 | 100 | 5 |
| 21 | 590,000 | 1,180,000 | 1,480,000 | 443,000 | 1d 16h 30m | city_hall 21 | 24,734 | 104 | 5 |
| 22 | 828,000 | 1,660,000 | 2,070,000 | 621,000 | 2d 35m | city_hall 22 | 27,527 | 108 | 5 |
| 23 | 1,150,000 | 2,300,000 | 2,880,000 | 864,000 | 2d 10h 30m | city_hall 23 | 30,490 | 112 | 5 |
| 24 | 1,580,000 | 3,170,000 | 3,960,000 | 1,190,000 | 2d 21h 45m | city_hall 24 | 33,625 | 116 | 5 |
| 25 | 2,160,000 | 4,320,000 | 5,400,000 | 1,620,000 | 3d 10h 50m | city_hall 25 | 36,936 | 120 | 5 |

#### `alliance_hall` - Alliance Hall

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Help limit | Reinforce cap |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 37 | 37 | - | - | 2s | city_hall 3 | 25 | 5 | 4,000 |
| 2 | 100 | 100 | - | - | 5s | city_hall 3 | 123 | 6 | 11,000 |
| 3 | 225 | 225 | - | - | 30s | city_hall 3 | 313 | 6 | 20,000 |
| 4 | 500 | 500 | - | - | 2m 30s | city_hall 4 | 606 | 7 | 30,000 |
| 5 | 900 | 900 | 450 | - | 7m 30s | city_hall 5 | 1,013 | 7 | 41,000 |
| 6 | 2,000 | 2,000 | 1,000 | - | 20m | city_hall 6 | 1,541 | 8 | 54,000 |
| 7 | 4,000 | 4,000 | 2,000 | - | 45m | city_hall 7 | 2,196 | 8 | 67,000 |
| 8 | 7,600 | 7,600 | 3,800 | - | 1h 30m | city_hall 8 | 2,986 | 9 | 82,000 |
| 9 | 13,600 | 13,600 | 6,800 | - | 2h 30m | city_hall 9 | 3,915 | 9 | 97,000 |
| 10 | 24,000 | 24,000 | 12,000 | - | 4h | city_hall 10 | 4,988 | 10 | 113,000 |
| 11 | 30,400 | 30,400 | 22,800 | 11,400 | 6h | city_hall 11 | 6,211 | 10 | 129,000 |
| 12 | 46,400 | 46,400 | 34,800 | 17,400 | 8h 30m | city_hall 12 | 7,587 | 11 | 147,000 |
| 13 | 70,400 | 70,400 | 52,800 | 26,400 | 11h 30m | city_hall 13 | 9,120 | 11 | 165,000 |
| 14 | 109,000 | 109,000 | 81,600 | 40,800 | 15h | city_hall 14 | 10,815 | 12 | 184,000 |
| 15 | 168,000 | 168,000 | 126,000 | 63,000 | 19h | city_hall 15 | 12,675 | 12 | 203,000 |
| 16 | 240,000 | 240,000 | 180,000 | 90,000 | 18h | city_hall 16 | 14,703 | 13 | 223,000 |
| 17 | 336,000 | 336,000 | 252,000 | 126,000 | 22h | city_hall 17 | 16,903 | 13 | 243,000 |
| 18 | 480,000 | 480,000 | 360,000 | 180,000 | 1d 2h | city_hall 18 | 19,278 | 14 | 264,000 |
| 19 | 672,000 | 672,000 | 504,000 | 252,000 | 1d 7h 30m | city_hall 19 | 21,831 | 14 | 286,000 |
| 20 | 944,000 | 944,000 | 708,000 | 354,000 | 1d 14h | city_hall 20 | 24,565 | 15 | 308,000 |
| 21 | 1,310,000 | 1,310,000 | 984,000 | 492,000 | 1d 21h | city_hall 21 | 27,482 | 15 | 331,000 |
| 22 | 1,840,000 | 1,840,000 | 1,380,000 | 690,000 | 2d 6h | city_hall 22 | 30,585 | 16 | 354,000 |
| 23 | 2,560,000 | 2,560,000 | 1,920,000 | 960,000 | 2d 17h | city_hall 23 | 33,878 | 16 | 377,000 |
| 24 | 3,520,000 | 3,520,000 | 2,640,000 | 1,320,000 | 3d 5h 30m | city_hall 24 | 37,362 | 17 | 401,000 |
| 25 | 4,800,000 | 4,800,000 | 3,600,000 | 1,800,000 | 3d 20h | city_hall 25 | 41,039 | 17 | 426,000 |

#### `hall_of_heroes` - Hall of Heroes

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Daily sculptures | Cmdr XP % |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 37 | 37 | - | - | 2s | city_hall 4 | 25 | 1 | 1 |
| 2 | 100 | 100 | - | - | 5s | city_hall 4 | 123 | 1 | 2 |
| 3 | 225 | 225 | - | - | 30s | city_hall 4 | 313 | 1 | 3 |
| 4 | 500 | 500 | - | - | 2m 30s | city_hall 4 | 606 | 1 | 4 |
| 5 | 900 | 900 | 450 | - | 7m 30s | city_hall 5 | 1,013 | 1 | 5 |
| 6 | 2,000 | 2,000 | 1,000 | - | 20m | city_hall 6 | 1,541 | 1 | 6 |
| 7 | 4,000 | 4,000 | 2,000 | - | 45m | city_hall 7 | 2,196 | 1 | 7 |
| 8 | 7,600 | 7,600 | 3,800 | - | 1h 30m | city_hall 8 | 2,986 | 2 | 8 |
| 9 | 13,600 | 13,600 | 6,800 | - | 2h 30m | city_hall 9 | 3,915 | 2 | 9 |
| 10 | 24,000 | 24,000 | 12,000 | - | 4h | city_hall 10 | 4,988 | 2 | 10 |
| 11 | 30,400 | 30,400 | 22,800 | 11,400 | 6h | city_hall 11 | 6,211 | 2 | 11 |
| 12 | 46,400 | 46,400 | 34,800 | 17,400 | 8h 30m | city_hall 12 | 7,587 | 2 | 12 |
| 13 | 70,400 | 70,400 | 52,800 | 26,400 | 11h 30m | city_hall 13 | 9,120 | 2 | 13 |
| 14 | 109,000 | 109,000 | 81,600 | 40,800 | 15h | city_hall 14 | 10,815 | 2 | 14 |
| 15 | 168,000 | 168,000 | 126,000 | 63,000 | 19h | city_hall 15 | 12,675 | 2 | 15 |
| 16 | 240,000 | 240,000 | 180,000 | 90,000 | 18h | city_hall 16 | 14,703 | 3 | 16 |
| 17 | 336,000 | 336,000 | 252,000 | 126,000 | 22h | city_hall 17 | 16,903 | 3 | 17 |
| 18 | 480,000 | 480,000 | 360,000 | 180,000 | 1d 2h | city_hall 18 | 19,278 | 3 | 18 |
| 19 | 672,000 | 672,000 | 504,000 | 252,000 | 1d 7h 30m | city_hall 19 | 21,831 | 3 | 19 |
| 20 | 944,000 | 944,000 | 708,000 | 354,000 | 1d 14h | city_hall 20 | 24,565 | 3 | 20 |
| 21 | 1,310,000 | 1,310,000 | 984,000 | 492,000 | 1d 21h | city_hall 21 | 27,482 | 3 | 21 |
| 22 | 1,840,000 | 1,840,000 | 1,380,000 | 690,000 | 2d 6h | city_hall 22 | 30,585 | 3 | 22 |
| 23 | 2,560,000 | 2,560,000 | 1,920,000 | 960,000 | 2d 17h | city_hall 23 | 33,878 | 3 | 23 |
| 24 | 3,520,000 | 3,520,000 | 2,640,000 | 1,320,000 | 3d 5h 30m | city_hall 24 | 37,362 | 4 | 24 |
| 25 | 4,800,000 | 4,800,000 | 3,600,000 | 1,800,000 | 3d 20h | city_hall 25 | 41,039 | 4 | 25 |

#### `war_hall` - War Hall

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Rally capacity |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 41 | 41 | - | - | 3s | city_hall 8 | 28 | 10,000 |
| 2 | 110 | 110 | - | - | 6s | city_hall 8 | 135 | 26,000 |
| 3 | 248 | 248 | - | - | 33s | city_hall 8 | 344 | 47,000 |
| 4 | 550 | 550 | - | - | 2m 45s | city_hall 8 | 667 | 70,000 |
| 5 | 990 | 990 | 495 | - | 8m 15s | city_hall 8 | 1,114 | 95,000 |
| 6 | 2,200 | 2,200 | 1,100 | - | 22m | city_hall 8 | 1,695 | 123,000 |
| 7 | 4,400 | 4,400 | 2,200 | - | 50m | city_hall 8 | 2,416 | 152,000 |
| 8 | 8,360 | 8,360 | 4,180 | - | 1h 39m | city_hall 8 | 3,284 | 184,000 |
| 9 | 15,000 | 15,000 | 7,480 | - | 2h 45m | city_hall 9 | 4,306 | 217,000 |
| 10 | 26,400 | 26,400 | 13,200 | - | 4h 24m | city_hall 10 | 5,487 | 251,000 |
| 11 | 33,400 | 33,400 | 25,100 | 12,500 | 6h 35m | city_hall 11 | 6,832 | 287,000 |
| 12 | 51,000 | 51,000 | 38,300 | 19,100 | 9h 20m | city_hall 12 | 8,345 | 324,000 |
| 13 | 77,400 | 77,400 | 58,100 | 29,000 | 12h 40m | city_hall 13 | 10,032 | 363,000 |
| 14 | 120,000 | 120,000 | 89,800 | 44,900 | 16h 30m | city_hall 14 | 11,897 | 402,000 |
| 15 | 185,000 | 185,000 | 139,000 | 69,300 | 20h 55m | city_hall 15 | 13,943 | 443,000 |
| 16 | 264,000 | 264,000 | 198,000 | 99,000 | 19h 50m | city_hall 16 | 16,174 | 485,000 |
| 17 | 370,000 | 370,000 | 277,000 | 139,000 | 1d 10m | city_hall 17 | 18,594 | 528,000 |
| 18 | 528,000 | 528,000 | 396,000 | 198,000 | 1d 4h 35m | city_hall 18 | 21,206 | 572,000 |
| 19 | 739,000 | 739,000 | 554,000 | 277,000 | 1d 10h 40m | city_hall 19 | 24,014 | 617,000 |
| 20 | 1,040,000 | 1,040,000 | 779,000 | 389,000 | 1d 17h 50m | city_hall 20 | 27,021 | 663,000 |
| 21 | 1,440,000 | 1,440,000 | 1,080,000 | 541,000 | 2d 1h 30m | city_hall 21 | 30,230 | 710,000 |
| 22 | 2,020,000 | 2,020,000 | 1,520,000 | 759,000 | 2d 11h 25m | city_hall 22 | 33,644 | 758,000 |
| 23 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 23h 30m | city_hall 23 | 37,265 | 806,000 |
| 24 | 3,870,000 | 3,870,000 | 2,900,000 | 1,450,000 | 3d 13h 15m | city_hall 24 | 41,098 | 856,000 |
| 25 | 5,280,000 | 5,280,000 | 3,960,000 | 1,980,000 | 4d 5h 10m | city_hall 25 | 45,143 | 906,000 |

#### `caravan_post` - Caravan Post

| Lv | Food | Wood | Stone | Gold | Time | Requires | Power | Caravan load | Tax % |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 30 | 30 | - | - | 2s | city_hall 9 | 20 | 20,000 | 19 |
| 2 | 80 | 80 | - | - | 4s | city_hall 9 | 98 | 49,000 | 19 |
| 3 | 180 | 180 | - | - | 24s | city_hall 9 | 250 | 83,000 | 18 |
| 4 | 400 | 400 | - | - | 2m | city_hall 9 | 485 | 121,000 | 17 |
| 5 | 720 | 720 | 360 | - | 6m | city_hall 9 | 810 | 162,000 | 17 |
| 6 | 1,600 | 1,600 | 800 | - | 16m | city_hall 9 | 1,232 | 205,000 | 16 |
| 7 | 3,200 | 3,200 | 1,600 | - | 36m | city_hall 9 | 1,757 | 251,000 | 16 |
| 8 | 6,080 | 6,080 | 3,040 | - | 1h 12m | city_hall 9 | 2,389 | 299,000 | 15 |
| 9 | 10,900 | 10,900 | 5,440 | - | 2h | city_hall 9 | 3,132 | 348,000 | 14 |
| 10 | 19,200 | 19,200 | 9,600 | - | 3h 12m | city_hall 10 | 3,991 | 399,000 | 14 |
| 11 | 24,300 | 24,300 | 18,200 | 9,120 | 4h 48m | city_hall 11 | 4,969 | 452,000 | 13 |
| 12 | 37,100 | 37,100 | 27,800 | 13,900 | 6h 50m | city_hall 12 | 6,069 | 506,000 | 12 |
| 13 | 56,300 | 56,300 | 42,200 | 21,100 | 9h 10m | city_hall 13 | 7,296 | 561,000 | 12 |
| 14 | 87,000 | 87,000 | 65,300 | 32,600 | 12h | city_hall 14 | 8,652 | 618,000 | 11 |
| 15 | 134,000 | 134,000 | 101,000 | 50,400 | 15h 10m | city_hall 15 | 10,140 | 676,000 | 10 |
| 16 | 192,000 | 192,000 | 144,000 | 72,000 | 14h 25m | city_hall 16 | 11,763 | 735,000 | 10 |
| 17 | 269,000 | 269,000 | 202,000 | 101,000 | 17h 35m | city_hall 17 | 13,523 | 795,000 | 9 |
| 18 | 384,000 | 384,000 | 288,000 | 144,000 | 20h 50m | city_hall 18 | 15,423 | 857,000 | 8 |
| 19 | 538,000 | 538,000 | 403,000 | 202,000 | 1d 1h 10m | city_hall 19 | 17,465 | 919,000 | 8 |
| 20 | 755,000 | 755,000 | 566,000 | 283,000 | 1d 6h 25m | city_hall 20 | 19,652 | 983,000 | 7 |
| 21 | 1,050,000 | 1,050,000 | 787,000 | 394,000 | 1d 12h | city_hall 21 | 21,985 | 1,047,000 | 7 |
| 22 | 1,470,000 | 1,470,000 | 1,100,000 | 552,000 | 1d 19h 10m | city_hall 22 | 24,468 | 1,112,000 | 6 |
| 23 | 2,050,000 | 2,050,000 | 1,540,000 | 768,000 | 2d 4h | city_hall 23 | 27,102 | 1,178,000 | 5 |
| 24 | 2,820,000 | 2,820,000 | 2,110,000 | 1,060,000 | 2d 14h | city_hall 24 | 29,889 | 1,245,000 | 5 |
| 25 | 3,840,000 | 3,840,000 | 2,880,000 | 1,440,000 | 3d 1h 35m | city_hall 25 | 32,832 | 1,313,000 | 4 |
<!-- /GEN:building_tables -->

## 4. Builders and the construction queue

- Every city has exactly **2 builder slots**. This is a constant in
  `data/progression.yaml` (`builders: 2`), not purchasable and not affected by modifiers.
- A **job** is `{ building_id (runtime), target_level, started_at, completes_at, helps_received, total_time_s }`.
  A builder slot is busy while its job exists.
- Constructing a new building and upgrading are the same kind of job
  (construction = reach level 1). A building under construction exists on the
  grid at level 0 and has no effects. A building being upgraded keeps working
  at its current level (it still produces/trains/heals/researches).
- Exception: a `hospital`/military building that is being upgraded still
  works; an `academy` under upgrade still runs research (we do not pause queues).

State machine per building: `absent → constructing(0) → idle(L) → upgrading(L→L+1) → idle(L+1)`.

### 4.1 `upgrade_building` / `build_building` validation order

Return the first failing check as an error:

1. Building exists and belongs to the player (`not_found`) / kind exists (`invalid_target`).
2. Not already under construction/upgrade (`queue_full` with message "already upgrading").
3. `target_level ≤ max_level` (`limit_reached`).
4. For construction: owned copies (including ones under construction) `< max_count` (`limit_reached`);
   City Hall level ≥ `requires_city_hall` (`requirements_not_met`); footprint
   fully inside `[0, city_size)` and not overlapping any building (`invalid_target`).
5. Every `levels[target].requires` entry satisfied by the **highest completed**
   level among the player's copies of that building (`requirements_not_met`,
   message lists what is missing).
6. A builder slot is free (`queue_full`).
7. Stockpile ≥ cost after `collect(now)` (`insufficient_resources`).

On success: deduct cost, create the job with
`total_time_s = max(1, ceil(time_s / (1 + build_speed_pct/100)))` and
`completes_at = now + total_time_s·1000`. Modifiers are sampled once, at start;
later changes do not alter running jobs. A level with `time_s == 0` completes immediately.

### 4.2 Completion, cancel, speedups, free finish

- **Completion** is applied lazily whenever the city is touched and on the
  server tick: if `now ≥ completes_at`, level becomes `target_level`, the slot
  frees, power is recomputed, `city_update` is pushed, quest/objective progress fires.
  Before changing a production building's level, run `collect_buffer` accounting
  (§6) at `completes_at` so the old rate applies up to that instant.
- **Cancel** (`cancel_build`): allowed any time before completion. Refund
  `floor(50 % of each resource paid)`. A cancelled construction removes the
  building. Items spent are not refunded.
- **Speedup items** (08 §2): `completes_at -= item_seconds·1000` per item used,
  clamped so `completes_at ≥ now` (excess is wasted; the client warns first).
  `speedup_build_*` and `speedup_universal_*` apply here.
- **Free finish**: if `completes_at - now ≤ free_finish_s·1000` the player may
  send `finish_build_free`. `free_finish_s = 180 + free_finish_flat` (modifier key
  `free_finish_flat`, from Renown, 08 §3). No cost.
- **Alliance help**: 07 §4. Each help subtracts
  `max(60, floor(0.01 · total_time_s))` seconds, at most `help_limit` times per job.

### 4.3 Moving buildings

`move_building { building_id, x, y }`: free, instant, any time (even while
upgrading), same bounds/overlap check as construction. `wall` cannot be moved
(`not_allowed`). There is no demolish action; nothing can be destroyed by the owner.

## 5. City grid

- 40×40 tiles (`city_size`), tile = 1 world unit inside the city scene.
- Footprints are axis-aligned squares anchored at their top-left tile.
- Tiles `y ≥ 37` except the gatehouse are reserved (wall strip); also reserve the
  1-tile border (`x==0`, `y==0`, `x==39`). Server rejects placement there.
- Total footprint of every building at max count is 188 tiles² of the ~1,330
  usable, so placement can never dead-end.

## 6. Production (lazy, buffered)

Each production building keeps `buffer: f64` and `buffer_at: u64` (ms).

```text
rate_per_hour(b, now)  = production_per_hour(level) × (1 + <res>_production_pct / 100)
                         [food only: − upkeep share, see below]
accrue(b, now):          buffer = min(buffer_capacity(level), buffer + rate × (now − buffer_at)/3_600_000)
                         buffer_at = now
collect(b, now):         accrue; stockpile[res] += floor(buffer); buffer −= floor(buffer)
```

- `accrue` is called before any event that changes the rate (level-up, modifier
  change, troop count change for food) and when the city is serialised.
- `collect_resources { building_id? }`: without id collects all production
  buildings. The client shows a "collect" bubble over a building when its
  buffer is ≥ 10 % full or ≥ 30 min old.
- `<res>_production_pct` keys: `food_production_pct`, `wood_production_pct`,
  `stone_production_pct`, `gold_production_pct`.
- **Troop upkeep** (02 §3): `upkeep = Σ troops owned × upkeep_food_per_hour × (1 + troop_upkeep_pct/100)`
  (all troops the player owns anywhere, healthy or wounded). The total food rate
  of the city is `max(0.25 × gross, gross − upkeep)` where `gross` is the sum of
  all farms' rates; the reduction is spread over farms proportionally to their
  gross rate. Upkeep never touches the stockpile and troops never desert.
- The city view sent to clients contains, per production building,
  `buffer`, `buffer_at`, `rate_per_hour`, `buffer_capacity`, so the client can interpolate.

## 7. Storehouse protection and loot

When a city loses a defence (05 §9.4):

```text
protected[r] = protect_<r>(storehouse level, 0 if none) × (1 + storehouse_protection_pct/100)
lootable[r]  = max(0, stockpile[r] − protected[r])       # after collect() is NOT called: buffers are safe
capacity     = Σ surviving healthy attacker troops × load × (1 + troop_load_pct/100)   (attacker's modifiers)
want         = Σ_r lootable[r]
if want ≤ capacity: take all lootable
else: take floor(lootable[r] × capacity / want) of each r
```

Resource weights for load: 1 load carries 1 food or 1 wood, but stone costs
1.33 load and gold 2 load per unit. Apply by converting `lootable` to load
units first (`stone × 1.33`, `gold × 2`), scaling, then converting back with `floor`.
Production buffers and resource **items** in the inventory are never lootable.
A city under a peace shield cannot be attacked at all (06 §12).

## 8. Power

`building_power = Σ levels[current].power` over all buildings (level-0 buildings
contribute 0). Totals for reference:

<!-- GEN:totals -->
| Quantity | Value |
|---|---:|
| City Hall 2-25 raw time | 44d 20h 31m |
| All buildings to 25 raw builder time | 540d 11h 47m |
| All buildings to 25 total cost | 1,293,149,641 |
| All research raw time | 251d 1h 24m |
| All research total cost | 334,485,782 |
| Research node-levels | 356 |
| Power: all buildings at 25 | 989,054 |
| Power: all research | 1,156,890 |
<!-- /GEN:totals -->

## 9. Pacing

Design target (DESIGN.md): max City Hall in roughly 3–4 months of regular play.
`tools/sim_economy.py` plays the rules of this document with two player
profiles and prints the day each City Hall level completes:

- **Active**: 6 sessions/day (07, 10, 13, 16, 19, 22 h) of 20 min, 150 min/day of
  build speedups, 90 min/day of research speedups, 80 % of possible alliance helps.
- **Regular**: 3 sessions/day of 15 min, 90 / 60 min of speedups, 60 % of helps.

Both start with the tutorial speedups, join an alliance on day 2, spend 30 % of
income on troops, and receive the chapter rewards of 08 §4.

<!-- GEN:pacing -->
| City Hall | Active player (day) | Regular player (day) |
|---:|---:|---:|
| 2 | 0.3 | 0.3 |
| 3 | 0.3 | 0.3 |
| 4 | 0.4 | 0.3 |
| 5 | 0.4 | 0.5 |
| 6 | 0.5 | 0.9 |
| 7 | 0.7 | 0.9 |
| 8 | 0.9 | 1.4 |
| 9 | 1.4 | 2.5 |
| 10 | 2.1 | 3.8 |
| 11 | 3.1 | 5.3 |
| 12 | 4.3 | 7.2 |
| 13 | 6.5 | 10.1 |
| 14 | 9.3 | 13.3 |
| 15 | 12.5 | 18.2 |
| 16 | 16.5 | 22.7 |
| 17 | 20.6 | 27.7 |
| 18 | 25.3 | 34.0 |
| 19 | 32.1 | 42.3 |
| 20 | 40.4 | 51.6 |
| 21 | 48.2 | 60.1 |
| 22 | 58.4 | 72.0 |
| 23 | 70.6 | 86.0 |
| 24 | 85.2 | 103.1 |
| 25 | 105.1 | 125.6 |
<!-- /GEN:pacing -->

Reading the table: City Hall 10 on day 2–4, 17 around three weeks, 22 around two
months, 25 at about 3.5 months (active) / 4 months (regular). When any data in
`buildings.yaml`, `research.yaml` or the speedup income in 08 §2 changes,
re-run the sim; a change is acceptable only if the active profile reaches
City Hall 25 between day 95 and day 115 and City Hall 10 before day 3.
Roadmap task P1-16 ports this simulator to Rust against the real `game-core`.

## 10. Protocol

Requests (all carry `req`; all answered `ok`/`error`; all followed by a `city_update` push on success):

| Message | Fields | Notes |
|---|---|---|
| `get_city` | — | existing; answer `city_state` |
| `build_building` | `kind, x, y` | §4.1 |
| `upgrade_building` | `building_id` | §4.1 |
| `cancel_build` | `building_id` | §4.2 |
| `finish_build_free` | `building_id` | §4.2 |
| `move_building` | `building_id, x, y` | §4.3 |
| `collect_resources` | `building_id?` | §6; `ok` carries `collected: Resources` |
| `use_speedup` | `target: {kind: "build"\|"research"\|"train"\|"heal", id}, item_id, count` | 08 §2 |

Pushes:

| Message | Fields |
|---|---|
| `city_state` / `city_update` | `city: CityView, server_time` |

`CityView` additions: `resources` (after lazy `accrue`, **not** including buffers),
`buildings[]: { id, kind, level, x, y, footprint, upgrading: {target_level,
started_at, completes_at, total_time_s, helps_received, help_requested}?,
production: {rate_per_hour, buffer, buffer_at, buffer_capacity}? }`,
`builders: { total: 2, busy: n }`, `power`, `modifiers: {key: value}` (the
folded city modifier set, 03 §1.4), `shield_until?`.
The client loads building definitions from a `game_data` message sent once
after login (`{ buildings, troops, research, … }` — the parsed YAML as JSON,
plus `data_version` hash) so it never hard-codes balance.

## 11. Edge cases

- Two requests in the same tick for the last builder slot: process in arrival
  order; the second gets `queue_full`.
- Upgrade completes while the player is offline: applied on next touch with the
  original `completes_at` as the effective time (production accrues at the new
  rate from `completes_at`, not from login).
- City Hall upgrade does not retroactively block anything; prerequisites are
  only checked at start.
- A building whose prerequisite building is later being upgraded stays valid.
- Cancelling a City Hall upgrade never invalidates other buildings (they were
  ≤ the old level anyway).
- Speedup or help reduces `completes_at` below `now`: complete immediately in
  the same request.
- `collect_resources` with all buffers `< 1`: `ok` with zeros (not an error).
- Level-up of a farm while food upkeep clamps production: recompute after `accrue`.
- If `data/` changes between server versions and a stored building has
  `level > max_level`, clamp to `max_level` at load and log a warning.
