# 03 — Modifiers and research

Conventions: [00](00-overview.md). Data: [`data/research.yaml`](data/research.yaml)
(generated; copy to `data/research.yaml`).

## 1. The Modifier system

Every bonus in the game is a pair `(key: string, value: f64)` contributed by a
**source**. `game-core` exposes one type:

```rust
pub struct Modifiers(BTreeMap<ModKey, f64>);      // ModKey: enum generated from the registry in §1.5
impl Modifiers { fn add(&mut self, key, value); fn merge(&mut self, other: &Modifiers); fn get(&self, key) -> f64; }
```

### 1.1 Stacking

1. Values with the same key are **summed** (additive), across all sources.
   Two +5 % sources give +10 %, never ×1.1025.
2. After summing, clamp to the key's `[min, max]` from the registry (§1.5).
3. Apply by key suffix:
   - `*_pct` on a **quantity** (production, capacity, stats, damage): `effective = base × (1 + v/100)`.
   - `*_pct` on a **speed** (`build_speed_pct`, `research_speed_pct`, `train_speed_pct`,
     `heal_speed_pct`): `time = ceil(base_time / (1 + v/100))`. (+100 % speed halves time; it can never reach zero.)
   - `*_speed_pct` for gathering/march/scouts multiplies the rate: `rate × (1 + v/100)`.
   - `*_cost_pct`, `troop_upkeep_pct`: `base × (1 + v/100)` with negative `v` (clamped ≥ −50).
   - `*_flat`: added to the base **before** any `_pct` of the same quantity.
   - `unlock_*`: boolean, true when value ≥ 1.
4. Different keys that affect the same number multiply as separate factors
   only where a formula says so (combat, 05 §3). Everywhere else exactly one
   `_pct` key (plus an optional generic one listed in the registry as "also")
   applies to a quantity, and "also" keys are **summed with** the specific key
   before applying (e.g. infantry attack uses `attack_pct + infantry_attack_pct`).

### 1.2 Scopes

| Scope | Lifetime | Sources | Used for |
|---|---|---|---|
| **Account** | recomputed when a source changes | research, buildings (`garrison_defense_pct`, `commander_xp_pct`), alliance research (07 §5), territory & Sanctum buffs (06 §9, 07 §7), Renown (08 §3), kingdom titles (09 §3), active buff items (08 §2), season buffs (09) | everything in the city; inherited by every army of the player |
| **Army** | recomputed when the army forms / commanders change | Account scope + primary commander's passive skills and talents + secondary commander's passive skills (04 §3, §6) | march speed, capacity, load, gathering, battle stats |
| **Battle** | per tick | Army scope + timed buffs/debuffs from skills (05 §6) + context modifiers (garrison, rally, terrain of structure) | combat formulas only |

Conditions on a contribution (`when:` in data) are evaluated by the scope that
knows the answer: e.g. `when: gathering` is checked when computing gather rate;
`when: garrison` when the army is the garrison of a city/structure. Conditions are listed in 04 §3.2.

### 1.3 Sampling rules

- **Timers** (build, research, train, heal) sample modifiers once at start (01 §4.1).
- **Rates** (production, gathering) use current modifiers; call `accrue` before any change.
- **March** speed is sampled when the march order is issued (06 §11).
- **Battle** stats are recomputed at the start of every tick from the current buff list (cheap: ≤ 30 keys).

### 1.4 Folding order (account scope)

```text
account = research ⊕ building stats flagged as modifiers ⊕ alliance research ⊕ territory/sanctum
          ⊕ renown ⊕ title ⊕ active buff items ⊕ season buffs      (⊕ = key-wise sum)
```

Cache the folded account set on the player; invalidate on: research complete,
building level change, alliance join/leave/research level, territory change,
Renown level-up, title change, buff start/expiry, season phase change.
The client receives the folded set in `CityView.modifiers` and a breakdown per
source on request (`get_modifier_breakdown`, used by the "Bonuses" panel, 10 §3.9).

### 1.5 Registry of keys

Every key any spec uses. Adding a key = adding a row here and a variant in
`ModKey`. `data` validation rejects unknown keys in any YAML file. Clamp is
applied to the summed value.

| Key | Applies to | Clamp |
|---|---|---|
| `food_production_pct`, `wood_production_pct`, `stone_production_pct`, `gold_production_pct` | building production (01 §6) | 0…200 |
| `build_speed_pct` | build/upgrade time | 0…100 |
| `research_speed_pct` | research time | 0…100 |
| `train_speed_pct` | training/promotion time | 0…150 |
| `heal_speed_pct` | healing time | 0…200 |
| `train_cost_pct` | training cost | −50…0 |
| `train_batch_pct` | batch size | 0…100 |
| `gather_speed_pct` (also) + `gather_speed_food_pct`, `gather_speed_wood_pct`, `gather_speed_stone_pct`, `gather_speed_gold_pct` | gather rate (06 §4) | 0…300 (sum) |
| `troop_load_pct` | army load | 0…200 |
| `storehouse_protection_pct` | protection (01 §7) | 0…200 |
| `hospital_capacity_pct` | hospital capacity | 0…100 |
| `troop_upkeep_pct` | upkeep | −50…0 |
| `free_finish_flat` | free-finish threshold seconds (01 §4.2) | 0…420 |
| `stamina_cap_flat`, `stamina_regen_pct` | stamina (06 §6) | 0…500, 0…100 |
| `commander_xp_pct` | commander XP gained | 0…100 |
| `scout_speed_pct` | scout speed | 0…200 |
| `help_limit_flat` | helps per timer (07 §4) | 0…10 |
| `march_speed_pct` | army speed (06 §11) | −50…150 |
| `march_capacity_pct`, `march_capacity_flat` | troops per army (04 §7) | 0…100, 0…100000 |
| `rally_capacity_pct` | rally size (05 §8) | 0…100 |
| `reinforcement_capacity_pct` | hosted reinforcements | 0…100 |
| `wall_durability_pct` | wall durability | 0…200 |
| `garrison_defense_pct` | added to `defense_pct` while garrisoning own city | 0…100 |
| `attack_pct`, `defense_pct`, `health_pct` (also) | all troop types' stats | −80…300 (sum with typed key) |
| `<type>_attack_pct`, `<type>_defense_pct`, `<type>_health_pct` for `infantry`, `cavalry`, `archer`, `siege` | that type's stat (05 §3) | see above |
| `damage_dealt_pct`, `damage_taken_pct` | all damage (05 §3) | −90…300 |
| `normal_damage_pct`, `counter_damage_pct`, `skill_damage_pct` | damage by kind | −90…300 |
| `skill_damage_taken_pct` | skill damage received | −90…300 |
| `barbarian_damage_pct` | damage dealt to PvE armies; multiplies like `damage_dealt_pct` | 0…200 |
| `structure_damage_pct` | durability damage to structures (05 §10) | 0…300 |
| `rage_gain_pct` | rage gained (05 §4) | −100…200 |
| `heal_potency_pct` | in-battle healing (05 §6) | 0…200 |
| `unlock_<type>_t<tier>` (tier 2–5) | troop availability (02 §4.2) | 0…1 |

## 2. Research rules

- One research queue per city, **one active entry**, requires an `academy`.
- Each node has `max_level` levels researched in order. Level `n` requires:
  academy level ≥ `levels[n].academy`, every `requires` node at ≥ the listed
  level, and the stockpile ≥ `levels[n].cost`.
- `total_time_s = max(1, ceil(time_s / (1 + research_speed_pct/100)))`.
- `levels[n].value` is the node's **total** contribution at level `n`
  (replace, do not add, when the level increases).
- Cancel: refund `floor(50 %)`. Speedups: `speedup_research_*`, universal.
  Free finish (01 §4.2) and alliance help (07 §4) apply.
- Research keeps running while the academy is being upgraded.
- `research_power = Σ levels[k].power for k in 1..=current` over all nodes
  (the per-level `power` field is the increment for that level).

`start_research { node_id }` validation order: node exists (`not_found`);
current level < `max_level` (`limit_reached`); queue empty (`queue_full`);
academy level and prerequisites (`requirements_not_met`); cost (`insufficient_resources`).

## 3. Schema

```yaml
research:
  - id: masonry
    name: "Masonry"
    tree: economy            # economy | military (tab in the UI)
    effect: build_speed_pct  # a key from §1.5
    max_level: 10
    requires: {}             # node id -> minimum level
    levels:
      - { level: 1, academy: 3, cost: { food: 56, wood: 56, stone: 0, gold: 0 }, time_s: 15, value: 1.0, power: 90 }
```

Validation: ids unique; `effect` in the registry; `levels` contiguous and
`max_level` long; `academy` non-decreasing, 1…25; `requires` references exist,
levels ≤ their `max_level`, and the graph is acyclic; `value` moves monotonically
away from zero.

Cost and time derivation (in `okdata.py`): a node level gated at academy level
`a` takes `0.25 ×` the City Hall-level-`a` upgrade time and costs `0.125 ×` its
cost; tier-unlock nodes use time factors 0.5 / 0.75 / 1.0 / 1.5 for T2–T5 (cost
half of that factor). Within a node, academy requirements are spread evenly
from the first to the last value in the "Academy lv" column.

## 4. Trees

Layout hint for the UI: each tree is drawn as columns by first academy level;
edges from `requires`.

### 4.1 Economy tree

<!-- GEN:research_economy -->
| id | Name | Levels | Effect | Academy lv | Requires | Total time | Total cost |
|---|---|---:|---|---:|---|---:|---:|
| `crop_rotation` | Crop Rotation | 10 | `food_production_pct` +2/lv | 3-24 | - | 4d 13h 4m | 5,162,474 |
| `sawpits` | Sawpits | 10 | `wood_production_pct` +2/lv | 3-24 | - | 4d 13h 4m | 5,162,474 |
| `masonry` | Masonry | 10 | `build_speed_pct` +1/lv | 3-15 | - | 1d 3h 33m | 300,162 |
| `scholarship` | Scholarship | 10 | `research_speed_pct` +1.5/lv | 4-16 | masonry 1 | 1d 9h 57m | 450,362 |
| `foraging` | Foraging | 10 | `gather_speed_food_pct` +3/lv | 4-24 | crop_rotation 1 | 4d 18h 56m | 5,403,300 |
| `timber_hauling` | Timber Hauling | 10 | `gather_speed_wood_pct` +3/lv | 4-24 | sawpits 1 | 4d 18h 56m | 5,403,300 |
| `stonecutting` | Stonecutting | 10 | `stone_production_pct` +2/lv | 5-24 | masonry 2 | 4d 21h 10m | 5,577,312 |
| `quarry_camps` | Quarry Camps | 10 | `gather_speed_stone_pct` +3/lv | 6-24 | stonecutting 1 | 5d 1h 25m | 5,629,250 |
| `pack_saddles` | Pack Saddles | 10 | `troop_load_pct` +2.5/lv | 6-24 | foraging 2, timber_hauling 2 | 5d 1h 25m | 5,629,250 |
| `granaries` | Hidden Granaries | 10 | `storehouse_protection_pct` +5/lv | 7-25 | crop_rotation 3 | 6d 3h 37m | 7,783,550 |
| `field_medicine` | Field Medicine | 10 | `heal_speed_pct` +3/lv | 8-25 | scholarship 2 | 6d 7h 15m | 7,891,000 |
| `cartography` | Cartography | 5 | `scout_speed_pct` +6/lv | 8-20 | scholarship 1 | 1d 17h 15m | 1,113,500 |
| `coinage` | Coinage | 10 | `gold_production_pct` +2/lv | 10-25 | stonecutting 3 | 7d 2h | 8,799,550 |
| `prospecting` | Prospecting | 10 | `gather_speed_gold_pct` +3/lv | 11-25 | coinage 1, quarry_camps 3 | 7d 8h 30m | 9,063,250 |
| `engineering` | Engineering | 10 | `build_speed_pct` +1/lv | 16-25 | masonry 10 | 9d 18h 30m | 13,049,500 |
| `encyclopedia` | Encyclopedia | 10 | `research_speed_pct` +1.5/lv | 17-25 | scholarship 10 | 10d 8h | 13,887,000 |
<!-- /GEN:research_economy -->

### 4.2 Military tree

The 12 stat nodes give +1 % per level to one stat of one troop type. The 16
`<type>_t<tier>` nodes are single-level unlocks for troop tiers (02 §2).

<!-- GEN:research_military -->
| id | Name | Levels | Effect | Academy lv | Requires | Total time | Total cost |
|---|---|---:|---|---:|---|---:|---:|
| `drill` | Drill | 10 | `train_speed_pct` +2/lv | 3-24 | - | 4d 13h 4m | 5,162,474 |
| `forced_march` | Forced March | 10 | `march_speed_pct` +1/lv | 6-24 | drill 2 | 5d 1h 25m | 5,629,250 |
| `mustering` | Mustering | 10 | `march_capacity_pct` +1/lv | 8-25 | drill 3 | 6d 7h 15m | 7,891,000 |
| `field_rations` | Field Rations | 5 | `troop_upkeep_pct` -6/lv | 8-20 | drill 3 | 1d 17h 15m | 1,113,500 |
| `hospital_wards` | Hospital Wards | 10 | `hospital_capacity_pct` +2/lv | 8-25 | drill 4 | 6d 7h 15m | 7,891,000 |
| `fortification` | Fortification | 10 | `wall_durability_pct` +3/lv | 9-25 | drill 4 | 6d 15h 30m | 8,247,250 |
| `war_councils` | War Councils | 10 | `rally_capacity_pct` +1/lv | 12-25 | mustering 3 | 7d 23h 30m | 10,272,050 |
| `infantry_attack` | Tempered Blades | 10 | `infantry_attack_pct` +1/lv | 4-25 | drill 1 | 5d 9h 41m | 7,138,750 |
| `infantry_defense` | Shield Drill | 10 | `infantry_defense_pct` +1/lv | 5-25 | drill 1 | 5d 16h 25m | 7,470,312 |
| `infantry_health` | Hardened Marches | 10 | `infantry_health_pct` +1/lv | 6-25 | drill 1 | 5d 22h 25m | 7,704,750 |
| `cavalry_attack` | Lance Drill | 10 | `cavalry_attack_pct` +1/lv | 6-25 | drill 1 | 5d 22h 25m | 7,704,750 |
| `cavalry_defense` | Barding | 10 | `cavalry_defense_pct` +1/lv | 7-25 | drill 1 | 6d 3h 37m | 7,783,550 |
| `cavalry_health` | Remount Herds | 10 | `cavalry_health_pct` +1/lv | 8-25 | drill 1 | 6d 7h 15m | 7,891,000 |
| `archer_attack` | Fletching | 10 | `archer_attack_pct` +1/lv | 5-25 | drill 1 | 5d 16h 25m | 7,470,312 |
| `archer_defense` | Pavise Lines | 10 | `archer_defense_pct` +1/lv | 6-25 | drill 1 | 5d 22h 25m | 7,704,750 |
| `archer_health` | Volley Discipline | 10 | `archer_health_pct` +1/lv | 7-25 | drill 1 | 6d 3h 37m | 7,783,550 |
| `siege_attack` | Counterweights | 10 | `siege_attack_pct` +1/lv | 8-25 | drill 1 | 6d 7h 15m | 7,891,000 |
| `siege_defense` | Mantlets | 10 | `siege_defense_pct` +1/lv | 9-25 | drill 1 | 6d 15h 30m | 8,247,250 |
| `siege_health` | Seasoned Timber | 10 | `siege_health_pct` +1/lv | 10-25 | drill 1 | 7d 2h | 8,799,550 |
| `infantry_t2` | Standing Army: Infantry | 1 | `unlock_infantry_t2` | 5 | infantry_attack 1 | 7m 30s | 1,125 |
| `infantry_t3` | Professional Army: Infantry | 1 | `unlock_infantry_t3` | 10 | infantry_attack 3, infantry_t2 1 | 6h | 45,000 |
| `infantry_t4` | Elite Army: Infantry | 1 | `unlock_infantry_t4` | 17 | infantry_attack 6, infantry_t3 1 | 1d 20h | 1,050,000 |
| `infantry_t5` | Peerless Army: Infantry | 1 | `unlock_infantry_t5` | 25 | infantry_attack 10, infantry_t4 1 | 11d 12h | 22,500,000 |
| `cavalry_t2` | Standing Army: Cavalry | 1 | `unlock_cavalry_t2` | 5 | cavalry_attack 1 | 7m 30s | 1,125 |
| `cavalry_t3` | Professional Army: Cavalry | 1 | `unlock_cavalry_t3` | 10 | cavalry_attack 3, cavalry_t2 1 | 6h | 45,000 |
| `cavalry_t4` | Elite Army: Cavalry | 1 | `unlock_cavalry_t4` | 17 | cavalry_attack 6, cavalry_t3 1 | 1d 20h | 1,050,000 |
| `cavalry_t5` | Peerless Army: Cavalry | 1 | `unlock_cavalry_t5` | 25 | cavalry_attack 10, cavalry_t4 1 | 11d 12h | 22,500,000 |
| `archer_t2` | Standing Army: Archer | 1 | `unlock_archer_t2` | 5 | archer_attack 1 | 7m 30s | 1,125 |
| `archer_t3` | Professional Army: Archer | 1 | `unlock_archer_t3` | 10 | archer_attack 3, archer_t2 1 | 6h | 45,000 |
| `archer_t4` | Elite Army: Archer | 1 | `unlock_archer_t4` | 17 | archer_attack 6, archer_t3 1 | 1d 20h | 1,050,000 |
| `archer_t5` | Peerless Army: Archer | 1 | `unlock_archer_t5` | 25 | archer_attack 10, archer_t4 1 | 11d 12h | 22,500,000 |
| `siege_t2` | Standing Army: Siege | 1 | `unlock_siege_t2` | 5 | siege_attack 1 | 7m 30s | 1,125 |
| `siege_t3` | Professional Army: Siege | 1 | `unlock_siege_t3` | 10 | siege_attack 3, siege_t2 1 | 6h | 45,000 |
| `siege_t4` | Elite Army: Siege | 1 | `unlock_siege_t4` | 17 | siege_attack 6, siege_t3 1 | 1d 20h | 1,050,000 |
| `siege_t5` | Peerless Army: Siege | 1 | `unlock_siege_t5` | 25 | siege_attack 10, siege_t4 1 | 11d 12h | 22,500,000 |
<!-- /GEN:research_military -->

### 4.3 Example node, fully expanded (`masonry`)

<!-- GEN:research_example -->
| Lv | Academy | Food | Wood | Stone | Gold | Time | Total effect | Power |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 56 | 56 | - | - | 15s | +1% | 90 |
| 2 | 4 | 125 | 125 | - | - | 1m 15s | +2% | 160 |
| 3 | 6 | 500 | 500 | 250 | - | 10m | +3% | 360 |
| 4 | 7 | 1,000 | 1,000 | 500 | - | 22m | +4% | 490 |
| 5 | 8 | 1,900 | 1,900 | 950 | - | 45m | +5% | 640 |
| 6 | 10 | 6,000 | 6,000 | 3,000 | - | 2h | +6% | 1000 |
| 7 | 11 | 7,600 | 7,600 | 5,700 | 2,850 | 3h | +7% | 1210 |
| 8 | 12 | 11,600 | 11,600 | 8,700 | 4,350 | 4h 15m | +8% | 1440 |
| 9 | 14 | 27,200 | 27,200 | 20,400 | 10,200 | 7h 30m | +9% | 1960 |
| 10 | 15 | 42,000 | 42,000 | 31,500 | 15,800 | 9h 30m | +10% | 2250 |
<!-- /GEN:research_example -->

All other per-level rows are in `data/research.yaml`.

### 4.4 Totals

Whole-tree raw time and cost are in 01 §8. One research slot and ~250 days of
raw research mean an active player has roughly 70 % of the tree at City Hall 25
(simulated: see `sim_economy.py` output) and finishes T5 for a first troop type
around month 5. This is intentional: research is the long-tail goal after max City Hall.

## 5. Protocol

| Request | Fields |
|---|---|
| `start_research` | `node_id` |
| `cancel_research` | — |
| `finish_research_free` | — |
| `get_modifier_breakdown` | — → `ok { sources: [{source, label, modifiers: {key: value}}] }` |

`CityView` additions: `research: { levels: {node_id: level}, active: { node_id, target_level, completes_at, total_time_s, helps_received }? }`.

## 6. Edge cases

- Research finishes offline: applied lazily with `completes_at` as the effective
  time; production buildings `accrue` at the old rate up to that instant first.
- A node's prerequisite is satisfied only by **completed** levels.
- Modifier change while a timer is running: no effect on that timer (§1.3).
- Unknown modifier key in stored player data after a data change: drop it and log.
- Sum outside the clamp: clamp silently; the breakdown panel shows "(capped)".
