# Devlog

Newest entries at the bottom. Each autonomous run appends one entry: date, task
ID, what changed, and anything the next run should know.

## 2026-10-03 — Phase 0 (P0-01 … P0-08)

- Scaffolded the repo: Rust workspace (`protocol`, `data`, `game-core`,
  `kingdom-server`), Godot 4.8 client, Blender model pipeline, CI.
- Handshake `hello → login → get_city` works end to end. Login is name-only and
  state is in memory; P1-01 and P1-02 fix that.
- 12 procedurally generated low-poly building models in `client/assets/models/`.
  Palette colours in the Blender script are sRGB and converted to linear on export.
- Godot 4.8 stable is not out yet: local and CI use `4.8-dev6`. When 4.8 stable
  ships, update `GODOT_VERSION` in `.github/workflows/ci.yml`, the path in
  `scripts/verify.sh` and CLAUDE.md.
- Note: `CityView.render_city()` defers until `_ready` because SceneTree scripts
  (tests) call it before the node enters the tree.
- Note: in this environment, Bash heredocs containing apostrophes sometimes fail
  to parse. Write files with the Write tool instead.

## 2026-10-03 ? P1-01 Authentication

- Protocol v2 requires 8?128 Unicode characters in passwords; new names register
  with randomly salted Argon2id hashes and existing names use constant-time hash verification.
- Random 32-byte base64url bearer tokens resume sessions. Tokens live in memory
  until persistence lands; use TLS at the deployment proxy to protect credentials.
- Hashing runs on blocking workers; pre-auth failures disconnect after five attempts,
  and WebSocket frames/messages are bounded to 4 KiB. Password fields are secret and
  cleared after submission; client tokens are retained only in memory.
- Added password boundary, hash, token, reconnect and WebSocket failure-limit tests.

## 2026-10-03 - P1-02 Persistence

- Chose bundled rusqlite: a small synchronous Store trait and existing blocking
  workers avoid blocking Tokio without adding an async SQL framework. SQLite uses
  WAL, foreign keys, FULL durability, and checked-in transactional migrations.
- Players, Argon2id credentials, bearer sessions and serialized cities persist in
  ROK_DB (default kingdom.db). Registration is atomic; the database is authoritative.
- Tests cover migrations, duplicate registration, foreign keys, city writes, and
  real binary restart with password login and token resume. E2e uses :memory: so
  verification never modifies a developer's persistent kingdom.

## 2026-10-03 - P1-03 Clock

- Added injected Clock, RealClock and ManualClock; all game timestamps are Unix
  seconds. Starting cities receive explicit time, persisted with a legacy default.
- Server lifetime owns a one-second tick loop with missed-tick skipping; tick work
  runs off-runtime and stops with the server. It is the hook for timer completion.
- Unit tests check clock semantics and city timestamps; a WebSocket integration
  test verifies a manual clock drives successive real server ticks.

## 2026-10-03 - P1-04 Resource production

- Added validated per-level production/storage curves and minute-scale early pacing.
- Pure lazy collection retains fractional numerators, caps production, handles
  backwards/extreme clocks, and initializes legacy cities without epoch windfalls.
- City snapshots expose per-hour rates, capacity and Unix-second as_of; collected
  state persists before replying. Added deterministic economy and WebSocket tests.

## 2026-10-03 — UI visual system (design sub-agent, not a roadmap task)

- Added the UI kit under `client/ui/`: project-wide theme (`theme/main_theme.tres`,
  set as `gui/theme/custom`), Cinzel + Nunito fonts (OFL), 38 icons, and widgets
  in `ui/widgets/` (ResourceBar/ResourceChip, TimerProgressBar, IconButton,
  PanelFrame, Toast, ConfirmDialog, CostRow). `UiFormat` does "12.4K" and
  "02:13:05" formatting; `UiIcons` and `UiColors` are the lookups.
- `docs/UI_STYLE.md` is the style guide. References to build against:
  `docs/screenshots/ui_showcase.png` and `docs/screenshots/ui_hud_mock.png`
  (P1-07 to P1-09 should compose the HUD from these widgets, as in
  `client/ui/hud_mock.gd`).
- All art is generated: `tools/ui/build_all.sh` runs the texture and icon
  scripts (Python: resvg-py, Pillow, numpy), re-imports and rebuilds the theme
  with `client/ui/theme/build_theme.gd`. Do not hand-edit the `.tres`.
- The theme now applies to every Control, including the existing login screen:
  default labels are cream (meant for dark surfaces); use the `...Ink` label
  variations on parchment.
- Note: icon `.import` files have mipmaps enabled by `build_icons.py`; draw icons
  with `UiIcons.make_rect` so they downscale cleanly.
- Note: `client/ui/icons/svg/` has a `.gdignore` so Godot does not import the
  SVG sources a second time.
- Note: to screenshot UI larger than the monitor, `client/ui/screenshot_ui.gd`
  renders the scene in a SubViewport.
## 2026-10-03 - P1-05 Upgrade queue

- Added atomic upgrade costs/reservations, two free builders, max-level/City-Hall
  gates and data-driven prerequisites (Hall N requires Barracks N-1).
- Persisted jobs finish lazily or on the one-second tick. Collection splits at
  completion boundaries; owner sessions receive persisted full city_update snapshots.
- Cancellation returns the full recorded cost, configurable in YAML, including
  over-cap refunds. Exact-deadline completion wins. Godot Net updates GameState.
- Added pure rule/edge tests plus WebSocket tests for queues, cancellation,
  owner isolation, timer pushes and restart completion.

## 2026-10-03 - P1-06 New construction

- Added build_building with authoritative kind/unlock/count/footprint/overlap/cost/
  builder checks, overflow-safe coordinates and monotonic IDs. Jobs persist and
  use the existing completion tick, notifications and full-refund cancellation.
- Pending buildings are level zero with under_construction state and timestamps;
  they reserve tiles/count/slots but produce nothing until completion. Cancelling
  removes them and releases the reservation.
- Extended pure rule and WebSocket tests for construction, cancellation, boundary
  coordinates, ownership and restart completion. Godot e2e renders a level-zero farm.
- Full client build/upgrade UI remains P1-07/P1-08; audit hardening remains P1-H1.

## 2026-10-03 — Design specs (`docs/design/`)

- Added implementation-ready specs `docs/design/00`–`11` plus
  `ROADMAP_PROPOSAL.md` (Phases 2–6 as PR-sized tasks, and amendments to the
  existing Phase 1 tasks). Docs only; no code or `data/` changes.
- Proposed balance data lives in `docs/design/data/*.yaml` and is meant to be
  copied into `data/` by the task that implements each system. The building
  schema changes from growth curves to explicit `levels:` (00 §1.2, 01 §2), and
  there are 19 buildings instead of 12 (7 new models needed).
- `buildings.yaml`, `troops.yaml`, `research.yaml` and every `<!-- GEN:… -->`
  table are generated: edit `docs/design/tools/okdata.py`, then run
  `python build_all.py` in that folder. Never hand-edit generated tables.
- `tools/sim_economy.py` is the pacing sim (active player City Hall 25 on day
  ~105, regular ~126; City Hall 10 on day 2–4). `tools/sim_combat.py` is the
  reference battle engine whose output the Rust engine must reproduce (P2-10).
  `tools/check_consistency.py` checks item ids, modifier keys, section
  references, the message catalogue and the speedup budget; run it after any
  spec edit. All three need Python 3 with `pyyaml`.
- Next run: the roadmap itself is unchanged. Paste the tasks from
  `ROADMAP_PROPOSAL.md` into `ROADMAP.md` when a phase starts, and apply the
  "Phase 1 amendments" table to the remaining Phase 1 tasks.
- Known gaps: the specs were written in parallel with P1-01 … P1-05, which
  already merged with different choices in places: timestamps are Unix seconds
  (spec: milliseconds), cancel refunds the full cost (spec: 50 %), City Hall
  prerequisites and the production/storage model differ from 01. Reconcile
  these (change code or spec) before building further on them.

## 2026-10-03 — P1-13 + P1-14: art style foundation, building tiers, city dressing

- New art pipeline, all generated: `tools/blender/gen_textures.py` paints a shared
  2048² atlas plus ground textures (system Python, numpy + Pillow);
  `tools/blender/okkit.py` is the modelling kit (UV-mapped primitives, roofs,
  towers, props, baked vertex AO); `build_buildings.py` now builds all 12
  buildings in 5 tiers (`<kind>_t<tier>.glb`, old `<kind>.glb` removed);
  `build_scenery.py` builds the city wall, terrain, forests and props into
  `client/assets/models/scenery/`. `scripts/build_art.sh` regenerates everything.
- `docs/ART_BIBLE.md` is the style guide: palette, scale, tiers, budgets, naming.
  Read it before touching art.
- Client: `BuildingFactory.create(kind, footprint, level)` picks the tier
  (`tier_for_level`, falls back to lower tiers). Generated models carry no
  materials; `apply_atlas` gives them the shared `assets/materials/atlas.tres`.
- City dressing: `CityDressing` node (terrain with `ground.gdshader`, water,
  wall, forests, props) and `CityRoads` (pure: avenues, plaza, door paths, road
  mask, prop placement). Decoration only; the whole 40x40 grid stays buildable
  and the server knows nothing about it.
- `city.tscn` has new lighting/environment (warm sun, cool ambient, fog, glow);
  `project.godot` gets a 4096 shadow map and soft shadow filtering.
- `repo_consistency.rs` now requires all 5 tier models (+ `.import`) per building.
- Fixtures: `showcase_city.json` (tiers 1–3) and `grand_city.json` (tiers 4–5).
  Screenshots in `docs/screenshots/`.
- Notes for the next run:
  - `scripts/build_art.sh` takes well under a minute; when filling Blender meshes
    from Python use `foreach_set`, per-loop access is quadratic in Blender 5.1.
  - Texture `.import` files have `mipmaps/generate=true` set by hand; keep that
    if a texture is ever re-imported from scratch.
  - `screenshot.gd` accepts `[focus_x] [focus_z]` after the camera distance.
  - Ideas not done: bridges where the gate roads meet the river, animated
    flags/water wheel, tier-up construction scaffolding, LOD for the forest.
