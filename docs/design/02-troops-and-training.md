# 02 — Troops and training

Conventions: [00](00-overview.md). Combat use of these stats: [05](05-combat.md).
Data: [`data/troops.yaml`](data/troops.yaml) (generated; copy to `data/troops.yaml`).

## 1. Types, tiers, counters

Four types × five tiers = 20 troop kinds, id `<type>_t<tier>`.

| Type | Trained in | Role | Beats (deals ×1.20) | Loses to (deals ×0.90) |
|---|---|---|---|---|
| `infantry` | `barracks` | Durable front line, average speed | `cavalry` | `archer` |
| `cavalry` | `stable` | Fast, high attack, used for chasing | `archer` | `infantry` |
| `archer` | `archery_range` | Highest attack, fragile | `infantry` | `cavalry` |
| `siege` | `siege_workshop` | Slow, weak in the field, huge load, triple damage to structures (05 §9–10) | — | — (neutral ×1.00 both ways) |

## 2. Stat table

<!-- GEN:troop_table -->
| id | Name | Atk | Def | HP | Speed | Load | Upkeep/h | Power | Food | Wood | Stone | Gold | Train s | Needs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `infantry_t1` | Levy Spearmen | 95 | 110 | 115 | 36 | 10 | 0.005 | 1 | 60 | 40 | 0 | 0 | 10 | barracks 1 |
| `infantry_t2` | Shieldbearers | 124 | 143 | 150 | 36 | 12 | 0.008 | 2 | 96 | 64 | 0 | 0 | 18 | barracks 5 |
| `infantry_t3` | Men-at-Arms | 157 | 182 | 190 | 36 | 13 | 0.012 | 4 | 156 | 104 | 0 | 0 | 30 | barracks 10 |
| `infantry_t4` | Halberdiers | 195 | 225 | 236 | 36 | 14 | 0.018 | 7 | 252 | 168 | 0 | 10 | 48 | barracks 17 |
| `infantry_t5` | Iron Guard | 238 | 275 | 288 | 36 | 16 | 0.026 | 11 | 408 | 272 | 0 | 30 | 75 | barracks 25 |
| `cavalry_t1` | Outriders | 110 | 95 | 110 | 54 | 8 | 0.005 | 1 | 60 | 20 | 20 | 0 | 10 | stable 1 |
| `cavalry_t2` | Lancers | 143 | 124 | 143 | 54 | 9 | 0.008 | 2 | 96 | 32 | 32 | 0 | 18 | stable 5 |
| `cavalry_t3` | Horse Guard | 182 | 157 | 182 | 54 | 10 | 0.012 | 4 | 156 | 52 | 52 | 0 | 30 | stable 10 |
| `cavalry_t4` | Cataphracts | 225 | 195 | 225 | 54 | 12 | 0.018 | 7 | 252 | 84 | 84 | 10 | 48 | stable 17 |
| `cavalry_t5` | Storm Riders | 275 | 238 | 275 | 54 | 13 | 0.026 | 11 | 408 | 136 | 136 | 30 | 75 | stable 25 |
| `archer_t1` | Slingers | 115 | 95 | 100 | 39 | 6 | 0.005 | 1 | 30 | 70 | 0 | 0 | 10 | archery_range 1 |
| `archer_t2` | Bowmen | 150 | 124 | 130 | 39 | 7 | 0.008 | 2 | 48 | 112 | 0 | 0 | 18 | archery_range 5 |
| `archer_t3` | Longbowmen | 190 | 157 | 165 | 39 | 8 | 0.012 | 4 | 78 | 182 | 0 | 0 | 30 | archery_range 10 |
| `archer_t4` | Arbalesters | 236 | 195 | 205 | 39 | 9 | 0.018 | 7 | 126 | 294 | 0 | 10 | 48 | archery_range 17 |
| `archer_t5` | Sky Wardens | 288 | 238 | 250 | 39 | 10 | 0.026 | 11 | 204 | 476 | 0 | 30 | 75 | archery_range 25 |
| `siege_t1` | Battering Rams | 70 | 80 | 90 | 27 | 22 | 0.005 | 1 | 20 | 50 | 40 | 0 | 12 | siege_workshop 1 |
| `siege_t2` | Mangonels | 91 | 104 | 117 | 27 | 25 | 0.008 | 2 | 32 | 80 | 64 | 0 | 22 | siege_workshop 5 |
| `siege_t3` | Ballistae | 116 | 132 | 148 | 27 | 29 | 0.012 | 4 | 52 | 130 | 104 | 0 | 36 | siege_workshop 10 |
| `siege_t4` | Trebuchets | 144 | 164 | 184 | 27 | 32 | 0.018 | 7 | 84 | 210 | 168 | 12 | 58 | siege_workshop 17 |
| `siege_t5` | Siege Titans | 175 | 200 | 225 | 27 | 35 | 0.026 | 11 | 136 | 340 | 272 | 36 | 90 | siege_workshop 25 |
<!-- /GEN:troop_table -->

Derivation (for retuning in `okdata.py`): tier multipliers for attack/defense/health are
×1.00 / 1.30 / 1.65 / 2.05 / 2.50; cost ×1.0 / 1.6 / 2.6 / 4.2 / 6.8; load ×1.00 / 1.15 /
1.30 / 1.45 / 1.60; siege trains 20 % slower and pays 20 % more gold.

Column meanings:

- **Atk / Def / HP**: used only by the combat formulas in 05 §3.
- **Speed**: tiles per minute on the world map. An army moves at the speed of
  its slowest troop kind (06 §11).
- **Load**: resource load units per troop (gathering and loot; stone = 1.33, gold = 2 load per unit).
- **Upkeep/h**: food per hour per troop (01 §6).
- **Power**: per troop; `troop_power = Σ count × power` over healthy + lightly
  wounded + severely wounded troops (wounded count; dead do not).
- **Needs**: building and level required; tiers 2–5 additionally need the
  research node `<type>_t<tier>` (03 §4).

## 3. Schema

```yaml
troops:
  - { id: infantry_t1, name: "Levy Spearmen", type: infantry, tier: 1,
      attack: 95, defense: 110, health: 115, speed: 36, load: 10,
      upkeep_food_per_hour: 0.005, power: 1,
      cost: { food: 60, wood: 40, stone: 0, gold: 0 }, train_time_s: 10,
      building: barracks, building_level: 1, research: null }
```

Validation: 20 entries, every `(type, tier)` exactly once; `building` exists;
`research` is `null` or an existing research id; stats > 0; within a type each
of attack/defense/health/power/cost strictly increases with tier.

## 4. Training

### 4.1 Queue rules

- Each military building has **one training queue with one active entry**
  (no stacking of entries; RoK-style "one batch at a time").
- An entry is `{ troop_id, count, kind: train|promote, from_troop_id?, started_at, completes_at, total_time_s, helps_received }`.
- `count ≤ train_batch(building level) × (1 + train_batch_pct/100)` (floor).
- Troops are delivered **all at once** when the entry completes (lazy + tick,
  like builds). They are added to the city's healthy pool.
- There is no population cap. Upkeep (01 §6) and hospital capacity are the soft limits.

### 4.2 `train_troops { building_id, troop_id, count }` validation order

1. Building exists, is completed (level ≥ 1), is the troop's `building` (`invalid_target`).
2. Building level ≥ `building_level` and research `research` (if any) is at level 1 (`requirements_not_met`).
3. Queue empty (`queue_full`).
4. `1 ≤ count ≤ batch limit` (`limit_reached`).
5. Stockpile ≥ `cost × count` (`insufficient_resources`). Cost has no discounts
   except modifier `train_cost_pct` (negative values reduce; `ceil` per resource on the total).

`total_time_s = max(1, ceil(train_time_s × count / (1 + train_speed_pct/100)))`.

### 4.3 Promotion (upgrading tiers)

`promote_troops { building_id, from_troop_id, to_troop_id, count }`: converts
healthy troops **in the city** to a higher tier of the same type.

- Requirements: same as training `to_troop_id`; `to.tier > from.tier`; the
  player has ≥ `count` healthy `from` troops in the city.
- Cost per troop = `to.cost − from.cost` per resource; time per troop =
  `to.train_time_s − from.train_time_s`; same speed/discount modifiers; same batch limit.
- The `from` troops are removed at start (they stop counting for defence,
  upkeep and power) and the `to` troops arrive at completion.
- Cancelling returns the `from` troops and 50 % of resources.

### 4.4 Cancel, speedups, help

- `cancel_training { building_id }`: refund `floor(50 %)` of resources;
  promotion returns the source troops.
- Speedups: `speedup_train_*` and `speedup_universal_*` (08 §2). Free finish
  does **not** apply to training or healing (build and research only).
- Alliance help applies (07 §4), same formula as builds.

### 4.5 Dismissing

`dismiss_troops { troop_id, count }`: deletes healthy troops in the city, no refund.

## 5. Where troops can be

`city` (healthy pool, defends the city) · `army` (in one of the player's armies:
healthy + lightly wounded) · `hospital` (severely wounded) · `reinforcing`
(inside an ally's city or alliance structure; still an army) · `training/promoting`
(not yet troops). A troop is in exactly one place. All of them except
training count for upkeep and power.

## 6. Hospital

- `capacity = floor(Σ hospital_capacity(level of each hospital) × (1 + hospital_capacity_pct/100))`.
- Severely wounded troops arriving (see §7) fill the hospital in arrival order.
  If a batch does not fit, the overflow **dies**; within a batch the overflow
  is taken from the lowest tier first, then by type order infantry, cavalry,
  archer, siege (so the best troops are saved).
- `heal_troops { troops: {troop_id: count} }`: one healing queue for the whole
  city (all hospitals share it), one active entry.
  - Cost per troop = `ceil-on-total(0.35 × train cost)` per resource; gold is **not** charged for healing (0).
  - Time per troop = `0.25 × train_time_s`; `total = max(1, ceil(Σ / (1 + heal_speed_pct/100)))`.
  - On completion the troops return to the city healthy pool.
  - `speedup_heal_*`/universal speedups and alliance help apply. Cancel refunds 50 %, troops stay wounded.
- Severely wounded troops stay in the hospital indefinitely; they never die there.
- Lightly wounded troops never enter the hospital (§7).

## 7. Wounded and dead

During a battle every troop knocked out becomes either **lightly wounded** or
**severely wounded** (05 §5: by default 60 % light / 40 % severe).

- **Lightly wounded** stay with their army, do not fight, do not carry load,
  and become healthy for free the moment the army enters its owner's city or
  garrisons an alliance structure (07 §7). They also recover instantly when a
  PvE battle (barbarians, Warcamp) ends in victory.
- **Severely wounded** leave the army immediately and are resolved by the
  battle context when the battle ends for that army:

| Context | Side | Severely wounded become |
|---|---|---|
| Barbarians, Warcamps, Sanctum/Pass guardians (PvE) | player | 100 % hospital |
| Field battle (army vs army, gatherer attacked) | both | 100 % hospital |
| Attack on a city (incl. rally) | attacker | 50 % dead, 50 % hospital |
| Attack on a city | defender: owner's troops | 100 % hospital |
| Attack on a city | defender: reinforcing allies | 100 % hospital (their own) |
| Attack on an alliance structure, Pass or Sanctum held by players | attacker | 50 % dead, 50 % hospital |
| same | garrison | 50 % dead, 50 % hospital |
| Season contested zone (09), any battle between players | both | 50 % dead, 50 % hospital, then hospital overflow dies |

"50 %" is `dead = floor(severe / 2)` per troop kind per owner; the remainder
goes to hospital. Hospital overflow always dies (§6). "Hospital" always means
the troop owner's own city hospital, credited instantly (no travel).

Dead troops are gone. Kill statistics credit the opponent with
`severe` counts (not light) — see 05 §11.

## 8. Protocol

| Request | Fields |
|---|---|
| `train_troops` | `building_id, troop_id, count` |
| `promote_troops` | `building_id, from_troop_id, to_troop_id, count` |
| `cancel_training` | `building_id` |
| `dismiss_troops` | `troop_id, count` |
| `heal_troops` | `troops: {troop_id: count}` |
| `cancel_healing` | — |

`CityView` additions: `troops: {troop_id: healthy_in_city}`,
`hospital: { capacity, wounded: {troop_id: n}, healing: {troops, completes_at, total_time_s, helps_received}? }`,
`buildings[].training: { troop_id, count, kind, from_troop_id?, completes_at, total_time_s, helps_received }?`.
All changes push `city_update`.

## 9. Edge cases

- Building upgrade completes during training: the running entry is unaffected.
- A promotion whose source troops left the city between client click and
  request: `requirements_not_met`.
- Healing more than is wounded: `invalid_target`. Healing zero troops: `bad_message`.
- Hospital capacity shrinks (cannot happen through play; only by data change):
  keep existing wounded, block new arrivals until under capacity.
- Army returns with lightly wounded while the city is being attacked: they
  become healthy on entry and join the garrison on the next tick.
- Training completes while the city is under attack: new troops join the
  garrison at the start of the next tick.
