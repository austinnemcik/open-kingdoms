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
