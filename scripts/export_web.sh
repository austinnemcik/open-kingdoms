#!/usr/bin/env bash
# Export the Compatibility web client. Install matching Godot templates first.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${GODOT:-}" ]]; then
  for candidate in godot4 godot \
    "$HOME/.local/godot/4.8-dev6/Godot_v4.8-dev6_win64_console.exe"; do
    if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
      GODOT="$candidate"
      break
    fi
  done
fi
: "${GODOT:?Godot not found; set GODOT=/path/to/godot}"
mkdir -p "$ROOT/build/web"
"$GODOT" --headless --path "$ROOT/client" --rendering-method gl_compatibility --import
"$GODOT" --headless --path "$ROOT/client" --rendering-method gl_compatibility \
  --export-release Web "$ROOT/build/web/index.html" 2>&1 | tee "$ROOT/build/export-web.log"
# Godot can report script/resource errors while returning a successful exit code.
if grep -qE 'ERROR:|SCRIPT ERROR|Parse Error' "$ROOT/build/export-web.log"; then
  echo "error: Godot reported errors during web export" >&2
  exit 1
fi
test -s "$ROOT/build/web/index.html"
test -s "$ROOT/build/web/index.wasm"
test -s "$ROOT/build/web/index.pck"
echo "Web client exported to $ROOT/build/web"
