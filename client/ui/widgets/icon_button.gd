class_name IconButton
extends Button
## Square icon button for HUD actions. Optional caption along the bottom and a
## red count badge in the corner (unread mail, idle builders...).
## It is a normal Button: connect `pressed`.

## Icon id from `UiIcons`, e.g. &"build".
@export var icon_name: StringName = &"":
	set(value):
		icon_name = value
		_icon.texture = UiIcons.get_icon(value) if value != &"" else null
## Short label drawn over the bottom edge. Empty for none.
@export var caption := "":
	set(value):
		caption = value
		_caption.text = value
		_caption.visible = not value.is_empty()
		_layout()
## Number in the corner badge; 0 hides it.
@export var badge_count := 0:
	set(value):
		badge_count = value
		_badge.visible = value > 0
		_badge_label.text = "99+" if value > 99 else str(value)

var _icon: TextureRect
var _caption: Label
var _badge: TextureRect
var _badge_label: Label


func _init() -> void:
	theme_type_variation = &"IconSlot"
	custom_minimum_size = Vector2(76, 76)
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_icon = UiIcons.make_rect(&"", 0)
	add_child(_icon)
	_caption = Label.new()
	_caption.theme_type_variation = &"BadgeValue"
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_caption.visible = false
	add_child(_caption)
	_badge = TextureRect.new()
	_badge.texture = UiIcons.get_texture(&"level_badge")
	_badge.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_badge.visible = false
	add_child(_badge)
	_badge_label = Label.new()
	_badge_label.theme_type_variation = &"BadgeValue"
	_badge_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_badge_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_badge.add_child(_badge_label)
	_badge_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_badge_label.offset_top = -2.0
	resized.connect(_layout)
	button_down.connect(_layout)
	button_up.connect(_layout)


func _ready() -> void:
	_layout()


func _layout() -> void:
	# The visible face stops ~7px above the bottom edge (the ledge below it).
	var pad := size.x * 0.17
	var press := 3.0 if is_pressed() else 0.0
	var face_bottom := size.y - 7.0
	var icon_bottom := face_bottom - pad - (10.0 if not caption.is_empty() else 0.0)
	_icon.position = Vector2(pad, pad + press)
	_icon.size = Vector2(size.x - pad * 2.0, maxf(icon_bottom - pad, 0.0))
	_caption.position = Vector2(0, face_bottom - 24.0 + press)
	_caption.size = Vector2(size.x, 22)
	_badge.size = Vector2(30, 30)
	_badge.position = Vector2(size.x - 22.0, -8.0)
	_icon.modulate = Color(1, 1, 1, 0.45) if disabled else Color.WHITE
