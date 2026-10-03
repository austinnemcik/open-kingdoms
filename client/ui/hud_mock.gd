extends Control
## Reference composition of the city HUD (static mock data, no networking).
## Rendered to docs/screenshots/ui_hud_mock.png. Engineers building the real
## HUD (P1-07..P1-09) should match this layout using the same widgets.

const EDGE := 16.0


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_background()
	_player_badge()
	_top_right()
	_builder_queue()
	_selection_card()
	_action_bar()
	_chat()
	var toast := Toast.new()
	toast.configure("Quarry upgraded to level 5", Toast.Kind.SUCCESS)
	add_child(toast)
	toast.set_anchors_and_offsets_preset(PRESET_CENTER_TOP)
	toast.grow_horizontal = GROW_DIRECTION_BOTH
	toast.offset_top = 84.0


func _text(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation
	return label


func _background() -> void:
	# Stand-in for the 3D city: flat grass tones so the HUD reads on its own.
	var gradient := Gradient.new()
	gradient.set_color(0, Color("8aa862"))
	gradient.set_color(1, Color("4f6d3c"))
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.45)
	texture.fill_to = Vector2(1.1, 1.0)
	var bg := TextureRect.new()
	bg.texture = texture
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	add_child(bg)
	bg.set_anchors_and_offsets_preset(PRESET_FULL_RECT)


func _player_badge() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 6)
	add_child(row)
	row.position = Vector2(EDGE, 10)
	var portrait := TextureRect.new()
	portrait.texture = UiIcons.get_texture(&"portrait_frame")
	portrait.custom_minimum_size = Vector2(100, 100)
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	row.add_child(portrait)
	var face := UiIcons.make_rect(&"commander", 0)
	portrait.add_child(face)
	face.set_anchors_and_offsets_preset(PRESET_FULL_RECT, PRESET_MODE_MINSIZE, 22)
	var level := TextureRect.new()
	level.texture = UiIcons.get_texture(&"level_badge")
	level.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	level.size = Vector2(36, 36)
	level.position = Vector2(66, 66)
	portrait.add_child(level)
	var level_text := _text("12", &"BadgeValue")
	level_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	level_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	level.add_child(level_text)
	level_text.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	level_text.offset_top = -2.0

	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 4)
	column.size_flags_vertical = SIZE_SHRINK_CENTER
	row.add_child(column)
	column.add_child(_text("Aldric the Bold", &"Subheader"))
	var power := ResourceChip.new()
	power.kind = &"power"
	power.set_amount(1243500)
	power.size_flags_horizontal = SIZE_SHRINK_BEGIN
	column.add_child(power)


func _top_right() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 10)
	add_child(row)
	row.set_anchors_and_offsets_preset(PRESET_TOP_RIGHT)
	row.grow_horizontal = GROW_DIRECTION_BEGIN
	row.offset_right = -EDGE
	row.offset_top = 14.0
	var bar := ResourceBar.new()
	bar.size_flags_vertical = SIZE_SHRINK_CENTER
	bar.set_amounts({"food": 152431, "wood": 98200, "stone": 41750, "gold": 6300})
	row.add_child(bar)
	var settings := IconButton.new()
	settings.icon_name = &"settings"
	settings.custom_minimum_size = Vector2(52, 52)
	settings.tooltip_text = "Settings"
	row.add_child(settings)


func _queue_row(icon: StringName, title: String, detail: Control) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 10)
	var well := PanelContainer.new()
	well.theme_type_variation = &"PanelInset"
	well.add_child(UiIcons.make_rect(icon, 40))
	row.add_child(well)
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 3)
	column.size_flags_horizontal = SIZE_EXPAND_FILL
	column.size_flags_vertical = SIZE_SHRINK_CENTER
	column.add_child(_text(title, &"Body"))
	column.add_child(detail)
	row.add_child(column)
	return row


func _builder_queue() -> void:
	var card := PanelContainer.new()
	card.custom_minimum_size.x = 312
	add_child(card)
	card.position = Vector2(EDGE, 128)
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 10)
	card.add_child(column)
	var head := HBoxContainer.new()
	head.add_child(UiIcons.make_rect(&"build", 26))
	var title := _text("Builders", &"Subheader")
	title.size_flags_horizontal = SIZE_EXPAND_FILL
	head.add_child(title)
	head.add_child(_text("1 / 2 busy", &"Caption"))
	column.add_child(head)
	var timer := TimerProgressBar.new()
	timer.auto_tick = false
	timer.set_timer(7985, 14400)
	column.add_child(_queue_row(&"farm", "Farm  →  Level 4", timer))
	column.add_child(HSeparator.new())
	var idle := _queue_row(&"build", "Builder idle", _text("Select a building to upgrade", &"Caption"))
	column.add_child(idle)


func _selection_card() -> void:
	var card := PanelContainer.new()
	add_child(card)
	card.set_anchors_and_offsets_preset(PRESET_CENTER_BOTTOM)
	card.grow_horizontal = GROW_DIRECTION_BOTH
	card.grow_vertical = GROW_DIRECTION_BEGIN
	# Floats above the bottom row so it never collides with chat or actions.
	card.offset_bottom = -(EDGE + 116.0 + 14.0)
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 12)
	card.add_child(row)
	row.add_child(UiIcons.make_rect(&"quarry", 60))
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 0)
	column.size_flags_vertical = SIZE_SHRINK_CENTER
	column.custom_minimum_size.x = 170
	column.add_child(_text("Quarry", &"Header"))
	column.add_child(_text("Level 5  ·  +860 stone / hour", &"Caption"))
	row.add_child(column)
	var info := Button.new()
	info.text = "Details"
	info.custom_minimum_size = Vector2(120, 52)
	info.size_flags_vertical = SIZE_SHRINK_CENTER
	row.add_child(info)
	var upgrade := Button.new()
	upgrade.text = "Upgrade"
	upgrade.icon = UiIcons.get_icon(&"upgrade")
	upgrade.theme_type_variation = &"ButtonPrimary"
	upgrade.custom_minimum_size = Vector2(150, 52)
	upgrade.size_flags_vertical = SIZE_SHRINK_CENTER
	row.add_child(upgrade)


func _action_bar() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 10)
	row.alignment = BoxContainer.ALIGNMENT_END
	add_child(row)
	row.set_anchors_and_offsets_preset(PRESET_BOTTOM_RIGHT)
	row.grow_horizontal = GROW_DIRECTION_BEGIN
	row.grow_vertical = GROW_DIRECTION_BEGIN
	row.offset_right = -EDGE
	row.offset_bottom = -EDGE
	var actions: Array[Array] = [
		[&"build", "Build", 0], [&"research", "Research", 0], [&"infantry", "Army", 0],
		[&"alliance", "Alliance", 3], [&"mail", "Mail", 12],
	]
	for action in actions:
		var button := IconButton.new()
		button.icon_name = action[0]
		button.caption = action[1]
		button.badge_count = action[2]
		button.custom_minimum_size = Vector2(88, 88)
		button.size_flags_vertical = SIZE_SHRINK_END
		row.add_child(button)
	var world := IconButton.new()
	world.icon_name = &"map"
	world.caption = "World"
	world.custom_minimum_size = Vector2(116, 116)
	row.add_child(world)


func _chat() -> void:
	var card := PanelContainer.new()
	card.custom_minimum_size.x = 400
	add_child(card)
	card.set_anchors_and_offsets_preset(PRESET_BOTTOM_LEFT)
	card.grow_vertical = GROW_DIRECTION_BEGIN
	card.offset_left = EDGE
	card.offset_bottom = -EDGE
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 2)
	card.add_child(column)
	var lines: Array[Array] = [["Mira", "Rally at the north pass in 5 minutes"], ["Tomas", "Sending 20K wood your way"]]
	for line in lines:
		var row := HBoxContainer.new()
		row.add_theme_constant_override(&"separation", 6)
		var who := _text("[Alliance] %s:" % line[0], &"Caption")
		who.add_theme_color_override(&"font_color", UiColors.TEXT_GOLD)
		row.add_child(who)
		row.add_child(_text(line[1], &"Caption"))
		column.add_child(row)
