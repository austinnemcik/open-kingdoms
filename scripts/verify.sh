#!/usr/bin/env bash
# Single source of truth for "is the repo healthy?". Run locally and in CI.
# Every change must leave this passing.
#
#   scripts/verify.sh            # everything
#   scripts/verify.sh server     # Rust only
#   scripts/verify.sh client     # Godot only (unit + e2e; builds the server)
#
# Env: GODOT = path to a Godot 4.8 binary (console build on Windows).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHAT="${1:-all}"

find_godot() {
  if [[ -n "${GODOT:-}" ]]; then echo "$GODOT"; return; fi
  for c in godot4 godot \
    "$HOME/.local/godot/4.8-dev6/Godot_v4.8-dev6_win64_console.exe"; do
    if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then echo "$c"; return; fi
  done
  echo "error: Godot not found; set GODOT=/path/to/godot" >&2
  exit 1
}

step() { printf '\n==> %s\n' "$*"; }

verify_server() {
  cd "$ROOT/server"
  step "cargo fmt --check"
  cargo fmt --all -- --check
  step "cargo clippy"
  cargo clippy --all-targets --quiet -- -D warnings
  step "cargo test"
  cargo test --quiet
}

verify_client() {
  local godot
  godot="$(find_godot)"
  cd "$ROOT/client"
  step "godot import"
  "$godot" --headless --path . --import >/dev/null 2>&1 || true
  step "godot unit tests"
  "$godot" --headless --path . -s res://tests/run_tests.gd 2>&1 | tee /tmp/rok-unit.log
  if grep -qE "SCRIPT ERROR|Parse Error" /tmp/rok-unit.log; then
    echo "error: GDScript errors during unit tests" >&2
    exit 1
  fi

  step "end-to-end: client <-> server"
  (cd "$ROOT/server" && cargo build --quiet -p kingdom-server)
  local port=$((20000 + RANDOM % 20000))
  local bin="$ROOT/server/target/debug/kingdom-server"
  [[ -x "$bin.exe" ]] && bin="$bin.exe"
  ROK_ADDR="127.0.0.1:$port" RUST_LOG=warn "$bin" &
  local server_pid=$!
  trap 'kill $server_pid 2>/dev/null || true' RETURN
  for _ in $(seq 50); do
    curl -sf "http://127.0.0.1:$port/health" >/dev/null && break
    sleep 0.1
  done
  "$godot" --headless --path . -s res://tests/e2e_login.gd -- "ws://127.0.0.1:$port/ws"
}

case "$WHAT" in
  server) verify_server ;;
  client) verify_client ;;
  all) verify_server; verify_client ;;
  *) echo "usage: $0 [all|server|client]" >&2; exit 2 ;;
esac

printf '\nverify: OK (%s)\n' "$WHAT"
