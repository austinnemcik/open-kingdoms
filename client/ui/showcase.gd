extends Control
## UI kit showcase: every theme style and widget on one page. Rendered to
## docs/screenshots/ui_showcase.png by `res://ui/screenshot_ui.gd`; also handy
## to open in the editor while changing the theme.

const SAMPLE_COSTS := {"food": 1200, "wood": 8400, "stone": 0, "gold": 150}
const SAMPLE_OWNED := {"food": 15300, "wood": 6100, "stone": 900, "gold": 4000}


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color("2a2019")
	add_child(bg)
	bg.set_anchors_and_offsets_preset(PRESET_FULL_RECT)

	var margin := MarginContainer.new()
	for side: StringName in [&"margin_left", &"margin_right", &"margin_top", &"margin_bottom"]:
		margin.add_theme_constant_override(side, 36)
	add_child(margin)
	margin.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	var page := VBoxContainer.new()
	page.add_theme_constant_override(&"separation", 52)
	margin.add_child(page)

	page.add_child(_top_row())
	var row1 := _row(40)
	row1.add_child(_typography())
	row1.add_child(_buttons())
	row1.add_child(_inputs())
	page.add_child(row1)
	var row2 := _row(40)
	row2.add_child(_icons())
	var right := _column(40)
	var right_top := _row(40)
	right_top.add_child(_upgrade_window())
	right_top.add_child(_feedback())
	right.add_child(right_top)
	right.add_child(_dialog())
	row2.add_child(right)
	page.add_child(row2)


func _row(separation: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", separation)
	return row


func _column(separation := 10) -> VBoxContainer:
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", separation)
	return column


func _text(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation
	return label


func _divider(ink: bool) -> TextureRect:
	var rect := TextureRect.new()
	rect.texture = UiIcons.get_texture(&"divider_ink" if ink else &"divider")
	rect.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	return rect


func _frame(title: String, width: float) -> PanelFrame:
	var frame := PanelFrame.new()
	frame.title = title
	frame.custom_minimum_size.x = width
	return frame


func _top_row() -> Control:
	var row := _row(16)
	row.add_child(_text("Open Kingdoms  ·  UI Kit", &"HeaderLarge"))
	var spacer := Control.new()
	spacer.size_flags_horizontal = SIZE_EXPAND_FILL
	row.add_child(spacer)
	var bar := ResourceBar.new()
	bar.size_flags_vertical = SIZE_SHRINK_CENTER
	bar.set_amounts({"food": 12431, "wood": 1250000, "stone": 950, "gold": 50000}, {"gold": 50000})
	row.add_child(bar)
	var power := ResourceChip.new()
	power.kind = &"power"
	power.set_amount(3482100)
	power.size_flags_vertical = SIZE_SHRINK_CENTER
	row.add_child(power)
	return row


func _typography() -> Control:
	var frame := _frame("Typography", 440)
	var column := _column(6)
	frame.add_content(column)
	column.add_child(_text("HeaderInk · Cinzel 24", &"HeaderInk"))
	column.add_child(_text("SubheaderInk · Nunito 20", &"SubheaderInk"))
	var body := _text("BodyInk · Nunito 18. Grow your city, gather on the map and fight beside your alliance.", &"BodyInk")
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(body)
	column.add_child(_text("CaptionInk · 14 · secondary details", &"CaptionInk"))
	column.add_child(_text("ResourceValueInk 12.4K", &"ResourceValueInk"))
	column.add_child(_divider(true))
	var dark := PanelContainer.new()
	var dark_column := _column(4)
	dark.add_child(dark_column)
	dark_column.add_child(_text("HeaderLarge 34", &"HeaderLarge"))
	dark_column.add_child(_text("Header · Cinzel 24", &"Header"))
	dark_column.add_child(_text("Subheader · Nunito 20", &"Subheader"))
	dark_column.add_child(_text("Body · the default label on dark surfaces", &"Body"))
	dark_column.add_child(_text("Caption · 14 · secondary details", &"Caption"))
	dark_column.add_child(_text("ResourceValue 1.2M   TimerValue 02:13:05", &"ResourceValue"))
	column.add_child(dark)
	return frame


func _state_button(text: String, variation: StringName, state: StringName) -> Button:
	var button := Button.new()
	button.text = text
	button.theme_type_variation = variation
	button.custom_minimum_size = Vector2(128, 52)
	var type := variation if variation != &"" else &"Button"
	if state == &"disabled":
		button.disabled = true
	elif state != &"normal":
		# Freeze a hover/pressed look so it shows up in a still image.
		button.add_theme_stylebox_override(&"normal", ThemeDB.get_project_theme().get_stylebox(state, type))
	return button


func _buttons() -> Control:
	var frame := _frame("Buttons", 660)
	var column := _column(14)
	frame.add_content(column)
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override(&"h_separation", 14)
	grid.add_theme_constant_override(&"v_separation", 10)
	column.add_child(grid)
	for heading: String in ["Normal", "Hover", "Pressed", "Disabled"]:
		var label := _text(heading.to_upper(), &"CaptionInk")
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		grid.add_child(label)
	var kinds: Array[Array] = [["Button", &""], ["Upgrade", &"ButtonPrimary"], ["Claim", &"ButtonGold"], ["Demolish", &"ButtonDanger"]]
	for kind in kinds:
		for state: StringName in [&"normal", &"hover", &"pressed", &"disabled"]:
			grid.add_child(_state_button(kind[0], kind[1], state))
	column.add_child(_divider(true))

	var slots := _row(14)
	column.add_child(slots)
	var plain := IconButton.new()
	plain.icon_name = &"build"
	slots.add_child(plain)
	var captioned := IconButton.new()
	captioned.icon_name = &"research"
	captioned.caption = "Research"
	captioned.custom_minimum_size = Vector2(88, 88)
	slots.add_child(captioned)
	var badged := IconButton.new()
	badged.icon_name = &"mail"
	badged.caption = "Mail"
	badged.badge_count = 12
	badged.custom_minimum_size = Vector2(88, 88)
	slots.add_child(badged)
	var locked := IconButton.new()
	locked.icon_name = &"lock"
	locked.disabled = true
	slots.add_child(locked)
	var small := IconButton.new()
	small.icon_name = &"settings"
	small.custom_minimum_size = Vector2(52, 52)
	small.size_flags_vertical = SIZE_SHRINK_CENTER
	slots.add_child(small)
	var with_icon := Button.new()
	with_icon.text = "Train"
	with_icon.icon = UiIcons.get_icon(&"infantry")
	with_icon.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	with_icon.theme_type_variation = &"ButtonPrimary"
	with_icon.custom_minimum_size = Vector2(140, 52)
	with_icon.size_flags_vertical = SIZE_SHRINK_CENTER
	slots.add_child(with_icon)

	var toggles := _row(18)
	column.add_child(toggles)
	var checks: Array[Array] = [["Checked", true, false], ["Unchecked", false, false]]
	for entry in checks:
		var box := CheckBox.new()
		box.text = entry[0]
		box.button_pressed = entry[1]
		box.theme_type_variation = &"CheckBoxInk"
		toggles.add_child(box)
	var group := ButtonGroup.new()
	for i in 2:
		var radio := CheckBox.new()
		radio.text = "Radio %d" % (i + 1)
		radio.button_group = group
		radio.button_pressed = i == 0
		radio.theme_type_variation = &"CheckBoxInk"
		toggles.add_child(radio)
	return frame


func _inputs() -> Control:
	var frame := _frame("Inputs, Tabs & Bars", 548)
	frame.size_flags_horizontal = SIZE_EXPAND_FILL
	var column := _column(12)
	frame.add_content(column)
	var fields := _row(12)
	column.add_child(fields)
	var empty := LineEdit.new()
	empty.placeholder_text = "Governor name"
	empty.size_flags_horizontal = SIZE_EXPAND_FILL
	fields.add_child(empty)
	var filled := LineEdit.new()
	filled.text = "Aldric the Bold"
	filled.size_flags_horizontal = SIZE_EXPAND_FILL
	fields.add_child(filled)
	var option := OptionButton.new()
	option.add_item("Sort: Power")
	option.add_item("Sort: Level")
	option.custom_minimum_size = Vector2(170, 46)
	fields.add_child(option)

	var tabs := TabContainer.new()
	tabs.custom_minimum_size.y = 236
	column.add_child(tabs)
	var list := ItemList.new()
	list.name = "Economy"
	list.fixed_icon_size = Vector2i(34, 34)
	list.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	for building: StringName in [&"farm", &"lumber_mill", &"quarry", &"goldmine", &"storehouse", &"academy"]:
		list.add_item("%s  ·  Level %d" % [UiIcons.display_name(building), 3 + list.item_count], UiIcons.get_icon(building))
	list.select(1)
	tabs.add_child(list)
	for tab_name: String in ["Military", "Alliance"]:
		var page := Control.new()
		page.name = tab_name
		tabs.add_child(page)
	tabs.set_tab_disabled(2, true)

	var bars := GridContainer.new()
	bars.columns = 2
	bars.add_theme_constant_override(&"h_separation", 12)
	column.add_child(bars)
	var variants: Array[Array] = [["ProgressBar", &"", 0.65], ["GoldBar", &"GoldBar", 0.4]]
	for variant in variants:
		bars.add_child(_text(variant[0], &"CaptionInk"))
		var bar := ProgressBar.new()
		bar.theme_type_variation = variant[1]
		bar.max_value = 1.0
		bar.value = variant[2]
		bar.custom_minimum_size = Vector2(0, 28)
		bar.size_flags_horizontal = SIZE_EXPAND_FILL
		bars.add_child(bar)
	bars.add_child(_text("TimerProgressBar", &"CaptionInk"))
	var timer := TimerProgressBar.new()
	timer.auto_tick = false
	timer.set_timer(7985, 14400)
	timer.size_flags_horizontal = SIZE_EXPAND_FILL
	bars.add_child(timer)
	return frame


func _icons() -> Control:
	var card := PanelContainer.new()
	card.size_flags_vertical = SIZE_SHRINK_BEGIN
	var column := _column(10)
	card.add_child(column)
	column.add_child(_text("Icons", &"Header"))
	var divider := _divider(false)
	divider.stretch_mode = TextureRect.STRETCH_KEEP
	column.add_child(divider)
	var grid := GridContainer.new()
	grid.columns = 10
	grid.add_theme_constant_override(&"h_separation", 6)
	grid.add_theme_constant_override(&"v_separation", 8)
	column.add_child(grid)
	for icon in UiIcons.NAMES:
		var cell := _column(0)
		cell.custom_minimum_size.x = 73
		var rect := UiIcons.make_rect(icon, 64)
		rect.size_flags_horizontal = SIZE_SHRINK_CENTER
		cell.add_child(rect)
		var caption := _text(String(icon), &"Caption")
		caption.add_theme_font_size_override(&"font_size", 12)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(caption)
		grid.add_child(cell)
	column.add_child(divider.duplicate())
	var sizes := _row(18)
	column.add_child(sizes)
	sizes.add_child(_text("Scales cleanly:", &"Caption"))
	for px: float in [96.0, 64.0, 48.0, 32.0, 24.0]:
		sizes.add_child(UiIcons.make_rect(&"city_hall", px))
		sizes.add_child(UiIcons.make_rect(&"cavalry", px))
	var surfaces := _row(12)
	column.add_child(surfaces)
	var samples: Array[Array] = [["PanelInset", &"PanelInset"], ["PanelChip", &"PanelChip"], ["PanelCard (default)", &"PanelCard"], ["TooltipPanel", &"TooltipPanel"]]
	for sample in samples:
		var panel := PanelContainer.new()
		panel.theme_type_variation = sample[1]
		panel.size_flags_vertical = SIZE_SHRINK_CENTER
		panel.add_child(_text(sample[0], &"Caption"))
		surfaces.add_child(panel)
	var portrait := TextureRect.new()
	portrait.texture = UiIcons.get_texture(&"portrait_frame")
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.custom_minimum_size = Vector2(72, 72)
	surfaces.add_child(portrait)
	var badge := TextureRect.new()
	badge.texture = UiIcons.get_texture(&"level_badge")
	badge.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	surfaces.add_child(badge)
	return card


func _upgrade_window() -> Control:
	var frame := _frame("Farm", 430)
	frame.size_flags_vertical = SIZE_SHRINK_BEGIN
	var column := _column(12)
	frame.add_content(column)
	var head := _row(14)
	column.add_child(head)
	var well := PanelContainer.new()
	well.theme_type_variation = &"PanelInsetLight"
	well.add_child(UiIcons.make_rect(&"farm", 84))
	head.add_child(well)
	var info := _column(2)
	info.size_flags_vertical = SIZE_SHRINK_CENTER
	head.add_child(info)
	info.add_child(_text("Level 3  →  4", &"SubheaderInk"))
	info.add_child(_text("Food per hour  1,200  →  1,560", &"BodyInk"))
	info.add_child(_text("Requires City Hall level 4", &"CaptionInk"))
	column.add_child(_divider(true))
	column.add_child(_text("COST", &"CaptionInk"))
	var cost := CostRow.new()
	cost.set_costs(SAMPLE_COSTS, SAMPLE_OWNED, 7985)
	column.add_child(cost)
	var note := _text("Not enough wood (2,300 short)", &"CaptionInk")
	note.add_theme_color_override(&"font_color", UiColors.INK_DANGER)
	column.add_child(note)
	var buttons := _row(12)
	buttons.alignment = BoxContainer.ALIGNMENT_END
	column.add_child(buttons)
	var info_button := Button.new()
	info_button.text = "Details"
	info_button.custom_minimum_size = Vector2(130, 52)
	buttons.add_child(info_button)
	var upgrade := Button.new()
	upgrade.text = "Upgrade"
	upgrade.icon = UiIcons.get_icon(&"upgrade")
	upgrade.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	upgrade.theme_type_variation = &"ButtonPrimary"
	upgrade.custom_minimum_size = Vector2(150, 52)
	buttons.add_child(upgrade)
	return frame


func _feedback() -> Control:
	var column := _column(12)
	column.size_flags_horizontal = SIZE_EXPAND_FILL
	column.add_child(_text("Toasts, tooltip, costs on dark", &"Caption"))
	var toasts: Array[Array] = [
		["Scout report received", Toast.Kind.INFO],
		["Quarry upgraded to level 5", Toast.Kind.SUCCESS],
		["Storehouse is almost full", Toast.Kind.WARNING],
		["Not enough wood", Toast.Kind.ERROR],
	]
	for entry in toasts:
		var toast := Toast.new()
		toast.configure(entry[0], entry[1])
		toast.size_flags_horizontal = SIZE_SHRINK_BEGIN
		column.add_child(toast)
	var tip := PanelContainer.new()
	tip.theme_type_variation = &"TooltipPanel"
	tip.size_flags_horizontal = SIZE_SHRINK_BEGIN
	tip.add_child(_text("Wood: 1,250,000 / 2,000,000", &"TooltipLabel"))
	column.add_child(tip)
	var dark_cost := PanelContainer.new()
	dark_cost.size_flags_horizontal = SIZE_SHRINK_BEGIN
	var cost := CostRow.new()
	cost.on_dark = true
	cost.set_costs(SAMPLE_COSTS, SAMPLE_OWNED, 95)
	dark_cost.add_child(cost)
	column.add_child(dark_cost)

	return column


func _dialog() -> Control:
	# The real dialog covers its whole parent; here it is boxed in to fit the page.
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(960, 300)
	holder.clip_contents = true
	var dialog := ConfirmDialog.new()
	dialog.setup("Demolish", "Remove this Lumber Mill? Half of its cost is refunded.", "Demolish", "Keep")
	dialog.set_destructive(true)
	holder.add_child(dialog)
	dialog.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	return holder
