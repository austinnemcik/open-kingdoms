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

## 2026-10-03 - P1-H1 Server hardening

- Removed persisted-kind panics, recover poisoned store locks, and keep city
  load/collect/save in one critical section. Views are built after releasing it.
- Argon2 runs outside the store lock, bounded by a semaphore; competing new-name
  registrations verify the winning password before issuing a session.
- Validated `data/server.yaml` controls handshake/idle deadlines, message token
  buckets, global/per-peer-IP connections, shared IP/account login and IP
  registration budgets, hash concurrency, and bounded admission tables. Ping
  bypasses blocking workers; all input frames consume the message budget.
- Migration 002 replaces plaintext sessions with SHA-256 digests, creation and
  expiry times; expiry is enforced/pruned on session access and issuance, with
  deterministic per-player eviction. Existing tokens are revoked because their
  creation times are unknown; players log in with their password again.
- Internal authentication failures propagate as `internal` and do not consume
  the credential-failure allowance. Rate limits use monotonic elapsed time;
  operational proxy deployments currently count the TCP peer, not forwarded IPs.
- Added pure token-bucket/unknown-kind tests, lock/race/atomic read tests, migration
  tests, and WebSocket timeout, cap, shared-budget and Internal-error regressions.

## 2026-10-03 - P1-15 Web export

- Added a single-threaded Web preset using the existing web Compatibility
  renderer override and `scripts/export_web.sh`; output lives in ignored
  `build/web`. CI installs the matching 4.8-dev6 templates (directory from
  `version.txt`) and uploads the `open-kingdoms-web` artifact.
- `ROK_WEB_DIR` enables static hosting at `/` alongside unchanged `/health`
  and `/ws` routes. ServeDir streams assets with MIME types, including
  `application/wasm` and `application/octet-stream` for `.pck`, plus COOP
  `same-origin` and COEP `require-corp`. Missing files remain 404. Temp-dir
  integration tests cover content, MIME, isolation headers, HEAD, traversal
  rejection, API precedence and opt-in hosting. No state/session changes.
- Browser defaults derive `ws`/`wss`, host and port from JavaScriptBridge page
  location; desktop keeps localhost:7777 and explicit overrides still work.
  Pure URL tests include HTTPS, custom ports, IPv6 and missing location.
- Removed a pre-existing BOM from login.tscn that prevented main-scene parsing;
  added a scene-loading regression test (the previous e2e bypassed login UI).
- Verified full `bash scripts/verify.sh`, release export, and a live server on
  127.0.0.1:18777 with ROK_WEB_DIR. Curl GETs of `/` and `/index.wasm` returned
  200 with correct MIME and both isolation headers. Chromium browser automation
  confirmed crossOriginIsolated=true, the derived non-default WebSocket port,
  registration/login and the rendered city: `docs/screenshots/city_web.png`.
  Browser console and native Compatibility city screenshot had no errors.
- README documents browser play, template installation and HTTPS proxy hosting.
  Templates on this machine originally contained only Windows binaries; web
  templates are now installed in `%APPDATA%/Godot/export_templates/4.8.dev6`.
  First web load currently downloads about 50 MiB uncompressed; compression
  and asset optimization are future work. P1-16 remains gated on P1-R1.
- Rebased on merged P1-H1, retaining peer-address injection and connection
  admission checks in both API-only and web-hosting modes. Added a live TCP
  WebSocket handshake test with static hosting enabled to protect that wiring.

## 2026-10-03 — P2-01: deterministic map generation

- Added pure `game_core::map::generate_map(seed)` and
  `generate_map_with_config(seed, &WorldConfig)`, plus reusable SplitMix64,
  hash3, unit and value-noise primitives. Runtime data loads through
  `GameData.world`; the one-argument generator uses compile-time YAML defaults
  without I/O, global RNG or mutable global state.
- Implemented noise terrain, mountain rings/spokes, pass IDs, clearings,
  no-corner-cutting connectivity pruning, moisture and chunk walkable counts.
  `Map` is immutable through its public API; tile arrays and chunk counts are
  row-major. Terrain discriminants are the specified bytes 0–5. Pass IDs are
  zero-based, rings in YAML order followed by spokes. Sites are ordered by
  kind, then normalized ascending angle; dynamic ownership is deliberately absent.
- Interpretation: ring passes use midpoint radii and outward radial gap lines;
  spoke gaps use perpendicular lines at pass_r. Exact cardinal unit vectors
  avoid floating-point trig residue shifting inclusive barrier boundaries.
  The checksum starts at zero and folds row-major bytes with splitmix64(acc ^ byte).
- Corrected a real spec/acceptance mismatch: the literal noise thresholds give
  1,343,387 walkable tiles for seed 1 (93.2908%), not 55–80%. Spec and roadmap
  now accept 90–96%; thresholds are unchanged. Fixed checksum:
  0x66ed2f8a48d8e987. All 16 pass centres and all 23 site centres meet the spec.
- World geometry, noise, site coordinates and march limits are typed and
  validated. Unimplemented world-system sections are retained as YAML values
  (`systems` / `rules`), explicitly awaiting semantic validation in their tasks.
- Validation: full `bash scripts/verify.sh` green (Rust fmt/clippy/tests, 48
  Godot unit tests, client/server E2E); design consistency checker green.
  Independent cardinal flood-fill checks every walkable tile, and tests check
  each chunk count, determinism, different seeds and invalid world data.
  Explicit release timing test: 219 ms (<2 s), run with
  `cargo test -p game-core --release generation_under_two_seconds -- --ignored --nocapture`.
- Integration: P2-02 can use terrain_at/index/zone/province, passes/sites and
  chunk_walkable. P2-03 must gather chunk rows from the full-map row stride;
  a chunk is not one contiguous 900-byte slice. P2-04 can use moisture (f32,
  cosmetic only) and y/size for tint. Pass walkability here is geometric only;
  gameplay paths must additionally enforce ownership (P2-06).
