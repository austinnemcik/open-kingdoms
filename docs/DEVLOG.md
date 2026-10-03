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
