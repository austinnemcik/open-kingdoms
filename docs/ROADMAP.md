# Roadmap

The task queue for autonomous agents. Work top to bottom: the first `- [ ]` in
the earliest unfinished phase is next. Each task is one PR. Split a task into
smaller ones (in place) if it is too big. `- [!]` = blocked (reason inline).

Task IDs are stable; reference them in branch names (`task/p1-03-...`) and in DEVLOG.

## Phase 0 — Foundations

- [x] P0-01 Repo layout, licenses, CLAUDE.md, design doc, roadmap
- [x] P0-02 Rust workspace: protocol, data, core, kingdom-server crates
- [x] P0-03 WebSocket server with hello → login → get_city handshake + integration tests
- [x] P0-04 Data-driven buildings (`data/buildings.yaml`) and starting city (`data/start.yaml`)
- [x] P0-05 Godot 4.8 client: login screen, Net autoload, 3D isometric city view, camera rig
- [x] P0-06 Blender procedural model pipeline for all 12 buildings
- [x] P0-07 Test harness: Rust tests, GDScript unit tests, client↔server e2e, screenshot tool
- [x] P0-08 `scripts/verify.sh` and GitHub Actions CI

## Phase 1 — The city

Goal: one player can grow a city from City Hall 1 to 10 by playing.

- [x] P1-01 Authentication: name + password at registration (argon2 hash), session token for reconnects. Reject logins with the wrong password.
- [ ] P1-02 Persistence: SQLite (sqlx or rusqlite, migrations in-repo) behind a `Store` trait; players and cities survive a server restart. Integration test restarts the server.
- [ ] P1-03 Server clock + game time: inject a `Clock` trait so core/server code and tests control time; add a 1s server tick task.
- [ ] P1-04 Resource production: per-level production and capacity in `data/buildings.yaml`; `City::collect(now)` in core (lazy, capped by storage); server sends resources with timestamps so the client can interpolate.
- [ ] P1-05 Upgrade queue (server): `upgrade_building` request; validate resources, City Hall requirement, max level, 2 builder slots; store `completes_at`; complete lazily and on tick; push `city_update`.
- [ ] P1-06 Construct new buildings (server): `build_building {kind, x, y}`; validate footprint, bounds, overlap, `max_count`, unlock level.
- [ ] P1-07 Client: click a building → info panel (name, level, next-level cost/time, Upgrade button); live construction progress bar over the building.
- [ ] P1-08 Client: build menu listing unlockable buildings; placement ghost snapped to the grid, red/green validity, confirm/cancel.
- [ ] P1-09 Client HUD: resource bar with smooth ticking counts, builder queue widget, toast for server errors.
- [ ] P1-10 Troops data: `data/troops.yaml` (infantry/cavalry/archers/siege, T1–T5: attack, defence, health, speed, load, upkeep, cost, time, required building level).
- [ ] P1-11 Troop training: queue per military building, `train_troops` request, completion adds to city garrison; client training panel.
- [ ] P1-12 Research: `data/research.yaml` (economy + military trees with prerequisites and effects); Academy queue; a generic modifier system in core (`Modifiers` summed from research/buildings, applied to production, build speed, troop stats).
- [ ] P1-13 Building visual tiers: Blender builders take a tier (1–5) and produce visibly grander models; client chooses by level.
- [ ] P1-14 City dressing: terrain beyond the city wall (hills, trees, water), roads, a city wall model, decorative props. Screenshot review.
- [ ] P1-15 Web export: Godot web export preset (Compatibility renderer), CI job that builds it, kingdom-server serves the exported client at `/`.
- [ ] P1-16 Balance simulator CLI (`tools/` or a `sim` bin): simulates an active player's first 30 days and prints City Hall level over time; use it to tune `data/` toward the pacing in DESIGN.md.

## Phase 2 — World map (outline: split into tasks when Phase 1 is done)

- Kingdom map generation (1200×1200 tiles, biomes, mountains/rivers, passes) in core, deterministic from a seed
- Chunked map storage and area-of-interest subscriptions over the protocol
- Godot world map scene: terrain chunks, LOD, city/node/barbarian markers, camera zoom levels
- Resource nodes and gathering marches (load, gather speed, return)
- Marches: A* pathfinding, real-time movement, recall, speed modifiers
- Barbarians: PvE targets with levels, rewards
- Combat engine in core: deterministic round-based battles, counters, rage, battle reports
- Fog of war and scouting

## Phase 3 — Commanders and PvP

- Commander data (original skills for historical figures), levels, stars, talent trees
- Primary/secondary commander armies, skills firing in combat
- Attacking cities, wall/garrison defence, hospital and wounded vs dead
- Battle and scout reports UI, mail
- Peace shield, teleports earned by play

## Phase 4 — Alliances

- Alliance create/join/roles, chat (alliance + kingdom), help requests
- Alliance research and gifts
- Flags, forts, territory and resource bonuses
- Rallies and reinforcements; barbarian forts
- Holy sites and passes

## Phase 5 — Kingdom lifecycle

- Kingdom seasons (linked kingdoms, shared zone), events framework
- Migration, kingdom titles, leaderboards
- Admin tools, moderation, anti-bot detection, rate limiting
- Server ops: Docker image, deployment docs, backups, metrics

## Phase 6 — Release

- Audio (open-licensed SFX and music), localisation framework
- Onboarding/tutorial, settings, accessibility
- Load test with bot clients (thousands of simulated players)
- Public alpha kingdom
