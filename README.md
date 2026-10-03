# Open Kingdoms

A free and open-source kingdom strategy game inspired by Rise of Kingdoms.
Build your city, gather across a shared world map, lead historical commanders
and fight with your alliance for the kingdom. **No microtransactions, no
gacha, no pay-to-win.**

![City view](docs/screenshots/city.png)

> Early development (Phase 0 complete). See [docs/ROADMAP.md](docs/ROADMAP.md).
> Not affiliated with Lilith Games or Rise of Kingdoms.

## Stack

- **Server:** Rust (tokio, axum), authoritative, one process per kingdom
- **Client:** Godot 4.8, GDScript, 3D isometric; PC and web first
- **Art:** low-poly models generated procedurally with Blender's Python API
- **Data:** all balance in editable YAML in [`data/`](data/)

## Run it

```bash
# 1. Server
cd server && cargo run -p kingdom-server     # listens on ws://127.0.0.1:7777/ws

# 2. Client (Godot 4.8)
godot --path client                          # enter any name and press Play
```

## Play in a browser

Use Godot **4.8-dev6** and the matching export templates. Download
[`Godot_v4.8-dev6_export_templates.tpz`](https://github.com/godotengine/godot-builds/releases/tag/4.8-dev6)
and install it with Godot's **Editor → Manage Export Templates → Install from File**.
Set `GODOT` to your console executable if it is not on PATH.

From the repository root (Bash, or Git Bash on Windows):

```bash
bash scripts/export_web.sh             # writes ignored build/web/
ROK_WEB_DIR="$PWD/build/web" cargo run --manifest-path server/Cargo.toml -p kingdom-server
```

Open **http://127.0.0.1:7777/** in a browser with WebGL 2 support, enter a
governor name and a password (8–128 characters), and press Play. A new name
registers an account; use the same credentials to return. The browser defaults
to `/ws` on the same host and port (`wss://` on HTTPS). Desktop clients still
default to `ws://127.0.0.1:7777/ws`.

For public hosting, set `ROK_ADDR=0.0.0.0:7777` and put the server behind an
HTTPS reverse proxy that forwards WebSocket upgrades and preserves
`Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Embedder-Policy: require-corp`. Point `ROK_WEB_DIR` only at the
exported build directory. Without it, the server serves only its API routes.
Connection and login limits currently use the TCP peer IP, so players behind
one reverse proxy share its per-IP budgets in `data/server.yaml`.
The CI **web** job also produces an `open-kingdoms-web` artifact: extract it
and point `ROK_WEB_DIR` at the directory containing `index.html`.

## Develop

```bash
scripts/verify.sh   # format, lint, Rust tests, Godot unit tests, client-server e2e
```

This project is developed by AI agents following [CLAUDE.md](CLAUDE.md).
The design is in [docs/DESIGN.md](docs/DESIGN.md) and progress in
[docs/DEVLOG.md](docs/DEVLOG.md).

## License

- Code: [AGPL-3.0](LICENSE). If you run a modified server, share your changes.
- Art, models and data files (`client/assets/`, `data/`): [CC BY-SA 4.0](ASSETS_LICENSE.md).
