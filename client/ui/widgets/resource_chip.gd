class_name ResourceChip
extends PanelContainer
## One HUD counter: icon + compact value ("12.4K"). The tooltip shows the exact
## value and capacity. Presentation only: call `set_amount` when state changes.

const ICON_SIZE := 30.0

## Resource (or any icon) id, e.g. &"food".
@export var kind: StringName = &"food":
	set = set_kind

var amount := 0
## Storage cap, or -1 when there is none. The value turns amber when full.
var capacity := -1

var _icon: TextureRect
var _label: Label


func _init() -> void:
	theme_type_variation = &"PanelChip"
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 6)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(row)
	_icon = UiIcons.make_rect(&"", ICON_SIZE)
	row.add_child(_icon)
	_label = Label.new()
	_label.theme_type_variation = &"ResourceValue"
	_label.custom_minimum_size.x = 56
	row.add_child(_label)
	set_kind(kind)


func set_kind(value: StringName) -> void:
	kind = value
	if _icon != null:
		_icon.texture = UiIcons.get_icon(kind)
		_refresh()


func set_amount(value: int, cap := -1) -> void:
	amount = value
	capacity = cap
	_refresh()


## True when a capacity is set and reached.
func is_full() -> bool:
	return capacity >= 0 and amount >= capacity


func _refresh() -> void:
	_label.text = UiFormat.compact(amount)
	_label.add_theme_color_override(&"font_color", UiColors.WARNING if is_full() else UiColors.TEXT)
	tooltip_text = tooltip_for(kind, amount, capacity)


## Tooltip text, e.g. "Food: 12,431 / 50,000".
static func tooltip_for(resource: StringName, value: int, cap := -1) -> String:
	var text := "%s: %s" % [UiIcons.display_name(resource), UiFormat.exact(value)]
	if cap >= 0:
		text += " / %s" % UiFormat.exact(cap)
		if value >= cap:
			text += " (full)"
	return text
