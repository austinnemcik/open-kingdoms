# Open Kingdoms — agent guide

Open-source, no-microtransaction kingdom strategy game in the style of Rise of
Kingdoms. **This project is built entirely by AI agents.** The owner does not
write code or review PRs, so every change must be self-verified and safe to merge
on its own.

## Layout

| Path | What |
|---|---|
| `server/` | Rust workspace. Authoritative kingdom server. |
| `server/crates/protocol` | Wire messages (JSON over WebSocket). Mirrored in `client/scripts/net/protocol.gd`. |
| `server/crates/data` | Loads + validates `data/*.yaml`. |
| `server/crates/core` | Pure game rules (crate `game-core`). No I/O, no clocks, no RNG: pass `now` and seeds in. |
| `server/crates/kingdom-server` | Networking, sessions, state, persistence. |
| `data/` | All balance numbers (YAML). Never hard-code balance in Rust or GDScript. |
| `client/` | Godot 4.8 project, GDScript only. |
| `client/tests/` | `unit/*_test.gd` (headless), `e2e_login.gd`, `screenshot.gd`. |
| `tools/blender/` | Python scripts that generate all 3D models procedurally in Blender. |
| `docs/` | `DESIGN.md` (game design), `ROADMAP.md` (task queue), `DEVLOG.md`. |

## Tools on this machine

- Rust stable (`cargo`), edition 2024.
- Godot 4.8 (dev6 until 4.8 stable ships): `~/.local/godot/4.8-dev6/Godot_v4.8-dev6_win64_console.exe`. Use the `_console` build so output is captured.
- Blender 5.1: `"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"`.
- `gh` CLI (authenticated), Docker.

## Commands

```bash
scripts/verify.sh                 # MUST pass before every commit (fmt, clippy, tests, Godot unit + e2e)
scripts/verify.sh server|client   # partial runs while iterating

# Run the game locally
(cd server && cargo run -p kingdom-server)          # ws://127.0.0.1:7777/ws
$GODOT --path client                                # client window

# Regenerate 3D models (then re-import Godot so .import files update)
"$BLENDER" -b --factory-startup -P tools/blender/build_buildings.py -- client/assets/models [kind ...]
$GODOT --headless --path client --import

# Visual check: render a city fixture to PNG, then LOOK at it with the Read tool
$GODOT --path client -s res://tests/screenshot.gd -- D:/rok-remake/docs/screenshots/city.png [fixture.json] [camera_distance]
```

## Non-negotiable rules

1. **The server is authoritative.** The client is open source and untrusted. It
   sends *requests*; the server validates everything (costs, timers, ownership,
   rate limits) and sends back state. Never trust a client-sent number.
2. **Game rules live in `game-core`** as pure, deterministic functions with unit
   tests. `kingdom-server` only wires them to the network and storage.
3. **Balance lives in `data/`.** New tunable numbers go in YAML, validated in
   the `data` crate.
4. **Protocol changes touch both sides**: the Rust `protocol` crate and
   `client/scripts/net/protocol.gd`. Bump `PROTOCOL_VERSION` / `VERSION` on
   breaking changes (a consistency test enforces they match).
5. **Every building/unit with a visual has a generated model.** Add a builder to
   `tools/blender/build_buildings.py` (or a sibling script), export to
   `client/assets/models/`, commit the `.glb` and its `.import`. A test checks
   that every building in `data/buildings.yaml` has a model.
6. **No microtransactions, ever.** No premium currency, gacha, paid speedups,
   VIP-for-money, or ads. See `docs/DESIGN.md` for the economy philosophy.
7. **Original assets and names only.** Do not copy Rise of Kingdoms art, text,
   UI layouts, character designs or exact numbers. Mechanics are fine; expression
   is not. Historical figures are fine with our own skills and descriptions.
8. **Tests with every change.** Rust: unit tests next to the code, integration
   tests in `kingdom-server/tests/`. GDScript: `client/tests/unit/*_test.gd`
   extending `TestCase`. Visual changes: take a screenshot and inspect it.

## Conventions

- Rust: `cargo fmt`, clippy clean with `-D warnings`, `thiserror` for library
  errors, `anyhow` only in the binary. Doc-comment public items.
- GDScript: static typing everywhere (`var x: int`, `-> void`), tabs, `class_name`
  for reusable scripts, `##` doc comments. Scenes minimal; build dynamic content in code.
- Commits: small and focused, imperative subject (`Add building upgrade queue`),
  body explaining why. One roadmap task per PR.
- Coordinates: city tiles are integers; 1 tile = 1 world unit; Godot +Y up.

## Autonomous workflow (one run = one roadmap task)

1. `git checkout main && git pull`. Read `docs/ROADMAP.md`, `docs/DESIGN.md` and the last
   entries of `docs/DEVLOG.md`.
2. If an open PR from a previous run exists (`gh pr list`), finish that first:
   fix CI, then merge it. Don't start new work on top of a red main.
3. Pick the **first unchecked** task (`- [ ]`) in the current phase. If it is too
   big for one PR, split it into smaller tasks in ROADMAP.md first and do the first.
4. `git checkout -b task/<id>-<slug>`. Implement with tests.
5. Run `scripts/verify.sh` until green. For visual work, screenshot and look.
6. In the same branch: tick the task in ROADMAP.md (`- [x]`), and append a
   DEVLOG entry (date, task, what changed, anything the next run should know).
7. Commit, push, `gh pr create`, wait for CI (`gh pr checks --watch`), then
   `gh pr merge --squash --delete-branch`. If CI fails, fix and push again.
   If CI cannot run at all (Actions minutes exhausted / billing error, not a
   test failure), merge on a green local `scripts/verify.sh` and note it in DEVLOG.
8. If truly blocked (missing tool, design question only the owner can answer),
   mark the task `- [!]` with a one-line reason, log it in DEVLOG, and move to the
   next task. Never merge red builds, never skip hooks, never force-push main.
