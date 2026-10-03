# 00 — Overview, conventions and system map

These specs turn `docs/DESIGN.md` into implementation-ready rules. **Implement them
literally.** Where a spec and `docs/DESIGN.md` disagree, the spec wins (and says so).
Where two specs disagree, that is a bug in the specs: fix the spec in the same PR.

| File | System | Roadmap phase |
|---|---|---|
| [01-city-economy.md](01-city-economy.md) | Buildings, builders, resources, storehouse, pacing | 1 |
| [02-troops-and-training.md](02-troops-and-training.md) | Troop stats, training, promotion, hospital | 1 (data, training), 3 (wounded rules) |
| [03-research.md](03-research.md) | Modifier system, economy + military research | 1 |
| [04-commanders.md](04-commanders.md) | Commanders, skills, talents, XP, stars | 3 |
| [05-combat.md](05-combat.md) | Battle simulation, rallies, garrisons, reports | 2 (engine, PvE), 3 (PvP), 4 (rallies) |
| [06-world-map.md](06-world-map.md) | Map generation, nodes, barbarians, marches, fog, teleports | 2 |
| [07-alliances.md](07-alliances.md) | Alliances, help, research, territory, chat, mail | 4 |
| [08-events-and-progression.md](08-events-and-progression.md) | Items, quests, Renown, events, leaderboards | 1 (items, quests), 5 (events) |
| [09-kingdom-seasons.md](09-kingdom-seasons.md) | Kingdom lifecycle, migration, seasons | 5 |
| [10-ui-ux-flows.md](10-ui-ux-flows.md) | Every client screen, data shown, messages used | all |
| [11-anti-cheat-and-limits.md](11-anti-cheat-and-limits.md) | Validation, rate limits, bot heuristics | all (5 for heuristics) |
| [ROADMAP_PROPOSAL.md](ROADMAP_PROPOSAL.md) | Phases 2–6 as PR-sized tasks | — |

Machine-readable balance lives next to the specs and is meant to be **copied
verbatim into `data/`**:

| Proposed file | Copy to | Source |
|---|---|---|
| `docs/design/data/buildings.yaml` | `data/buildings.yaml` (replaces the growth-curve schema) | generated |
| `docs/design/data/troops.yaml` | `data/troops.yaml` | generated |
| `docs/design/data/research.yaml` | `data/research.yaml` | generated |
| `docs/design/data/commanders.yaml` | `data/commanders.yaml` | hand-written |
| `docs/design/data/talents.yaml` | `data/talents.yaml` | hand-written |
| `docs/design/data/world.yaml` | `data/world.yaml` | hand-written |
| `docs/design/data/alliance.yaml` | `data/alliance.yaml` | hand-written |
| `docs/design/data/items.yaml` | `data/items.yaml` | hand-written |
| `docs/design/data/progression.yaml` | `data/progression.yaml` | hand-written |
| `docs/design/data/combat.yaml` | `data/combat.yaml` | hand-written |
| `docs/design/data/limits.yaml` | `data/limits.yaml` | hand-written |
| `docs/design/data/seasons.yaml` | `data/seasons.yaml` | hand-written |

Generated files and every `<!-- GEN:… -->` table in these docs come from
`docs/design/tools/okdata.py`. To change a generated number, edit `okdata.py` and
run `python docs/design/tools/build_all.py`; never edit a generated table by hand.
`tools/sim_economy.py` is the pacing simulation (01 §9), `tools/sim_combat.py`
is the reference battle engine (05 §12) and `tools/check_consistency.py` verifies
cross-file consistency (item ids, modifier keys, section references, message catalogue, reward budgets).

## 1. Conventions (binding for every spec)

| Topic | Rule |
|---|---|
| Durations | Integer **seconds** in data and protocol (`time_s`, `duration_s`). |
| Timestamps | **Unix milliseconds, UTC**, `u64`, fields end in `_at` (`completes_at`). The server clock is the only clock; clients interpolate. |
| Server tick | 1 tick = 1000 ms. Combat, march movement and timers advance on ticks. Tick `n` covers `[n·1000, (n+1)·1000)` ms since kingdom epoch. |
| Game day | Resets at **00:00 UTC**. Game week starts Monday 00:00 UTC. |
| Resources | `food`, `wood`, `stone`, `gold`; `u64` whole units. Never negative. |
| Percent values | Plain numbers: `5` means 5 %. Modifier keys end in `_pct`. Stored as `f64`, shown with at most one decimal. |
| Rounding | Costs after discounts: round **up** (`ceil`). Durations after speed bonuses: round **up** to whole seconds, minimum 1 s. Production/gather amounts: round **down** (`floor`). Troop losses: see 05 §5. |
| IDs | Data ids are `snake_case` strings (`city_hall`, `infantry_t4`). Runtime ids (`player_id`, `army_id`, `alliance_id`, …) are `u64`. |
| Coordinates | World tile `(x, y)`, integers, `0 ≤ x,y < 1200`, origin top-left (north-west), `+x` east, `+y` south. Distances are Euclidean in tiles. City-interior tiles are a separate 40×40 grid. |
| Determinism | `game-core` functions take `now`/seeds as arguments. No wall clock, no RNG state. Where randomness is needed the spec names the seed (`splitmix64(seed ^ …)`, 06 §2.1). Combat uses no randomness at all. |
| Levels | 1-based. Level 0 means "not built / not researched". |
| Power | Sum of building, research, troop and commander power (each spec gives its formula). Display only, plus matchmaking for seasons. |
| Names | All names/text are original. Never copy text, numbers or names from Rise of Kingdoms. |

### 1.1 Protocol conventions

All messages are JSON objects with a snake_case `type` (existing convention in
`server/crates/protocol`). Additions used by every spec:

- **Requests** carry a client-chosen `req: u32`. The server answers each request
  with exactly one of `ok { req, … }` (payload documented per message) or
  `error { req, code, message }`, then pushes state changes as normal push
  messages (`city_update`, `army_update`, …). Clients never apply a change
  optimistically except UI affordances (button disabled while waiting).
- **Pushes** have no `req`. Every push that describes an entity carries the
  full entity (not a diff) plus `server_time: u64` (unix ms).
- Error codes are snake_case enums. Shared codes: `bad_message`,
  `not_logged_in`, `rate_limited`, `not_found`, `not_allowed`,
  `insufficient_resources`, `requirements_not_met`, `queue_full`, `invalid_target`,
  `cooldown`, `limit_reached`. A spec may add system-specific codes.
- Message names are listed in each spec's "Protocol" section; the complete
  catalogue is [10 §A](10-ui-ux-flows.md#a-protocol-message-catalogue).
- Bump `PROTOCOL_VERSION` for every roadmap task that adds or changes messages.

### 1.2 Data-file conventions

- Each YAML file has one top-level key naming its content (`buildings:`, `troops:` …).
- Tables are explicit per level (no growth curves) so designers can hand-tune
  any cell. The `data` crate validates on load: ids unique, references resolve,
  levels contiguous from 1, costs/time non-negative, percent values finite.
- The existing `CostCurve`/`TimeCurve` schema in `server/crates/data` is
  **replaced** by `levels: [...]` (01 §2). This is a deliberate schema change.

## 2. System map

```text
                +-------------------+
                |  Account/Renown   |  08: daily objectives, quests, items
                +---------+---------+
                          |
 +-----------+   +--------v--------+   +--------------+
 | Research  +--->   City (01)     <---+  Troops (02) |
 |   (03)    |   | buildings, res. |   | train / heal |
 +-----+-----+   +--------+--------+   +------+-------+
       | Modifiers (03 §1) |  armies          |
       +---------+---------+---------+--------+
                 |                   |
        +--------v-------+   +-------v--------+
        | Commanders (04)|-->|  Combat (05)   |
        +----------------+   +-------+--------+
                                     |
        +----------------+   +-------v--------+   +------------------+
        | Alliances (07) |<->| World map (06) |<->| Seasons (09)     |
        +----------------+   +----------------+   +------------------+
   Anti-cheat and limits (11) wrap every request. UI flows (10) cover every box.
```

Every numeric bonus in the game flows through **one** mechanism, the Modifier
system (03 §1). Buildings, research, commanders, talents, alliance research,
territory, Renown, items and season buffs all contribute `(key, value)` pairs.

## 3. Glossary

| Term | Meaning |
|---|---|
| **Kingdom** | One game world (one server process, one 1200×1200 map). |
| **City** | A player's base. Interior is a 40×40 build grid; on the world map it occupies 3×3 tiles. |
| **CH** | City Hall level (1–25). Gates almost everything. |
| **Builder** | One of the two free construction slots (01 §4). |
| **Troop type / tier** | `infantry`, `cavalry`, `archer`, `siege`; tiers T1–T5 (02). |
| **Army / march** | A group of troops that left the city under up to two commanders. "March" = an army with a movement order. |
| **March slot** | How many armies a player can have outside the city (CH table). |
| **Healthy / lightly wounded / severely wounded / dead** | Troop states (02 §7). |
| **Potency** | Damage coefficient of an attack; a normal attack has potency 100 (05 §3). |
| **Rage** | Per-army meter (0–1000) that triggers the primary commander's active skill (05 §4). |
| **Modifier** | `(key, value)` bonus; see 03 §1. |
| **Renown** | Earned account level that replaces VIP (08 §3). |
| **Stamina** | Earned-only action points spent on PvE attacks (06 §6). |
| **Sculpture** | Commander upgrade material, earned only (04 §5). |
| **Speedup** | Item that removes a fixed number of seconds from a timer (08 §2). |
| **Help** | Alliance action that shortens an ally's timer (07 §4). |
| **Node** | Resource deposit on the world map (06 §4). |
| **Barbarians / Warcamp** | PvE armies / rally-only PvE strongholds (06 §5–6). |
| **Zone** | Outlands (outer), Heartlands (middle), Crown (centre) (06 §1). |
| **Pass** | Gate through a mountain ring, capturable (06 §8). |
| **Sanctum** | Capturable holy site granting a kingdom-wide or alliance buff (06 §9). |
| **Banner / Stronghold** | Alliance flag / alliance fort that project territory (07 §7). |
| **Rally** | Timed group attack merged into one army (05 §8). |
| **Season / Convergence** | Kingdom-vs-kingdom event on a shared map (09). |

## 4. Differences from a monetised game (design guard-rails)

1. Two builders and one research slot for everyone, forever. No paid queues.
2. No premium currency. The only currencies are the four resources, personal
   **alliance credits** (07 §6) and **season medals** (09 §6); none can be bought.
3. Speedups, teleports, shields, sculptures and stamina come only from play
   (08 §2 lists every source and the expected daily amounts the pacing sim uses).
4. Commander acquisition is deterministic: you choose what you unlock; nothing
   is a random draw of power (04 §5).
5. Renown (earned) replaces VIP. Its bonuses are small and capped (08 §3).
6. Pacing target: City Hall 25 in about 3.5 months for an active player and
   about 4 months for a regular one (01 §9), with the first 10 levels inside
   the first three days.

## 5. How specs map to code

| Layer | What goes there |
|---|---|
| `data/*.yaml` + `server/crates/data` | Every table in these specs. Validation rules listed per spec. |
| `server/crates/core` (`game-core`) | Pure rules: cost/time lookup, modifier folding, `City::collect`, queues, combat tick, march geometry, map generation, loot, reward rolls from a seed. |
| `server/crates/kingdom-server` | Sessions, persistence, tick loop, area-of-interest, rate limits, wiring. |
| `server/crates/protocol` + `client/scripts/net/protocol.gd` | Messages from each spec's Protocol section. |
| `client/` | Screens in 10. The client may *display* derived values using the same formulas, but the server's numbers always win. |
