class_name PanelFrame
extends PanelContainer
## Titled window: wood frame, crimson title plaque straddling the top edge,
## parchment body and an optional close button. Put your UI in it with
## `add_content(node)` (or add children to `content`).

## Emitted when the close button is pressed. The frame does not hide itself.
signal close_requested

@export var title := "Title":
	set(value):
		title = value
		_title.text = value
		_plaque.reset_size()
		_fit()
@export var show_close := true:
	set(value):
		show_close = value
		_close.visible = value

## Parchment area that holds the window's content.
var content: MarginContainer

var _title: Label
var _plaque: PanelContainer
var _close: Button


func _init() -> void:
	theme_type_variation = &"PanelWood"
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", 0)
	add_child(column)
	var spacer := Control.new()
	spacer.custom_minimum_size.y = 14
	column.add_child(spacer)
	var body := PanelContainer.new()
	body.theme_type_variation = &"PanelParchment"
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(body)
	content = MarginContainer.new()
	body.add_child(content)

	# Decorations float over the frame instead of taking part in its layout.
	var overlay := Control.new()
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(overlay)
	_plaque = PanelContainer.new()
	_plaque.theme_type_variation = &"PanelPlaque"
	_plaque.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(_plaque)
	_plaque.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_plaque.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_plaque.offset_top = -52.0
	_plaque.offset_bottom = 12.0
	_title = Label.new()
	_title.theme_type_variation = &"Title"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.text = title
	_plaque.add_child(_title)

	_close = Button.new()
	_close.theme_type_variation = &"CloseButton"
	_close.tooltip_text = "Close"
	_close.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	overlay.add_child(_close)
	_close.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_close.offset_left = -30.0
	_close.offset_right = 18.0
	_close.offset_top = -42.0
	_close.offset_bottom = 8.0
	var cross := UiIcons.make_rect(&"close", 0)
	_close.add_child(cross)
	cross.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	cross.offset_left = 13.0
	cross.offset_right = -13.0
	cross.offset_top = 11.0
	cross.offset_bottom = -17.0
	_close.pressed.connect(close_requested.emit)
	_fit()


## Add a control to the parchment body.
func add_content(node: Control) -> void:
	content.add_child(node)


func _fit() -> void:
	# Keep the frame wider than its plaque so the title never overhangs.
	custom_minimum_size.x = maxf(custom_minimum_size.x, _plaque.get_combined_minimum_size().x + 96.0)
