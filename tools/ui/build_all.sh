#!/usr/bin/env bash
# Regenerate every UI asset: textures, icons, Godot imports and the theme.
#   GODOT=/path/to/godot tools/ui/build_all.sh
# Needs: python with resvg-py, Pillow, numpy (pip install -r tools/ui/requirements.txt).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GODOT="${GODOT:-$HOME/.local/godot/4.8-dev6/Godot_v4.8-dev6_win64_console.exe}"
PYTHON="${PYTHON:-python}"

cd "$ROOT"
"$PYTHON" tools/ui/build_textures.py
"$PYTHON" tools/ui/build_icons.py
# First import creates the .import files, the second run of build_icons turns
# on mipmaps in them, and the last import applies that.
"$GODOT" --headless --path client --import >/dev/null 2>&1 || true
"$PYTHON" tools/ui/build_icons.py
"$GODOT" --headless --path client --import >/dev/null 2>&1 || true
"$GODOT" --headless --path client -s res://ui/theme/build_theme.gd
