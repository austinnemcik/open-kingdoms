#!/usr/bin/env bash
# Regenerate every generated art asset from the scripts in tools/blender/, then
# re-import the Godot project so the .import files match.
#
#   scripts/build_art.sh               # everything
#   scripts/build_art.sh textures      # atlas + ground textures (system Python: numpy, Pillow)
#   scripts/build_art.sh buildings [kind[:tier] ...]
#   scripts/build_art.sh scenery [wall|terrain|scatter|props ...]
#
# Env: BLENDER = path to Blender 5.x, GODOT = path to a Godot 4.8 binary,
#      PYTHON = Python 3 with numpy and Pillow.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHAT="${1:-all}"
shift || true

find_tool() {
  local var="$1"; shift
  if [[ -n "${!var:-}" ]]; then echo "${!var}"; return; fi
  for c in "$@"; do
    if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then echo "$c"; return; fi
  done
  echo "error: $var not found; set $var=/path/to/it" >&2
  exit 1
}

BLENDER_BIN="$(find_tool BLENDER blender "/c/Program Files/Blender Foundation/Blender 5.1/blender.exe")"
GODOT_BIN="$(find_tool GODOT godot4 godot "$HOME/.local/godot/4.8-dev6/Godot_v4.8-dev6_win64_console.exe")"
PYTHON_BIN="$(find_tool PYTHON python3 python)"

cd "$ROOT"
blender() { "$BLENDER_BIN" -b --factory-startup -P "$1" -- "${@:2}" | grep -E "^(exported|scatter:)|Error|Traceback" || true; }

case "$WHAT" in
  textures) "$PYTHON_BIN" tools/blender/gen_textures.py ;;
  buildings) blender tools/blender/build_buildings.py client/assets/models "$@" ;;
  scenery) blender tools/blender/build_scenery.py client/assets/models/scenery "$@" ;;
  all)
    "$PYTHON_BIN" tools/blender/gen_textures.py
    blender tools/blender/build_buildings.py client/assets/models
    blender tools/blender/build_scenery.py client/assets/models/scenery
    ;;
  *) echo "usage: $0 [all|textures|buildings|scenery] [args...]" >&2; exit 2 ;;
esac

"$GODOT_BIN" --headless --path client --import >/dev/null 2>&1 || true
echo "build_art: OK ($WHAT)"
