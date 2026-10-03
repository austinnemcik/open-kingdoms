# Roadmap proposal — Phases 2–6

Proposed replacement for the outline sections of `docs/ROADMAP.md`. Each task
is one PR, in dependency order; the list format matches the roadmap so the
tasks can be pasted in as they are. **Accept** = acceptance criteria that the
PR's tests must demonstrate. **Spec** = the section to implement literally.
Every task that adds messages also updates `protocol.gd`, bumps the protocol
version and extends the catalogue test (10 §A). Every task ends with
`scripts/verify.sh` green.

## Phase 1 amendments (apply while doing the existing P1 tasks)

These do not add tasks; they pin down what the existing ones must build.

| Task | Amendment | Spec |
|---|---|---|
| P1-03 | Add the `req` / `ok` / `error` request convention and `server_time` on pushes | 00 §1.1 |
| P1-04 | Replace the growth-curve schema by explicit `levels:`; copy `docs/design/data/buildings.yaml` to `data/`; 10 h production buffers, uncapped stockpile, `game_data` message | 01 §2, §6, §10 |
| P1-05 / P1-06 | Requirements, 50 % cancel refund, free finish, move building; all 19 buildings (7 new models per rule 5 of CLAUDE.md) | 01 §3–4 |
| P1-10 / P1-11 | Copy `troops.yaml`; batch caps, promotion, upkeep, dismiss | 02 §2–5 |
| P1-12 | Copy `research.yaml`; modifier registry with clamps and scopes; `get_modifier_breakdown` | 03 |
| P1-16 | Port `docs/design/tools/sim_economy.py` to Rust against `game-core`; CI asserts the acceptance window (active City Hall 25 on day 95–115, City Hall 10 before day 3) | 01 §9 |
| new **P1-17** | Items and inventory: `items.yaml`, `grant()`, `use_speedup`, `use_item`, starting items | 08 §1–2 |
| new **P1-18** | Quests: counters, chapters 1–9, daily objectives and chests, Renown levels and modifiers; quest panel | 08 §3–4, 10 §3.11 |
| new **P1-19** | Rate limits and validation pipeline (buckets from `limits.yaml`, field limits, audit table with exactly-once source keys) | 11 §2–4, §6 |

## Phase 2 — World map and PvE

Goal: a player can explore, gather, and fight barbarians on a shared map.

- [ ] P2-01 Map generation in `game-core`
  - Accept: `generate_map(seed)` implements hash, noise, rings, spokes, passes, clearings and connectivity; tests: fixed checksum for seed 1, all 16 pass centres are `pass`, every walkable tile reachable from the Throne, walkable share 55–80 %; runs < 2 s in release.
  - Spec: 06 §1–2; data `world.yaml` loaded and validated by the `data` crate.
- [ ] P2-02 Map objects, footprints and city placement
  - Accept: object index with free-tile rule; new accounts spawn by the province rule; 1,000 simulated spawns never overlap; city position persisted.
  - Spec: 06 §3, §13 (spawn only).
- [ ] P2-03 Area-of-interest protocol
  - Accept: `map_view`, `map_chunk`, `map_objects`, `map_object_update/remove`, `get_map_overview`; integration test with two clients: object changes reach only subscribed sessions; LOD filters applied.
  - Spec: 06 §14.
- [ ] P2-04 Client world scene: terrain chunks and camera
  - Accept: `world.tscn` renders chunks from `map_chunk` (mesh per chunk, terrain colours, mountains/water models), pan/zoom with debounced `map_view`, City/World toggle; screenshot reviewed.
  - Spec: 10 §2, §5.1.
- [ ] P2-05 Client map objects and kingdom overview
  - Accept: cities, nodes, barbarians rendered with level plates; tap pop-ups (read-only actions for now); LOD 2 overview from `get_map_overview`; models generated in Blender for node types, barbarian camp, map city.
  - Spec: 10 §5.2, §5.6.
- [ ] P2-06 Pathfinding
  - Accept: `find_path` with supercover line, A* tie-break rules, smoothing, expansion cap; property test: path never crosses impassable tiles; golden paths for 5 fixed cases; 1,200-tile path < 50 ms.
  - Spec: 06 §11.3.
- [ ] P2-07 Armies and marches (server)
  - Accept: `march` (kind `move`), `order_army`, `recall_army`, march slots and capacity from City Hall, speed formula, analytic position, `army_update`; armies persist across restart.
  - Spec: 06 §11.1–11.2, §11.4 (recall/redirect), 04 §7 (capacity without commanders = base).
- [ ] P2-08 Client marches: composer and army rendering
  - Accept: march composer (troops only), moving banners with path lines, army queue cards, recall/redirect; unit tests with fixtures; screenshot.
  - Spec: 10 §5.3–5.4.
- [ ] P2-09 Resource nodes: spawning and gathering
  - Accept: chunk spawn sweep with seeded picks, densities and level weights; gather formula, load weights, completion, recall, stale removal; sim test: an army gathers the exact expected amount.
  - Spec: 06 §4.
- [ ] P2-10 Combat engine core
  - Accept: `game-core::combat` reproduces `docs/design/tools/sim_combat.py` tick for tick on the worked examples (golden files exported by the script); no randomness; property tests (losses ≤ troops, deterministic).
  - Spec: 05 §1–5, §12; data `combat.yaml`.
- [ ] P2-11 Barbarians
  - Accept: spawn by density and zone level ranges; attack march → engagement → battle ticks → rewards; stamina cost/refund; level gate; reset after 30 s; severe ratio 0.10; hospital intake.
  - Spec: 06 §5–6 (stamina), 05 §5, 02 §7.
- [ ] P2-12 Hospital and healing
  - Accept: wounded table for PvE, capacity overflow → dead, `heal_troops` queue, costs/time, help hooks stubbed; client hospital panel.
  - Spec: 02 §6–7, 10 §3.6.
- [ ] P2-13 Battle reports and mail (system categories)
  - Accept: `BattleReport` stored once; mail list/read/claim/delete; retention rules; client mail screen and report view.
  - Spec: 05 §11, 07 §10.2, 10 §6.
- [ ] P2-14 Client battle overlay and barbarian flow
  - Accept: `battle_update` drives bars and damage numbers; barbarian pop-up with stamina; `search_map`; e2e test: client attacks a level-1 barbarian and receives a report.
  - Spec: 10 §5.5, §5.7.
- [ ] P2-15 Fog of war and scouting
  - Accept: per-player fog bitset, exploration by scouts and armies, server never sends unexplored chunks/objects (integration test with a second client), `scout_explore`, `scout` reports with accuracy rule; scout camp stats.
  - Spec: 06 §10.
- [ ] P2-16 Barbarian drops, reward tokens and event counters
  - Accept: seeded drop rolls reproducible in a unit test; `speedup_any_*` resolution; counters feed daily objectives.
  - Spec: 06 §5.3, 08 §2.2, §4.1.

## Phase 3 — Commanders and PvP

Goal: armies are led by commanders; players can attack each other's armies and cities.

- [ ] P3-01 Commander data and validation
  - Accept: `commanders.yaml`, `talents.yaml`, `progression.yaml` (commanders section) load; validation of effect types, `when` conditions, modifier keys against the registry.
  - Spec: 04 §1–3, §6; 03 §1.5.
- [ ] P3-02 Commander progression (server)
  - Accept: starter choice, unlock, sculptures and conversion, daily Hall of Heroes claim, XP and level caps by stars, star-up, skill upgrade, tomes; all exactly-once.
  - Spec: 04 §4–5, §8.
- [ ] P3-03 Talents
  - Accept: `set_talents` validation (points, prerequisites, ranks), free reset interval, talents folded into Army scope.
  - Spec: 04 §6.
- [ ] P3-04 Commanders in armies
  - Accept: `ArmySpec` with primary/secondary (★3 rule), capacity formula, Army-scope modifiers, commander XP from PvE to both commanders.
  - Spec: 04 §7, 03 §1.2.
- [ ] P3-05 Skills in combat
  - Accept: rage, active skills, passive triggers, all effect types (damage, dot, heal, buff, debuff, rage, rage_drain, silence); golden tests against `sim_combat.py` example 2 and one test per effect type.
  - Spec: 05 §4, §6.
- [ ] P3-06 Client commanders screens
  - Accept: roster, detail (overview, skills, talents), starter choice, Hall of Heroes claim; portraits generated procedurally (original art); fixtures + screenshots.
  - Spec: 10 §4.
- [ ] P3-07 Field PvP
  - Accept: attack on armies, engagement range, multi-army battles with counterattacks to every attacker, chase rules, retreat, kill credit, PvP severe ratio 0.40.
  - Spec: 05 §2, §5, §7; 06 §11.4.
- [ ] P3-08 Shields and attack rules
  - Accept: new-player shield, shield items, removal on hostile orders, war frenzy, marches turned around at shielded cities.
  - Spec: 06 §12.
- [ ] P3-09 City attack and defence
  - Accept: garrison commanders, wall durability and burn, watchtower potency, loot with storehouse protection and load weights, raze → random teleport with shield; wounded table for city fights.
  - Spec: 05 §9, 01 §7, 02 §7.
- [ ] P3-10 Watchtower intel and incoming warnings
  - Accept: `incoming_update` fields by `intel_tier`; client red banner with countdown.
  - Spec: 01 §3, 05 §14, 10 §10.
- [ ] P3-11 Teleports
  - Accept: novice, random, targeted teleports with all requirements; client placement mode.
  - Spec: 06 §13.
- [ ] P3-12 Scout reports on players and PvP report UI
  - Accept: report accuracy by scout camp vs watchtower; report timeline strip; share link in chat (after P4-03, link renders as text until then).
  - Spec: 06 §10.2, 10 §6.
- [ ] P3-13 Balance check: combat sandbox CLI
  - Accept: Rust CLI runs any two army specs and prints the result; CI runs the mirror-match table from 05 §12 and asserts durations within ±1 tick of the Python reference.
  - Spec: 05 §12.

## Phase 4 — Alliances

Goal: players organise, help each other, hold territory and fight together.

- [ ] P4-01 Alliance core
  - Accept: create/search/join/apply/invite/leave/kick/ranks/transfer/succession/disband with every permission check; `alliance_update`; persistence.
  - Spec: 07 §1–3, §11; data `alliance.yaml`.
- [ ] P4-02 Client alliance screens (browser, home, members)
  - Accept: 10 §7.1–7.3 with fixtures and screenshots.
  - Spec: 10 §7.
- [ ] P4-03 Chat
  - Accept: kingdom, alliance, private channels; history; block; coordinate links; chat rate limit and duplicate rule.
  - Spec: 07 §10.1, 11 §4–5, 10 §8.
- [ ] P4-04 Help
  - Accept: `request_help`, `help_all`, help limit from alliance hall + modifier, time reduction formula, credits with daily cap; works for build, research, training, healing.
  - Spec: 07 §4.
- [ ] P4-05 Alliance research and donations
  - Accept: charges with lazy regen, costs, points/funds/credits, immediate level-up with overflow, member modifiers applied/removed on join/leave.
  - Spec: 07 §5.
- [ ] P4-06 Credits, shop and gifts
  - Accept: shop catalogue with weekly limits; gifts with expiry and daily claim cap; client shop/gifts tab.
  - Spec: 07 §6, 10 §7.6.
- [ ] P4-07 Player mail and alliance mail
  - Accept: `send_mail`, `send_alliance_mail` with limits.
  - Spec: 07 §10.2.
- [ ] P4-08 Reinforcements
  - Accept: `reinforce` cities with capacity from alliance hall; reinforcements fight under the host's garrison rules; return on leave/kick.
  - Spec: 05 §9, 07 §8.
- [ ] P4-09 Rallies
  - Accept: start/join/cancel, preparation times, capacity from war hall, leader's commanders and modifiers, launch, loss distribution, reports to every participant; War tab.
  - Spec: 05 §8, 10 §7.5.
- [ ] P4-10 Warcamps
  - Accept: global counts per level, rally-only, stamina per participant, rewards and alliance gift, respawn after 2 h.
  - Spec: 06 §6.
- [ ] P4-11 Strongholds, Banners and territory
  - Accept: placement rules, construction state, territory grid by completion order, connectivity/inactive Banners, bonuses, garrison, destruction and cooldown; property test: territory recompute is order-independent given completion times; client placement preview and territory tint.
  - Spec: 07 §7, 05 §10, 10 §7.7.
- [ ] P4-12 Passes
  - Accept: sealed/guarded/held state machine by kingdom day, guardians, capture by most durability damage, passage only for the holder, 24 h protection, stranded-army rule.
  - Spec: 06 §8, §15.
- [ ] P4-13 Sanctums and the Throne
  - Accept: site states, buff cycling, Account-scope buffs to members, first-capture rewards.
  - Spec: 06 §9, 08 §5.3.
- [ ] P4-14 Caravans
  - Accept: load, tax, daily cap, membership age, caravan map object, delivery after leave.
  - Spec: 07 §9.
- [ ] P4-15 Markers and territory teleport
  - Accept: ten marker slots with permissions; `teleport_territory`.
  - Spec: 07 §8, 06 §13.

## Phase 5 — Kingdom lifecycle

Goal: kingdoms open, age, compete in seasons; operators can run them safely.

- [ ] P5-01 Events framework and weekly rotation
  - Accept: event instances from schedule, brackets fixed at first score, thresholds, per-bracket ranking and mailed rewards; five event scorers; client events screen.
  - Spec: 08 §5, 10 §9.1.
- [ ] P5-02 Leaderboards and profiles
  - Accept: seven boards refreshed every 300 s, own rank, profile view with power breakdown and milestones.
  - Spec: 08 §6–7, 10 §9.2–9.3.
- [ ] P5-03 Kingdom day schedule and info screen
  - Accept: openings driven by kingdom epoch; `get_kingdom_info`; inactive-city removal.
  - Spec: 09 §1.
- [ ] P5-04 Titles
  - Accept: Sovereign automatic; grant/reassign cooldown; cleared on Throne change; modifiers in Account scope.
  - Spec: 09 §3.
- [ ] P5-05 Gateway service
  - Accept: new `gateway` crate (accounts, kingdom directory, signed tickets); kingdom server accepts tickets; client kingdom list.
  - Spec: 09 §2, 11 §9.
- [ ] P5-06 Transfer primitive and migration
  - Accept: lock → export → import → mark moved, idempotent by transfer id; integration test with two kingdom servers; migration requirements and writ cost.
  - Spec: 09 §2, §4.
- [ ] P5-07 Season server mode and map
  - Accept: `--mode season`, 8-sector map overrides, faction alliance rule, shadow alliances, enter/leave.
  - Spec: 09 §5.1–5.4.
- [ ] P5-08 Season scoring, medals and shop
  - Accept: hourly site points, kill-point share, contribution formula, thresholds, rank multiplier, medal shop limits; season screen.
  - Spec: 09 §5.5–6, 10 §9.4.
- [ ] P5-09 Moderation tools
  - Accept: reports, auto-mute rule, moderator requests, sanction ladder, admin CLI; all audited.
  - Spec: 11 §5, §9.
- [ ] P5-10 Automation and feeding heuristics
  - Accept: hourly job producing flags for each signal with unit tests on synthetic logs; audit replay checker.
  - Spec: 11 §6–8.
- [ ] P5-11 Server operations
  - Accept: Docker image, compose file (gateway + kingdom + reverse proxy with TLS), backup/restore script tested in CI, Prometheus metrics (tick histogram, sessions, queue depths), ops guide in `docs/`.
  - Spec: 11 §10.
- [ ] P5-12 Load test
  - Accept: `tools/loadbot` runs 2,000 scripted clients for 10 minutes against a local server; tick p99 < 200 ms; report committed to DEVLOG.
  - Spec: 11 §10–11.

## Phase 6 — Release

- [ ] P6-01 Localisation framework
  - Accept: every UI string through `tr()`; `en.csv` complete; a test fails on missing keys for any data id; pseudo-locale screenshot shows no clipped text.
  - Spec: 10 §1.
- [ ] P6-02 Onboarding
  - Accept: scripted first session following chapters 1–3 with highlights on the next control (no forced modal chains longer than 3 steps); skippable; e2e test completes chapter 1 through the UI.
  - Spec: 08 §4.2, 10 §2.
- [ ] P6-03 Audio
  - Accept: open-licensed (CC0/CC-BY with attribution file) SFX for UI, build, battle, alarms; two music loops; volume settings.
  - Spec: 10 §9.5.
- [ ] P6-04 Settings and accessibility
  - Accept: graphics levels, UI scale 80–140 %, colour-blind-safe troop/rarity palettes (shape + colour), full keyboard navigation of panels, reduced-motion toggle.
  - Spec: 10 §1, §9.5.
- [ ] P6-05 Notifications
  - Accept: in-game notification table complete; optional desktop notification for incoming attacks while the window is unfocused.
  - Spec: 10 §10.
- [ ] P6-06 Moderation and self-hosting guides
  - Accept: `docs/OPERATING.md` and `docs/MODERATION.md`; fresh-machine install test in CI using the Docker compose file.
  - Spec: 11 §5, §9.
- [ ] P6-07 Balance pass with real data
  - Accept: economy sim and combat sandbox re-run against shipped data; pacing window still met; ten mirror and counter matchups documented in DEVLOG.
  - Spec: 01 §9, 05 §12.
- [ ] P6-08 Public alpha kingdom
  - Accept: one hosted kingdom with TLS, backups and metrics; known-issues list; licence and asset attribution pages in the client.
  - Spec: 09 §1.
