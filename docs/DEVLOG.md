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
