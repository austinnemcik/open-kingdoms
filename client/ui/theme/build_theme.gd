extends SceneTree
## Builds `res://ui/theme/main_theme.tres` and the font variations in
## `res://ui/fonts/` from the generated textures. Run after the textures change:
##   godot --headless --path client -s res://ui/theme/build_theme.gd
## Slice margins here must match tools/ui/build_textures.py.

const TEX := "res://ui/theme/textures/"
const FONTS := "res://ui/fonts/"
const OUT := "res://ui/theme/main_theme.tres"

const FONT_SIZE := 18

var _theme := Theme.new()
var _body: Font
var _bold: Font
var _heading: Font


func _initialize() -> void:
	_body = _font("Nunito-Variable.ttf", 650, "body.tres", 0)
	_bold = _font("Nunito-Variable.ttf", 850, "body_bold.tres", 0)
	_heading = _font("Cinzel-Variable.ttf", 800, "heading.tres", 1)
	_theme.default_font = _body
	_theme.default_font_size = FONT_SIZE
	_labels()
	_buttons()
	_panels()
	_inputs()
	_tabs()
	_progress()
	_scrolling()
	_popups()
	var err := ResourceSaver.save(_theme, OUT)
	print("saved %s (%s)" % [OUT, error_string(err)])
	quit(0 if err == OK else 1)


func _font(file: String, weight: int, out: String, glyph_spacing: int) -> Font:
	var font := FontVariation.new()
	font.base_font = load(FONTS + file)
	font.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): weight}
	font.spacing_glyph = glyph_spacing
	var path := FONTS + out
	ResourceSaver.save(font, path)
	font.take_over_path(path)
	return font


## 9-slice stylebox. `margins` and `content` are [left, top, right, bottom].
func _box(texture: String, margins: Array[int], content: Array[int], expand := 0) -> StyleBoxTexture:
	var box := StyleBoxTexture.new()
	box.texture = load(TEX + texture + ".png")
	box.texture_margin_left = margins[0]
	box.texture_margin_top = margins[1]
	box.texture_margin_right = margins[2]
	box.texture_margin_bottom = margins[3]
	box.content_margin_left = content[0]
	box.content_margin_top = content[1]
	box.content_margin_right = content[2]
	box.content_margin_bottom = content[3]
	box.set_expand_margin_all(expand)
	return box


func _flat(color: Color, radius: int, content := 0) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = color
	box.set_corner_radius_all(radius)
	box.set_content_margin_all(content)
	box.anti_aliasing_size = 0.6
	return box


func _label(type: StringName, font: Font, size: int, color: Color, outline := 0, shadow := false) -> void:
	_theme.set_type_variation(type, &"Label")
	_theme.set_font(&"font", type, font)
	_theme.set_font_size(&"font_size", type, size)
	_theme.set_color(&"font_color", type, color)
	_theme.set_constant(&"outline_size", type, outline)
	_theme.set_color(&"font_outline_color", type, Color(UiColors.OUTLINE, 0.9))
	_theme.set_color(&"font_shadow_color", type, Color(0, 0, 0, 0.55 if shadow else 0.0))
	_theme.set_constant(&"shadow_offset_x", type, 0)
	_theme.set_constant(&"shadow_offset_y", type, 2 if shadow else 0)
	_theme.set_constant(&"shadow_outline_size", type, outline)


func _labels() -> void:
	_theme.set_color(&"font_color", &"Label", UiColors.TEXT)
	_theme.set_constant(&"line_spacing", &"Label", 2)
	_label(&"HeaderLarge", _heading, 34, UiColors.TEXT_GOLD, 6, true)
	_label(&"Header", _heading, 24, UiColors.TEXT_GOLD, 5, true)
	_label(&"HeaderInk", _heading, 24, UiColors.INK)
	_label(&"Title", _heading, 21, UiColors.TEXT, 5, true)
	_label(&"Subheader", _bold, 20, UiColors.TEXT, 4)
	_label(&"SubheaderInk", _bold, 20, UiColors.INK)
	_label(&"Body", _body, FONT_SIZE, UiColors.TEXT)
	_label(&"BodyInk", _body, FONT_SIZE, UiColors.INK)
	_label(&"Caption", _body, 14, UiColors.TEXT_MUTED)
	_label(&"CaptionInk", _body, 14, UiColors.INK_MUTED)
	_label(&"ResourceValue", _bold, FONT_SIZE, UiColors.TEXT, 4)
	_label(&"ResourceValueInk", _bold, FONT_SIZE, UiColors.INK)
	_label(&"TimerValue", _bold, 15, UiColors.TEXT, 5)
	_label(&"BadgeValue", _bold, 14, UiColors.TEXT, 4)
	_theme.set_color(&"default_color", &"RichTextLabel", UiColors.TEXT)


func _button(type: StringName, colour: String, text: Color, outline: int) -> void:
	if not ClassDB.class_exists(type):
		_theme.set_type_variation(type, &"Button")
	var margins: Array[int] = [20, 22, 20, 26]
	var up: Array[int] = [22, 9, 22, 15]
	var down: Array[int] = [22, 13, 22, 11]
	_theme.set_stylebox(&"normal", type, _box("button_%s_normal" % colour, margins, up))
	_theme.set_stylebox(&"hover", type, _box("button_%s_hover" % colour, margins, up))
	_theme.set_stylebox(&"pressed", type, _box("button_%s_pressed" % colour, margins, down))
	_theme.set_stylebox(&"hover_pressed", type, _box("button_%s_pressed" % colour, margins, down))
	_theme.set_stylebox(&"disabled", type, _box("button_disabled", margins, up))
	_theme.set_stylebox(&"focus", type, _box("focus_ring", [16, 16, 16, 16], [0, 0, 0, 0], 3))
	_theme.set_font(&"font", type, _bold)
	_theme.set_font_size(&"font_size", type, FONT_SIZE)
	for state: StringName in [&"font_color", &"font_hover_color", &"font_pressed_color", &"font_hover_pressed_color", &"font_focus_color"]:
		_theme.set_color(state, type, text)
	_theme.set_color(&"font_disabled_color", type, Color("e4dccf"))
	_theme.set_color(&"font_outline_color", type, Color(UiColors.OUTLINE, 0.75))
	_theme.set_constant(&"outline_size", type, outline)
	_theme.set_constant(&"h_separation", type, 8)
	_theme.set_constant(&"icon_max_width", type, 28)
	for state: StringName in [&"icon_normal_color", &"icon_hover_color", &"icon_pressed_color", &"icon_hover_pressed_color", &"icon_focus_color"]:
		_theme.set_color(state, type, Color.WHITE)
	_theme.set_color(&"icon_disabled_color", type, Color(1, 1, 1, 0.5))


func _slot(type: StringName, texture: String) -> void:
	_theme.set_type_variation(type, &"Button")
	var margins: Array[int] = [26, 26, 26, 28]
	var up: Array[int] = [10, 9, 10, 13]
	var down: Array[int] = [10, 12, 10, 10]
	_theme.set_stylebox(&"normal", type, _box(texture + "_normal", margins, up))
	_theme.set_stylebox(&"hover", type, _box(texture + "_hover", margins, up))
	_theme.set_stylebox(&"pressed", type, _box(texture + "_pressed", margins, down))
	_theme.set_stylebox(&"hover_pressed", type, _box(texture + "_pressed", margins, down))
	_theme.set_stylebox(&"disabled", type, _box("slot_disabled", margins, up))
	_theme.set_stylebox(&"focus", type, _box("focus_ring", [16, 16, 16, 16], [0, 0, 0, 0], 3))


func _buttons() -> void:
	_button(&"Button", "neutral", UiColors.TEXT, 5)
	_button(&"ButtonPrimary", "primary", UiColors.TEXT, 5)
	_button(&"ButtonDanger", "danger", UiColors.TEXT, 5)
	_button(&"ButtonGold", "gold", Color("4a2c0a"), 0)
	_button(&"OptionButton", "neutral", UiColors.TEXT, 5)
	_theme.set_icon(&"arrow", &"OptionButton", load(TEX + "arrow_down.png"))
	_theme.set_constant(&"arrow_margin", &"OptionButton", 14)
	_slot(&"IconSlot", "slot")
	_slot(&"CloseButton", "slot_red")

	var empty := StyleBoxEmpty.new()
	empty.set_content_margin_all(4)
	for type: StringName in [&"CheckBox", &"CheckButton"]:
		for state: StringName in [&"normal", &"hover", &"pressed", &"hover_pressed", &"disabled"]:
			_theme.set_stylebox(state, type, empty)
		_theme.set_stylebox(&"focus", type, _box("focus_ring", [16, 16, 16, 16], [0, 0, 0, 0], 1))
		_theme.set_font(&"font", type, _body)
		_theme.set_constant(&"outline_size", type, 0)
		_theme.set_color(&"font_color", type, UiColors.TEXT)
		_theme.set_color(&"font_hover_color", type, Color.WHITE)
		_theme.set_color(&"font_pressed_color", type, UiColors.TEXT)
		_theme.set_color(&"font_hover_pressed_color", type, Color.WHITE)
		_theme.set_color(&"font_disabled_color", type, Color(UiColors.TEXT_MUTED, 0.6))
		_theme.set_constant(&"h_separation", type, 8)
	_theme.set_icon(&"checked", &"CheckBox", load(TEX + "check_checked.png"))
	_theme.set_icon(&"unchecked", &"CheckBox", load(TEX + "check_unchecked.png"))
	_theme.set_icon(&"checked_disabled", &"CheckBox", load(TEX + "check_checked.png"))
	_theme.set_icon(&"unchecked_disabled", &"CheckBox", load(TEX + "check_unchecked.png"))
	_theme.set_icon(&"radio_checked", &"CheckBox", load(TEX + "radio_checked.png"))
	_theme.set_icon(&"radio_unchecked", &"CheckBox", load(TEX + "radio_unchecked.png"))
	_theme.set_icon(&"radio_checked_disabled", &"CheckBox", load(TEX + "radio_checked.png"))
	_theme.set_icon(&"radio_unchecked_disabled", &"CheckBox", load(TEX + "radio_unchecked.png"))
	# On parchment.
	_theme.set_type_variation(&"CheckBoxInk", &"CheckBox")
	for state: StringName in [&"font_color", &"font_hover_color", &"font_pressed_color", &"font_hover_pressed_color"]:
		_theme.set_color(state, &"CheckBoxInk", UiColors.INK)
	_theme.set_color(&"font_disabled_color", &"CheckBoxInk", Color(UiColors.INK_MUTED, 0.7))


func _panel(type: StringName, box: StyleBox) -> void:
	_theme.set_type_variation(type, &"PanelContainer")
	_theme.set_stylebox(&"panel", type, box)


func _parchment() -> StyleBoxTexture:
	var box := _box("panel_parchment", [32, 32, 32, 32], [18, 16, 18, 16])
	box.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	box.axis_stretch_vertical = StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	return box


func _panels() -> void:
	var card := _box("card", [28, 28, 28, 28], [14, 12, 14, 12], 8)
	_theme.set_stylebox(&"panel", &"Panel", card)
	_theme.set_stylebox(&"panel", &"PanelContainer", card)
	_panel(&"PanelCard", card)
	var wood := _box("panel_wood", [56, 56, 56, 56], [24, 24, 24, 24], 16)
	_panel(&"PanelWood", wood)
	_panel(&"PanelParchment", _parchment())
	_panel(&"PanelChip", _box("chip", [20, 18, 20, 18], [6, 4, 14, 4]))
	_panel(&"PanelPlaque", _box("title_plaque", [44, 0, 44, 0], [40, 12, 40, 16]))
	_panel(&"PanelInset", _box("inset_dark", [12, 12, 12, 12], [10, 8, 10, 8]))
	_panel(&"PanelInsetLight", _box("inset_light", [12, 12, 12, 12], [10, 8, 10, 8]))

	var line := StyleBoxLine.new()
	line.color = Color(UiColors.GOLD, 0.45)
	line.thickness = 2
	_theme.set_stylebox(&"separator", &"HSeparator", line)
	_theme.set_constant(&"separation", &"HSeparator", 12)
	var vline := line.duplicate() as StyleBoxLine
	vline.vertical = true
	_theme.set_stylebox(&"separator", &"VSeparator", vline)
	_theme.set_constant(&"separation", &"BoxContainer", 8)
	_theme.set_constant(&"separation", &"HBoxContainer", 8)
	_theme.set_constant(&"separation", &"VBoxContainer", 8)
	_theme.set_constant(&"h_separation", &"GridContainer", 8)
	_theme.set_constant(&"v_separation", &"GridContainer", 8)


func _inputs() -> void:
	var margins: Array[int] = [12, 12, 12, 12]
	var content: Array[int] = [14, 9, 14, 9]
	for type: StringName in [&"LineEdit", &"TextEdit"]:
		_theme.set_stylebox(&"normal", type, _box("lineedit_normal", margins, content))
		_theme.set_stylebox(&"focus", type, _box("lineedit_focus", margins, content))
		_theme.set_stylebox(&"read_only", type, _box("lineedit_readonly", margins, content))
		_theme.set_color(&"font_color", type, UiColors.INK)
		_theme.set_color(&"font_uneditable_color", type, UiColors.INK_MUTED)
		_theme.set_color(&"font_placeholder_color", type, Color("7a6444"))
		_theme.set_color(&"font_selected_color", type, UiColors.INK)
		_theme.set_color(&"selection_color", type, Color(UiColors.GOLD, 0.55))
		_theme.set_color(&"caret_color", type, UiColors.INK)
		_theme.set_color(&"clear_button_color", type, UiColors.INK_MUTED)
		_theme.set_color(&"clear_button_color_pressed", type, UiColors.INK)
	_theme.set_constant(&"minimum_character_width", &"LineEdit", 8)

	var list_box := _box("lineedit_normal", margins, [8, 8, 8, 8])
	_theme.set_stylebox(&"panel", &"ItemList", list_box)
	_theme.set_stylebox(&"focus", &"ItemList", _box("focus_ring", [16, 16, 16, 16], [0, 0, 0, 0], 2))
	var selected := _flat(Color(UiColors.GOLD, 0.6), 6, 4)
	selected.border_color = UiColors.GOLD_DARK
	selected.set_border_width_all(1)
	_theme.set_stylebox(&"selected", &"ItemList", selected)
	_theme.set_stylebox(&"selected_focus", &"ItemList", selected)
	_theme.set_stylebox(&"hovered", &"ItemList", _flat(Color(UiColors.WOOD_LIGHT, 0.18), 6, 4))
	_theme.set_stylebox(&"hovered_selected", &"ItemList", selected)
	_theme.set_stylebox(&"hovered_selected_focus", &"ItemList", selected)
	_theme.set_stylebox(&"cursor", &"ItemList", StyleBoxEmpty.new())
	_theme.set_stylebox(&"cursor_unfocused", &"ItemList", StyleBoxEmpty.new())
	_theme.set_color(&"font_color", &"ItemList", UiColors.INK)
	_theme.set_color(&"font_hovered_color", &"ItemList", UiColors.INK)
	_theme.set_color(&"font_selected_color", &"ItemList", UiColors.INK)
	_theme.set_color(&"font_hovered_selected_color", &"ItemList", UiColors.INK)
	_theme.set_color(&"guide_color", &"ItemList", Color(UiColors.WOOD_LIGHT, 0.2))
	_theme.set_constant(&"v_separation", &"ItemList", 6)
	_theme.set_constant(&"h_separation", &"ItemList", 8)
	_theme.set_constant(&"icon_margin", &"ItemList", 6)


func _tabs() -> void:
	var margins: Array[int] = [18, 20, 18, 4]
	var up: Array[int] = [22, 9, 22, 8]
	var low: Array[int] = [22, 13, 22, 6]
	for type: StringName in [&"TabContainer", &"TabBar"]:
		_theme.set_stylebox(&"tab_selected", type, _box("tab_selected", margins, up))
		_theme.set_stylebox(&"tab_unselected", type, _box("tab_unselected", margins, low))
		_theme.set_stylebox(&"tab_hovered", type, _box("tab_hover", margins, low))
		_theme.set_stylebox(&"tab_disabled", type, _box("tab_disabled", margins, low))
		_theme.set_stylebox(&"tab_focus", type, StyleBoxEmpty.new())
		_theme.set_font(&"font", type, _bold)
		_theme.set_font_size(&"font_size", type, 17)
		_theme.set_color(&"font_selected_color", type, Color("4a2c0a"))
		_theme.set_color(&"font_unselected_color", type, UiColors.TEXT_MUTED)
		_theme.set_color(&"font_hovered_color", type, UiColors.TEXT)
		_theme.set_color(&"font_disabled_color", type, Color("b9ab95"))
		_theme.set_constant(&"h_separation", type, 6)
	_theme.set_stylebox(&"panel", &"TabContainer", _parchment())
	_theme.set_stylebox(&"tabbar_background", &"TabContainer", StyleBoxEmpty.new())
	_theme.set_constant(&"side_margin", &"TabContainer", 14)


func _progress() -> void:
	var margins: Array[int] = [14, 13, 14, 13]
	var none: Array[int] = [0, 0, 0, 0]
	_theme.set_stylebox(&"background", &"ProgressBar", _box("progress_bg", margins, none))
	_theme.set_stylebox(&"fill", &"ProgressBar", _box("progress_fill", margins, none))
	_theme.set_font(&"font", &"ProgressBar", _bold)
	_theme.set_font_size(&"font_size", &"ProgressBar", 15)
	_theme.set_color(&"font_color", &"ProgressBar", UiColors.TEXT)
	_theme.set_color(&"font_outline_color", &"ProgressBar", Color(UiColors.OUTLINE, 0.9))
	_theme.set_constant(&"outline_size", &"ProgressBar", 5)
	_theme.set_type_variation(&"GoldBar", &"ProgressBar")
	_theme.set_stylebox(&"fill", &"GoldBar", _box("progress_fill_gold", margins, none))
	# Construction / training / research timers: striped blue fill.
	_theme.set_type_variation(&"ConstructionBar", &"ProgressBar")
	var timer := _box("progress_fill_timer", margins, none)
	timer.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	_theme.set_stylebox(&"fill", &"ConstructionBar", timer)


func _scrolling() -> void:
	var empty_icon: Texture2D = load(TEX + "empty.png")
	for type: StringName in [&"VScrollBar", &"HScrollBar"]:
		var track := _flat(Color(UiColors.OUTLINE, 0.3), 5)
		var grabber := _flat(Color("a8834f"), 5)
		grabber.border_color = Color(UiColors.OUTLINE, 0.8)
		grabber.set_border_width_all(1)
		var bright := grabber.duplicate() as StyleBoxFlat
		bright.bg_color = UiColors.GOLD
		if type == &"VScrollBar":
			track.content_margin_left = 5
			track.content_margin_right = 5
		else:
			track.content_margin_top = 5
			track.content_margin_bottom = 5
		_theme.set_stylebox(&"scroll", type, track)
		_theme.set_stylebox(&"scroll_focus", type, track)
		_theme.set_stylebox(&"grabber", type, grabber)
		_theme.set_stylebox(&"grabber_highlight", type, bright)
		_theme.set_stylebox(&"grabber_pressed", type, bright)
		for icon: StringName in [&"increment", &"increment_highlight", &"increment_pressed", &"decrement", &"decrement_highlight", &"decrement_pressed"]:
			_theme.set_icon(icon, type, empty_icon)
	_theme.set_stylebox(&"panel", &"ScrollContainer", StyleBoxEmpty.new())
	_theme.set_stylebox(&"focus", &"ScrollContainer", StyleBoxEmpty.new())


func _popups() -> void:
	_theme.set_stylebox(&"panel", &"TooltipPanel", _box("tooltip", [12, 12, 12, 12], [12, 8, 12, 8]))
	_theme.set_font(&"font", &"TooltipLabel", _body)
	_theme.set_font_size(&"font_size", &"TooltipLabel", 16)
	_theme.set_color(&"font_color", &"TooltipLabel", UiColors.TEXT)
	_theme.set_color(&"font_shadow_color", &"TooltipLabel", Color(0, 0, 0, 0))

	var card := _box("card", [28, 28, 28, 28], [14, 12, 14, 12], 8)
	_theme.set_stylebox(&"panel", &"PopupPanel", card)
	_theme.set_stylebox(&"panel", &"PopupMenu", _box("card", [28, 28, 28, 28], [12, 12, 12, 12], 8))
	_theme.set_stylebox(&"hover", &"PopupMenu", _flat(Color(UiColors.GOLD, 0.28), 6, 4))
	var line := StyleBoxLine.new()
	line.color = Color(UiColors.GOLD, 0.35)
	_theme.set_stylebox(&"separator", &"PopupMenu", line)
	_theme.set_font(&"font", &"PopupMenu", _body)
	_theme.set_color(&"font_color", &"PopupMenu", UiColors.TEXT)
	_theme.set_color(&"font_hover_color", &"PopupMenu", Color.WHITE)
	_theme.set_color(&"font_disabled_color", &"PopupMenu", Color(UiColors.TEXT_MUTED, 0.6))
	_theme.set_constant(&"v_separation", &"PopupMenu", 8)
	_theme.set_constant(&"item_start_padding", &"PopupMenu", 8)
	_theme.set_constant(&"item_end_padding", &"PopupMenu", 8)
	_theme.set_icon(&"radio_checked", &"PopupMenu", load(TEX + "radio_checked.png"))
	_theme.set_icon(&"radio_unchecked", &"PopupMenu", load(TEX + "radio_unchecked.png"))
	_theme.set_icon(&"checked", &"PopupMenu", load(TEX + "check_checked.png"))
	_theme.set_icon(&"unchecked", &"PopupMenu", load(TEX + "check_unchecked.png"))
