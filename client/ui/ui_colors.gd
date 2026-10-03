class_name UiColors
extends RefCounted
## Colour tokens for the UI. Mirrors `tools/ui/common.py` and docs/UI_STYLE.md.
## Prefer theme type variations over reading these directly; use them only for
## state colours set from code (e.g. an unaffordable cost).

# Text on dark surfaces (wood, cards, HUD).
const TEXT := Color("fff6e0")
const TEXT_MUTED := Color("d9c7a3")
const TEXT_GOLD := Color("ffd978")
const DANGER := Color("ff8a78")
const SUCCESS := Color("9be063")
const WARNING := Color("ffc24a")

# Text on parchment.
const INK := Color("2e2014")
const INK_MUTED := Color("6b543a")
const INK_DANGER := Color("b3261e")
const INK_SUCCESS := Color("276a1c")

# Surfaces and trim.
const OUTLINE := Color("2b1a0f")
const WOOD_DARK := Color("33231a")
const WOOD := Color("463020")
const WOOD_LIGHT := Color("7a5a36")
const PARCHMENT := Color("f1e3c4")
const PARCHMENT_LIGHT := Color("fbf3de")
const PARCHMENT_DARK := Color("c9ae7c")
const GOLD_LIGHT := Color("ffe58a")
const GOLD := Color("f2b632")
const GOLD_DARK := Color("8a5a14")
const VERDIGRIS := Color("2f7a87")
const GREEN := Color("5cab3d")
const CRIMSON := Color("c5463a")
const SCRIM := Color(0.07, 0.04, 0.02, 0.6)
