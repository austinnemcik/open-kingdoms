# 05 — Combat

Conventions: [00](00-overview.md). Troop stats: [02](02-troops-and-training.md).
Modifiers: [03 §1](03-research.md). Commanders and skill data: [04](04-commanders.md).
Marches and map objects: [06](06-world-map.md). Constants: [`data/combat.yaml`](data/combat.yaml).
Reference implementation and golden numbers: [`tools/sim_combat.py`](tools/sim_combat.py) (§12).

Combat is a **deterministic, RNG-free** simulation advanced once per server tick
(1 s). It lives entirely in `game-core`: `fn battle_tick(armies: &mut [BattleArmy], ctx: &TickCtx) -> TickLog`.
All arithmetic is IEEE-754 `f64` using only `+ − × ÷ sqrt floor`; identical inputs
give identical outputs on every platform.

## 1. Participants

A **battle army** is anything that fights:

| Kind | Troops | Commanders | Notes |
|---|---|---|---|
| Player army | its groups | primary + optional secondary | 04 §7 |
| Rally army | merged groups of all participants | rally leader's pair | §8 |
| City garrison | all healthy troops in the city + reinforcing armies | owner's garrison pair | §9 |
| Structure garrison | all armies stationed in the structure | the pair of the earliest-arrived army | §10 |
| PvE army (barbarians, Warcamp, guardians) | from `data/world.yaml` | none (fixed skill, 06 §5) | never moves to attack |

Per army the engine tracks: `groups[]` (`troop_id`, `healthy`, `light`, `severe`,
`lost_cum`, `carry: f64`), `rage: u32`, `target: Option<ArmyId>`, `engaged_at_tick`,
`buffs[]`, `attack_count`, `start_healthy` (healthy total when it entered the battle),
and the folded Army-scope modifiers (03 §1.2).

## 2. Engagement rules

- An army with an **attack order** engages when its position is within
  `engage_range` (1.5 tiles) of a target army, or when it reaches the tile ring
  of a target city/structure/PvE object. From the next tick it is `engaged`.
- **Targets.** Every engaged army has at most one `target`:
  - the attacker's target is what it was ordered to attack;
  - an army that is attacked and has no target takes its **earliest attacker**
    (lowest `engaged_at_tick`, then lowest army id) as target;
  - when a target is routed or leaves, an army whose order was to attack it has
    no target any more; if other armies are attacking it, it retargets the
    earliest one, otherwise its battle ends (§7).
- An attacked army **stops moving** and fights where it stands (gatherers pause
  gathering; armies marching home stop). Its owner may order it away (§7.2).
- Any number of armies may attack the same target. An army can be attacked by
  any number of armies but attacks only its one target (plus counterattacks, §3.2).
- Who may attack whom: 06 §12 (shields, alliance membership, zones).

## 3. Damage

### 3.1 Per-tick sequence

At the start of the tick take a **snapshot** of every army's healthy counts,
modifiers and buffs. All damage this tick is computed from the snapshot
(simultaneous), accumulated per victim, then applied (§5). Armies are processed
in ascending army id; this order only matters for floating-point summation order.

For each army `X` with `N_X > 0` healthy troops in the snapshot:

1. **Active skill** (§4): if `X` has a commander, a target, `rage ≥ 1000` and is not silenced,
   resolve the primary commander's active skill (§6), set `rage = 0`, and set
   `secondary_fires_next_tick = true`.
   Else if `secondary_fires_next_tick` and it has a target: resolve the secondary
   commander's active skill and clear the flag.
2. **Normal attack**: if `X` has a living target `T`: `B = base(X, T, 100, normal)` to `T`;
   `attack_count += 1`; rage `+90`.
3. **Counterattacks**: for every army `Y ≠ X` whose target is `X` (and `N_Y > 0`):
   `B = base(X, Y, 100, counter)` to `Y`. Rage `+10` per counterattack, at most `+30` per tick.
   (In a mutual 1-v-1 each side therefore deals one normal attack **and** one counterattack per tick.)
4. **Triggered passives** (§6.3) whose condition became true this tick.
5. **Damage over time** entries owned by `X` tick (§6).

### 3.2 Base damage

```text
size(N)      = sqrt(N)                         if N ≥ 200
             = N / sqrt(200)                   if N < 200          (small armies lose efficiency)
stat(g, s)   = troop[g].s × max(0.1, 1 + (s_pct + <type>_s_pct) / 100)        s ∈ attack, defense, health
A_X          = Σ_g healthy_g × stat(g, attack) / N_X                           (army average attack)
counter(X,T) = Σ_i Σ_j (n_i / N_X) × (m_j / N_T) × c(type_i, type_j)
               c = 1.20 if type_i beats type_j, 0.90 if type_j beats type_i, else 1.00   (02 §1)
F(p)         = max(0.1, 1 + p / 100)

base(X, T, potency, kind) =
      K × (potency / 100) × size(N_X) × A_X × counter(X, T)
    × F(X.damage_dealt_pct [+ X.barbarian_damage_pct if T is PvE])
    × F(T.damage_taken_pct)
    × F(X.<kind>_damage_pct)                 kind ∈ normal, counter, skill
    × F(T.skill_damage_taken_pct)            only when kind = skill
K = 200
```

`garrison_defense_pct` is added to `defense_pct` for a city garrison. All
modifier sums are clamped per the registry (03 §1.5) before use.

### 3.3 From damage to troops

For victim `T` with snapshot counts `m_j` (`M = Σ m_j`) and total incoming damage `D`:

```text
kills_j = D × (m_j / M) / (stat(j, defense) × stat(j, health)) + carry_j
whole_j = min(healthy_j, floor(kills_j))
carry_j = kills_j − floor(kills_j)            (0 if the group was wiped)
healthy_j −= whole_j
```

Diminishing returns come from `sqrt(N)`: doubling an army multiplies its damage
by 1.41, not 2. Several medium armies out-damage one huge army, which is what
makes coordinated swarms and rallies (bigger than any single march) both matter.

## 4. Rage

- Only armies with a primary commander have rage. Range `0…1000`.
- Gains (after §3.1, multiplied by `F(rage_gain_pct)`, floored, then added, capped at 1000):
  `+90` per normal attack, `+10` per counterattack (max `+30`/tick), plus skill effects.
- The active skill fires at the start of the first tick where `rage ≥ 1000`
  (so in a plain 1-v-1 at +100/tick: ticks 11, 21, 31, …).
- Rage persists between consecutive battles while the army stays outside a
  city, and resets to 0 when it enters any city or structure.
- PvE armies have no rage; a PvE "skill" is a `trigger: { every_n_attacks }` passive (06 §5).

## 5. Losses: lightly vs severely wounded

Each troop removed in §3.3 becomes lightly or severely wounded, per group, cumulatively:

```text
lost_cum_j   += whole_j
severe_j      = floor(lost_cum_j × severe_ratio)
light_j       = lost_cum_j − severe_j − healed_j
```

`severe_ratio` by context (`data/combat.yaml`): **0.40** for any battle where
both sides are players (field, city, structure); **0.10** for the player side
of PvE battles; PvE armies' losses are simply removed (no wounded).
What happens to severely wounded afterwards (hospital vs dead) is 02 §7.

Kill credit: `severe` increments on a victim in a tick are credited to the
armies that damaged it that tick, proportional to damage, largest-remainder
method with ties to the lower army id. Credit feeds reports and leaderboards (08 §7).

## 6. Skill effects

Skill data is in `data/commanders.yaml` (04 §3). Every numeric field of an
effect is an array of 5 values indexed by skill level.

### 6.1 Effect types

| `type` | Fields | Resolution |
|---|---|---|
| `damage` | `potency`, `targets` (default 1) | `base(X, T, potency, skill)` to the current target. If `targets > 1`: also to up to `targets − 1` other enemy armies that are attacking `X` or whose position is within 3 tiles of `X`'s target, lowest army id first; each takes the full amount. |
| `dot` | `potency`, `ticks`, `targets` | Registers a damage-over-time entry on each chosen target: on each of the next `ticks` ticks deal `base(X, T, potency, skill)` computed with **that** tick's snapshot. Re-applying the same skill's dot refreshes the duration. Ends if `X` or `T` leaves the battle. |
| `heal` | `potency` | `H = K × potency/100 × size(N_X) × A_X × F(heal_potency_pct)`; for each group `restored_j = min(light_j, floor(H × (light_j / Σ light) / (stat(j,defense) × stat(j,health))))`; move from `light` to `healthy` (`healed_j += restored_j`). No effect on severely wounded. |
| `buff` | `mods: {key: value}`, `ticks` | Adds the modifiers to `X` (Battle scope) for the next `ticks` ticks, starting with the tick after it is applied. |
| `debuff` | `mods`, `ticks`, `targets` | Same, applied to the target(s). |
| `rage` | `amount` | `X.rage += amount` (not multiplied by `rage_gain_pct`; capped at 1000). |
| `rage_drain` | `amount` | `T.rage = max(0, T.rage − amount)`. |
| `silence` | `ticks` | Target cannot fire active skills for `ticks` ticks (rage still accumulates and is kept). |
| `mods` | `mods`, `when` | Permanent passive modifiers (Army scope) while the condition holds (04 §3.2). |

### 6.2 Buff stacking

A buff/debuff instance is identified by `(source army, skill id, effect index)`.
Re-applying the same instance **refreshes** its duration (never stacks).
Different instances stack additively through the Modifier system. Buffs are
removed when their owner leaves the battle; debuffs when either side leaves.
An army carries at most 16 timed instances; when full, the one with the least
remaining time is replaced.

### 6.3 Triggers (passive skills with `trigger:`)

| Trigger | Fires |
|---|---|
| `{ every_n_attacks: n }` | in the tick where `attack_count % n == 0` after a normal attack |
| `{ on_active: true }` | in the same tick, right after the army's primary active skill resolves |
| `{ troops_below_pct: p }` | once per battle, in the first tick whose snapshot has `N < p % × start_healthy` |
| `{ on_battle_start: true }` | on the army's first engaged tick of a battle |

Triggered effects resolve exactly like active effects but never cost or require rage.

## 7. Ending, rout, retreat

### 7.1 Rout

An army whose healthy total reaches 0 is **routed** at the end of that tick:
it leaves the battle, loses its target and all buffs, and marches home at
normal speed carrying only its lightly wounded (which cannot fight). A routed
city garrison means the defence is lost (§9.4). A routed PvE army is defeated
(rewards: 06 §5). If both sides reach 0 in the same tick both are routed and
nobody wins.

### 7.2 Retreat

Any new order from the owner (move, return, gather, attack something else)
makes an engaged army leave the battle at the start of the next tick. In that
tick the leaving army deals no damage, and every army whose target it was
deals one last normal attack to it (**parting blow**, no counterattack, no
rage for either side). Then it moves normally. Pursuers keep their attack
order and chase (06 §11.4). A city garrison and structure garrisons cannot retreat.

### 7.3 Battle end

An army's battle ends when it has no target and nobody targets it. It then:
resolves its severely wounded (02 §7), produces a battle report (§11), and
- if it attacked a city and won: loots and returns home automatically (§9.4);
- if it was gathering: resumes gathering;
- if it was marching (attacked en route): resumes its previous order;
- otherwise: stays **stationed** on its tile until ordered.

After a PvE victory the lightly wounded become healthy immediately (02 §7).

## 8. Rallies

- Requirements: leader has a `war_hall`, is in an alliance, has a free march slot.
- Valid targets: enemy city, enemy alliance structure, Pass/Sanctum (06 §8–9), Warcamp (06 §6).
- `start_rally { target, prep_s ∈ {300, 600, 1800}, army }`: the leader's army
  (with the leader's commander pair) forms in the leader's city and waits `prep_s`.
  One led rally per player at a time. Alliance members see it on the War tab (10 §7.5).
- `join_rally { rally_id, army }`: the member sends an army (commanders are
  ignored for stats but still gain XP and travel with it) to the leader's city.
  It counts as joined when it **arrives**. Armies that have not arrived at launch
  turn around. Total healthy troops (leader + joined + en route) may not exceed
  `rally_capacity(war_hall) × (1 + rally_capacity_pct/100)` using the leader's modifiers;
  a join that would exceed it is rejected (`limit_reached`).
- **Launch** at `prep` end: all arrived contingents merge into one rally army
  that marches at the slowest troop's speed using the leader's `march_speed_pct`.
  The rally launches even if nobody joined. The leader can cancel before launch
  (everyone returns home); the target teleporting/shielding cancels it.
- **In battle** the rally is one army: troop groups are merged by `troop_id`;
  all modifiers and skills are the **leader's** Army scope; `when: rally` conditions are true.
- **Losses** are apportioned to contingents per troop kind proportionally to
  each contingent's share of that kind at launch (largest remainder, ties to
  the lower player id). Severely wounded rules: attacker rows of 02 §7.
- **After the battle** (win or lose) the rally dissolves at the target; each
  surviving contingent marches home on its own. Loot (§9.4) is split by each
  contingent's remaining load capacity. A rally that wins against a structure
  may instead garrison it if the leader chose `occupy: true` at start
  (contingents become stationed armies inside).
- **Reinforcing** (`reinforce { target_city_or_structure, army }`): an army
  enters an ally's city or alliance structure and becomes part of its garrison.
  City limit: `reinforcement_capacity(alliance_hall) × (1 + reinforcement_capacity_pct/100)`
  total hosted troops. The owner of a reinforcing army can recall it any time
  it is not in battle.

## 9. City defence

### 9.1 The garrison army

- Troops: every healthy troop of the owner in the city plus all reinforcing armies, merged by `troop_id`.
- Commanders: the owner's **garrison pair** (set with `set_garrison_commanders`).
  A designated commander who is away on an army is skipped; if the primary is
  away the secondary becomes primary; if neither is home, the highest-level
  commander currently in the city is used; if none, the garrison has no commander.
  Reinforcing armies' commanders give nothing but gain XP.
- Modifiers: owner's Account scope + garrison pair (conditions `garrison`
  true) + `garrison_defense_pct` (wall).
- Its target: the earliest attacker. It cannot retreat and is never "stationed".

### 9.2 Durability and burning

`max_durability = wall_durability(level) × (1 + wall_durability_pct/100)`.
The city stores `durability` (starts at max) and `burning_until`.

- While `now < burning_until`: durability decreases by `max / 9000` per second
  (so 30 min of burning = 20 % of max).
- While not burning: durability regenerates `max / 14400` per second (full in 4 h).
- Both are computed lazily from timestamps.

### 9.3 Watchtower

While the garrison army has a target, the watchtower adds one extra hit per
tick on that target: `B = K × (tower_potency / 100) × 100 × 200 × F(target.damage_taken_pct)`
(kind `normal`, no counter multiplier, no rage). No watchtower = no hit.

### 9.4 Losing and winning

**Attackers all routed or gone** → defence won: garrison battle ends, report.

**Garrison routed** (or the city had zero healthy troops when the first attacker arrived — then this happens on the arrival tick) → defence lost:

1. Severely wounded resolve per 02 §7. Reinforcing armies are routed and march home.
2. **Loot**: each attacking army still engaged, in order of `engaged_at_tick`,
   takes loot from what remains lootable (01 §7), limited by its load.
3. `durability −= 0.20 × max × (1 + siege_share)`, where `siege_share` = fraction
   of siege troops among all healthy attacking troops at that moment.
4. `burning_until = now + 1800 s`.
5. All attackers' battles end; they return home automatically with loot.
6. If `durability ≤ 0`: the city is **razed** — it is teleported to a random
   free tile in the Outlands (seed `splitmix64(kingdom_seed ^ player_id ^ now)`,
   06 §13), incoming marches turn around, `durability = 0.5 × max`, burning stops,
   and the city gets a 4-hour peace shield.

A city can be attacked again immediately after a lost defence (no cooldown) unless razed.

## 10. Structures (alliance Banners/Strongholds, Passes, Sanctums)

- A structure has `durability` (07 §7, 06 §8–9) and an optional garrison (§1).
- While a garrison with healthy troops exists, attackers fight it like a city
  garrison (no watchtower, no wall bonus). Garrison routed → all stationed armies leave for home.
- With no garrison, each attacking army deals per tick
  `S = 4 × size(N) × (1 + 2 × siege_share_of_that_army) × F(structure_damage_pct)` durability damage.
- At `durability ≤ 0`: Banner → destroyed; Stronghold → destroyed (07 §7.4);
  Pass/Sanctum → captured by the alliance that dealt the most durability damage
  in this siege (ties: earliest engaged), durability reset to max (06 §8).
- Structures regenerate `max / 7200` per second when not attacked for 60 s.
- Severely wounded: structure rows in 02 §7.

## 11. Battle report

One report per army per battle (from first engaged tick to battle end), mailed
to the owner (and every rally participant / reinforcing owner), category `battle` (07 §10):

```text
BattleReport {
  id, kind: field | city_attack | city_defense | structure | pve | rally,
  started_at, ended_at, ticks, location: {x, y}, result: victory | defeat | draw | withdrew,
  sides: [ {                      # index 0 = report owner's side
    owner: {player_id, name, alliance_tag?} | {pve_id, level},
    commanders: [{id, level, stars, skill_levels[4]}; 0..2],
    troops: [{troop_id, start, healthy, light, severe, dead, healed}],
    kills: {troop_id: severe inflicted},          # kill credit, §5
    damage: {normal, counter, skill},             # summed base damage dealt
    skills_fired: {skill_id: count},
    power_lost,                                   # Σ (severe + dead-converted) × troop power
  } ; one entry per army that fought on that side ],
  loot?: Resources, commander_xp?: {commander_id: xp}, rewards?: [ItemStack],
  timeline: [{tick, healthy_own_side, healthy_enemy_side}] sampled every 5 ticks (max 240 points)
}
```

`result`: victory = the opposing target routed/destroyed while you survived;
defeat = you were routed; withdrew = you left by order; draw = both routed in the same tick.
The enemy's commander skill levels and exact troop table are always shown in
battle reports (unlike scout reports, 06 §10).

## 12. Worked example (golden test)

Army A: 10,000 `infantry_t4` + 5,000 `archer_t3`. Army B: 12,000 `cavalry_t4`.
Mutual targets, no modifiers. Stats (02 §2): infantry_t4 195/226/236, archer_t3
190/157/165, cavalry_t4 225/195/225.

Tick 1 by hand:

```text
A: N=15000  size=sqrt(15000)=122.4745
   A_A = (10000×195 + 5000×190)/15000 = 193.3333
   counter(A,B) = (10000/15000)×1.20 [inf beats cav] + (5000/15000)×0.90 [cav beats archer] = 1.10
   normal = 200 × 1 × 122.4745 × 193.3333 × 1.10 = 5,209,248.2      (counter hit is identical)
B: N=12000  size=109.5445  A_B=225
   counter(B,A) = (2/3)×0.90 + (1/3)×1.20 = 1.00
   normal = 200 × 109.5445 × 225 × 1.00 = 4,929,503.0               (counter hit identical)
B takes 2 × 5,209,248.2 = 10,418,496.4 → kills = 10,418,496.4 / (195 × 225) = 237.46 → 237 lost, carry 0.46
A takes 2 × 4,929,503.0 =  9,859,006.0
   infantry: 9,859,006.0 × (10000/15000) / (226 × 236) = 123.23 → 123 lost
   archers:  9,859,006.0 × ( 5000/15000) / (157 × 165) = 126.86 → 126 lost
```

Full run from `python docs/design/tools/sim_combat.py` (Example 2 gives A a
commander: active skill = one `damage` effect of potency 600, plus a passive
`infantry_attack_pct +10`). The Rust engine must reproduce these lines exactly;
turn them into unit tests in `game-core`.

<!-- GEN:combat_example -->
```text
== Example 1: no commanders ==
tick   1 A: attack=5209248.2 counter=5209248.2 lost=249 healthy=[9877, 4874] rage=0
tick   1 B: attack=4929503.0 counter=4929503.0 lost=237 healthy=[11763] rage=0
tick   2 A: attack=5170327.2 counter=5170327.2 lost=248 healthy=[9754, 4749] rage=0
tick   2 B: attack=4876313.3 counter=4876313.3 lost=236 healthy=[11527] rage=0
tick   3 A: attack=5131221.6 counter=5131221.6 lost=244 healthy=[9632, 4627] rage=0
tick   3 B: attack=4822845.9 counter=4822845.9 lost=234 healthy=[11293] rage=0
battle ends after tick 64
  A: infantry_t4 healthy=4528 light=3284 severe=2188, archer_t3 healthy=975 light=2415 severe=1610
  B: cavalry_t4 healthy=0 light=7200 severe=4800
== Example 2: A has a commander (active skill potency 600, +10% infantry attack) ==
tick   1 A: attack=5559525.2 counter=5559525.2 lost=249 healthy=[9877, 4874] rage=100
tick   1 B: attack=4929503.0 counter=4929503.0 lost=253 healthy=[11747] rage=0
tick   2 A: attack=5519480.9 counter=5519480.9 lost=248 healthy=[9754, 4749] rage=200
tick   2 B: attack=4872995.8 counter=4872995.8 lost=252 healthy=[11495] rage=0
tick   3 A: attack=5479244.2 counter=5479244.2 lost=243 healthy=[9632, 4628] rage=300
tick   3 B: attack=4816146.9 counter=4816146.9 lost=249 healthy=[11246] rage=0
tick  11 A: attack=5164006.9 counter=5164006.9 skill=30984041.7 lost=216 healthy=[8690, 3742] rage=100
tick  11 B: attack=4358325.9 counter=4358325.9 lost=942 healthy=[8606] rage=0
battle ends after tick 43
  A: infantry_t4 healthy=6214 light=2272 severe=1514, archer_t3 healthy=1874 light=1876 severe=1250
  B: cavalry_t4 healthy=0 light=7200 severe=4800
== Durations (mirror infantry_t4, no commanders) ==
     1000 vs    1000: 78 ticks
    10000 vs   10000: 171 ticks
   100000 vs  100000: 464 ticks
   200000 vs  200000: 642 ticks
```
<!-- /GEN:combat_example -->

The "Durations" block is the pacing reference: a full-march mirror (200k) with
no commanders lasts about 10.5 minutes; commanders roughly halve that.

## 13. `data/combat.yaml`

See [`data/combat.yaml`](data/combat.yaml). All constants named in this spec
(`K`, small-army threshold, counter multipliers, rage numbers, severe ratios,
engage range, structure constant, burn/regen rates, raze shield) are there;
`game-core` reads them from `GameData`, never from literals.

## 14. Protocol

Combat has almost no requests of its own; it is driven by march orders (06 §14).

| Request | Fields |
|---|---|
| `set_garrison_commanders` | `primary?, secondary?` |
| `start_rally` | `target: MapTarget, prep_s, army: ArmySpec, occupy?: bool` |
| `join_rally` | `rally_id, army: ArmySpec` |
| `cancel_rally` | `rally_id` |
| `reinforce` | `target: MapTarget, army: ArmySpec` |
| `get_battle_report` | `report_id` → `ok { report }` |

| Push | Fields | Sent to |
|---|---|---|
| `battle_update` | `army_id, target_id?, healthy, light, severe, rage, buffs: [{skill_id, ticks_left}], last_tick: {dealt, taken, skill_id?}` | owner every tick; observers with the army in view every tick (area of interest, 06 §14) |
| `rally_update` | `rally: {id, leader, target, launches_at, capacity, joined: [{player, troops, arrived}]}` | alliance members; the target if its watchtower `intel_tier ≥ 1` |
| `incoming_update` | `incoming: [{march_id, kind, arrives_at, …fields by intel_tier (01 §3)}]` | defender |
| `mail_new` | report summary (07 §10) | participants |

## 15. Edge cases

- **Order of simultaneous events in a tick**: (1) arrivals/engagement changes
  and retreat flags from orders received before the tick, (2) snapshot,
  (3) damage per §3.1, (4) apply losses, rage, buff timers, (5) routs and
  battle ends, (6) reports/pushes.
- Target routed by someone else earlier in the same tick: damage already
  computed from the snapshot still applies (overkill is discarded by `min`).
- A buff applied in tick `t` affects ticks `t+1 … t+ticks`.
- A silenced army at 1000 rage fires on the first unsilenced tick.
- Army with a commander but zero rage sources (never attacks, never attacked): no rage.
- `targets > 1` when only one enemy exists: only one hit; no splash on allies ever.
- Healing with no lightly wounded: no effect.
- Garrison commander pair changed during a battle: takes effect next tick; rage resets to 0.
- Reinforcement arrives during a city battle: its troops join the garrison
  snapshot from the next tick; `start_healthy` of the garrison increases by the same amount.
- Training/healing completing during a battle: same as reinforcement.
- An army whose owner's shield activates mid-battle: shields cannot be activated
  while any of the player's armies or the city is in battle (06 §12).
- Rally leader goes offline: nothing changes; everything is server-driven.
- Numerical safety: all `F()` factors floor at 0.1; `size(0) = 0`; division by
  `N` or `M` is skipped when 0.
