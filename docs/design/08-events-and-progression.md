# 08 — Items, Renown, quests, events, leaderboards

Conventions: [00](00-overview.md). Data: [`data/items.yaml`](data/items.yaml),
[`data/progression.yaml`](data/progression.yaml). Nothing in this file can be
bought; every reward comes from play.

## 1. Inventory and rewards

```text
Inventory = { item_id: count }            count ≤ 999,999; entries with 0 are removed
Rewards   = { resources?: Resources, items?: {id: n}, alliance_credits?: n, season_medals?: n,
              commander_xp?: n, unlock_commander?: id, city_hall_cost_of_level?: L }
```

`grant(player, rewards, source)` is the single entry point (in `game-core`,
pure): resolves reward tokens (§2.2), adds items/resources, and returns the
concrete list for the UI and the audit log (11 §6). Resources granted directly
go to the stockpile; `resource_*` **items** stay in the inventory until used.
`city_hall_cost_of_level: L` grants the full cost of City Hall level `L` from `buildings.yaml`.
`unlock_commander` on an already unlocked commander grants 10 sculptures of it instead.

## 2. Items

### 2.1 Catalogue and use rules

| Family | Ids | Use |
|---|---|---|
| Speedups | `speedup_<build\|research\|train\|heal>_<5m\|60m\|3h>`, `speedup_universal_<5m\|60m>` | `use_speedup` (01 §10) on a matching timer; universal fits any of the four. Removes the item's seconds, clamped at `now`. |
| Resources | `resource_<food\|wood\|stone\|gold>_<10k\|50k\|500k>` | `use_item`: adds the amount to the stockpile. Stone items need City Hall ≥ 4, gold ≥ 10 (to use, not to hold). |
| Commander XP | `xp_tome_1k / 10k / 50k` | `use_xp_item` (04 §8); XP × `(1 + commander_xp_pct/100)`; rejected at level cap (04 §4). |
| Sculptures | `sculpture_universal_<veteran\|renowned\|legendary>` | `convert_sculptures` (04 §5). |
| Stamina | `stamina_50`, `stamina_100` | adds stamina; may exceed the cap up to `2 × cap` (06 §6). |
| Shields | `shield_8h / 24h / 72h` | `use_shield` (06 §12). |
| Teleports | `teleport_novice / random / territory / targeted` | `teleport` (06 §13). |
| Buffs | `buff_gather_8h` (+25 gather), `buff_production_8h` (+25 all production), `buff_attack_1h` (+5), `buff_defense_1h` (+5) | `use_item`: Account-scope modifiers for the duration. One active buff per `buff_group`; using another of the same group replaces it only if it would end later. |

`use_item { item_id, count }` handles resources, stamina and buffs (count > 1 only
for resources and stamina). `migration_writ` and cosmetics are consumed by their own requests (09). Items cannot be traded, sold or dropped.

### 2.2 Reward tokens (`speedup_any_*`)

Reward tables may name `speedup_any_5m`, `speedup_any_60m` or `speedup_any_3h`.
These are not inventory items. Each unit is resolved at grant time:

```text
h    = hash3(kingdom_seed ^ player_id, 0x616E79, player.token_rolls)      (06 §2.1), then token_rolls += 1
item = weighted pick with unit(h): build 30, research 20, train 30, heal 20   → speedup_<kind>_<duration>
```

### 2.3 Income budget (what the pacing sim assumes)

Minutes of speedups per day. "Any" tokens are split by the weights above.
The sim (01 §9) uses **150 build + 90 research** minutes per day for the active
profile and **90 + 60** for the regular one; universal speedups count as build.

| Source | Active: build | Active: research | Regular: build | Regular: research |
|---|---:|---:|---:|---:|
| Daily objective chests (§4.3) incl. universal | 75 | 30 | 30 | 15 |
| Barbarian drops (06 §5.3; ~20 / ~12 kills per day) | 18 | 12 | 10 | 7 |
| Alliance gifts (07 §6; cap 10 per day) | 22 | 15 | 12 | 8 |
| Weekly events (§5), averaged per day | 26 | 14 | 14 | 8 |
| Renown level rewards (§3), averaged per day | 10 | 5 | 8 | 4 |
| Alliance shop (07 §6), averaged per day | 0 | 14 | 15 | 18 |
| **Total** | **151** | **90** | **89** | **60** |

One-off: the starting inventory (01 §2.1: 50 min build + 50 min universal) plus
chapters 1–5 (§4.2: 40 × `speedup_build_5m`, 24 × `speedup_research_5m`) give
the sim's tutorial grant of 300 build + 120 research minutes.
Training and healing speedups are not part of the City Hall pacing target.

**Sculptures** per week for an active player with Hall of Heroes ≥ 16, in
legendary-equivalents (4 veteran = 2 renowned = 1 legendary):

| Source | Per week |
|---|---:|
| Hall of Heroes daily allowance (3 picks/day, 04 §5) | 21 |
| Daily chest at 100 activity (2 renowned/day) | 7 |
| Alliance shop (5 legendary + what credits remain) | ~8 |
| Weekly event thresholds | 6 |
| Barbarians, Warcamps, Renown, rankings | ~3 |
| **Total** | **~45** |

Any change to a reward table must keep these two budgets (re-run `tools/sim_economy.py` if the speedup totals change).

## 3. Renown

Renown is the earned account level (0–15) that replaces a paid VIP system.

- **Renown points** = activity points earned from daily objectives (§4.3), 1:1,
  so at most 100 per game day. There is no other source and no decay.
- Level `n` needs `100 × n(n+1)/2` cumulative points: 100, 300, 600, 1,000, 1,500,
  2,100, 2,800, 3,600, 4,500, 5,500, 6,600, 7,800, 9,100, 10,500, 12,000.
  A player earning 100/day reaches level 10 on day 55 and level 15 on day 120.
- Bonuses (Account scope, totals at level `n`):

| Key | Value |
|---|---|
| `build_speed_pct`, `research_speed_pct`, `gather_speed_pct` | `min(n, 10)` each |
| `free_finish_flat` | `30 × (n − 1)` seconds for n ≥ 2 (420 at level 15 → free finish 10 min) |
| `train_speed_pct` | `2 × (n − 10)` for n > 10 |
| `stamina_cap_flat` | `20 × (n − 10)` for n > 10 |

- Level-up rewards (one-off, mailed): levels 1–5 one `speedup_build_60m`; levels
  6–10 add one `speedup_research_60m`; levels 11–15 two build + one research;
  `sculpture_universal_legendary` 1 (levels 5–9), 2 (10–14), 3 (15). Exact rows in `progression.yaml`.

## 4. Quests

### 4.1 Counters

All quest systems read the same per-player counters, incremented by `game-core`
when the action is **accepted** by the server:
`login`, `collect_resources`, `start_build`, `start_research`, `start_training`,
`start_healing`, `defeat_barbarian`, `complete_gather_march`, `alliance_help`,
`alliance_donate`, `use_speedup`, `scout_or_explore`, `join_or_start_rally`,
`claim_daily_sculptures`, plus lifetime totals `troops_trained`, `troops_healed`,
`research_levels`, `explored_cells`, `gather_marches`, `max_barbarian_level`.
Daily counters reset at 00:00 UTC; lifetime totals never reset.

### 4.2 Chapters (guided progression)

Nine chapters, one active at a time. Objective kinds: `building_level` (own any
building of that kind at ≥ level), `train_troops`, `heal_troops`, `research_levels`,
`explore_cells`, `gather_marches` (lifetime totals), `defeat_barbarians`
(`max_barbarian_level ≥ min_level`), `commander_level`, `commander_stars` (any
commander), `join_alliance` (currently in one), `alliance_helps` (lifetime).
Objectives already satisfied when the chapter starts are complete immediately.
`claim_objective { chapter, index }` pays `objective_reward`; when all are
claimed, `claim_chapter { chapter }` pays `completion_reward` and activates the next chapter.

| # | Name | Objectives | Completion reward |
|---:|---|---|---|
| 1 | First Stones | Farm 2, Lumber Mill 2, train 50 troops, City Hall 2 | cost of City Hall 3 |
| 2 | Walls and Wards | Storehouse, Scout Camp, Hospital, explore 3 cells, City Wall 2, City Hall 3 | cost of City Hall 4 |
| 3 | Scholars and Allies | Academy, 1 research, Archery Range, Alliance Hall, join an alliance, defeat a barbarian, City Hall 4 | cost of City Hall 5 + commander `hatshepsut` |
| 4 | Heroes of the Hall | Quarry, Hall of Heroes, commander level 5, 2 gather marches, barbarian level 3, City Hall 5 | cost of City Hall 6 + 10 veteran sculptures |
| 5 | Hooves and Watchfires | Stable, Watchtower, 5 research levels, 10 alliance helps, City Hall 6 | cost of City Hall 7 |
| 6 | A Standing Army | 1,000 troops trained, barbarian level 5, 5 gather marches, heal 100 troops, City Hall 7 | cost of City Hall 8 + 10 veteran sculptures |
| 7 | Engines of War | Siege Workshop, 12 research levels, commander level 10, City Hall 8 | cost of City Hall 9 + `teleport_random` |
| 8 | The War Hall | War Hall, barbarian level 8, explore 30 cells, City Hall 9 | cost of City Hall 10 + 5 renowned sculptures |
| 9 | Roads of Trade | Caravan Post, 20 research levels, any commander ★2, City Hall 10 | cost of City Hall 11 + 5 legendary sculptures + `shield_24h` |

The "cost of the next City Hall level" reward is what keeps the first ten
levels inside three days (01 §9); the sim grants exactly this.
After chapter 9 the panel shows only daily objectives and events.

### 4.3 Daily objectives

14 tasks worth 125 activity points in total; activity is capped at 100 per day.
A task's points are added automatically when its counter reaches the target.

| Task | Target | Activity |
|---|---:|---:|
| Log in | 1 | 10 |
| Collect from production buildings | 3 | 5 |
| Start a construction or upgrade | 2 | 10 |
| Start a research | 1 | 10 |
| Start a training batch | 1 | 10 |
| Defeat barbarians | 5 | 15 |
| Complete gather marches | 3 | 15 |
| Help alliance members | 10 | 10 |
| Donate to alliance research | 5 | 10 |
| Use speedups | 5 | 5 |
| Start healing | 1 | 5 |
| Scout or explore | 1 | 5 |
| Join or start a rally | 1 | 10 |
| Claim the Hall of Heroes allowance | 1 | 5 |

Chests (`claim_daily_chest { index }`, each once per day, unclaimed chests are lost at reset):

| Activity | Rewards |
|---:|---|
| 20 | 3 × `speedup_build_5m`, 2 × `resource_food_10k`, 2 × `resource_wood_10k` |
| 40 | 3 × `speedup_research_5m`, 3 × `speedup_train_5m`, 3 × `xp_tome_1k` |
| 60 | 3 × `speedup_build_5m`, 1 × `stamina_50`, 5 × `xp_tome_1k` |
| 80 | 3 × `speedup_research_5m`, 3 × `speedup_train_5m`, 1 × `speedup_universal_5m` |
| 100 | 6 × `speedup_build_5m`, 2 × `speedup_universal_5m`, 2 × `sculpture_universal_renowned` |

The regular profile is assumed to reach 70 activity (three chests).

## 5. Events

### 5.1 Framework

```text
EventDef  { id, name, scoring, thresholds[3], bracketed, start, end }
EventState per player: { event_instance, bracket, points, claimed: [bool; 3] }
```

- An event instance is `(id, start_at)`. A player's **bracket** is fixed at the
  first point scored: City Hall ≤ 9 / 10–16 / 17–21 / 22–25, with threshold
  multipliers ×1 / ×4 / ×12 / ×30 when `bracketed`.
- Three personal thresholds; `claim_event_reward { event, index }` until 24 h after the end.
- Ranking per bracket (top 50 rewarded), final at event end, mailed.
- Scoring happens server-side when the underlying action completes.

### 5.2 Weekly rotation (all times 00:00 UTC)

| Event | Days | Points | Thresholds (bracket ×1) |
|---|---|---|---|
| The Muster | Mon–Tue | power of troops trained or promoted (power gained) | 2,000 / 10,000 / 30,000 |
| The Great Hunt | Wed–Thu | 10 × barbarian level per kill; 200 × level per Warcamp rally victory | 300 / 1,000 / 2,500 (not bracketed) |
| Harvest Day | Fri | load units brought home by gather marches ÷ 1,000 | 100 / 400 / 1,000 |
| Great Works | Sat–Sun | building + research power gained | 500 / 2,000 / 6,000 |
| The Clash (replaces Great Works every 4th week, counted from the kingdom epoch week) | Sat–Sun | kill points (§7) | 2,000 / 10,000 / 40,000 |

Threshold rewards (every event): 1st 3 × `speedup_build_5m` + 2 × `speedup_research_5m`;
2nd 3 × build + 1 × research + 1 × `sculpture_universal_renowned`;
3rd 3 × build + 2 × research + 1 × `sculpture_universal_legendary`.
Ranking: rank 1 → 5 legendary sculptures + badge; 2–10 → 3 + badge; 11–50 → 1.
Badges are cosmetic profile icons.

### 5.3 One-off world rewards

First capture of each Pass / Shrine / Sanctum / Great Sanctum / Throne by an
alliance: every member who was online in the previous 24 h is mailed the
`first_capture_rewards` row (50–500 alliance credits, plus `speedup_any_60m` or
legendary sculptures for the larger sites) and the alliance receives a tier-5 gift (07 §6).

Season events are specified in 09.

## 6. Milestones

Lifetime achievements shown on the profile: ten ladders (power, City Hall,
troops trained, barbarians defeated, resources gathered, research levels,
commander levels, alliance helps, kill points, cells explored), each with five
steps at ×1 / ×5 / ×25 / ×100 / ×500 of a base value. Rewards are **cosmetic
only** (profile titles and frames), so they sit outside both budgets in §2.3.
Base values: power 10,000; City Hall steps are 5/10/15/20/25; troops 1,000;
barbarians 20; gathered 500,000; research levels 5/25/75/150/300; commander
level (highest) 10/20/30/40/50; helps 100; kill points 10,000; cells 20/100/500/2,000/6,400.

## 7. Leaderboards

- Boards: `power`, `city_hall` (level, then earliest time reached), `kill_points`,
  `barbarians_defeated`, `resources_gathered`, `alliance_power`, `alliance_kill_points`,
  plus one board per running event and bracket.
- **Kill points** = Σ over credited severely wounded enemy **player** troops (05 §5) of that troop's power (02 §2).
- Rebuilt from player rows every 300 s into an in-memory top 100; `get_leaderboard { board, page }`
  → 50 rows per page plus the caller's own rank and value (rank computed by count query; cached 300 s).
- Banned or deleted accounts are excluded.

## 8. Protocol

Requests: `get_inventory`, `use_item`, `use_speedup` (01 §10), `get_quests`
→ `ok { chapter, daily, renown }`, `claim_objective`, `claim_chapter`,
`claim_daily_chest`, `get_events` → `ok { events: [EventView] }`,
`claim_event_reward`, `get_leaderboard`.

Pushes: `inventory_update { items }` (full inventory, after any change),
`quest_update { chapter, daily, renown }` (throttled to once per second),
`event_update { event }`, `rewards_granted { source, rewards }` (drives the reward pop-up).

## 9. Edge cases

- A chest threshold reached exactly at reset: the claim is evaluated against the day in which the request arrives.
- Renown points above level 15 keep accumulating (display only).
- Using a speedup larger than the remaining time is allowed (excess wasted); `count` is clamped so that at most one item is wasted.
- Event points scored after the end tick are ignored even if the action started before.
- Player changes bracket mid-event (City Hall upgrade): bracket stays fixed.
- Unlock via chapter 3 when `hatshepsut` is already owned: 10 sculptures of it (§1).
- Inventory stack would exceed 999,999: the excess is discarded and logged.
