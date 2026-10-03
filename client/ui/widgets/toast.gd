class_name Toast
extends PanelContainer
## Short self-dismissing notification (server errors, "Upgrade complete").
##   Toast.popup(self, "Not enough wood", Toast.Kind.ERROR)
## Toasts stack top-centre inside the node you pass.

enum Kind { INFO, SUCCESS, WARNING, ERROR }

## Emitted after the toast has faded out, just before it frees itself.
signal dismissed

const SCENE := "res://ui/widgets/toast.tscn"
const STACK_NAME := "ToastStack"
const ICONS: Dictionary[Kind, StringName] = {
	Kind.INFO: &"info", Kind.SUCCESS: &"check", Kind.WARNING: &"warning", Kind.ERROR: &"warning",
}

var kind := Kind.INFO

var _icon: TextureRect
var _label: Label


func _init() -> void:
	theme_type_variation = &"PanelCard"
	size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 10)
	add_child(row)
	_icon = UiIcons.make_rect(&"info", 30)
	row.add_child(_icon)
	_label = Label.new()
	_label.theme_type_variation = &"Body"
	row.add_child(_label)


## Set the message and style without animating (the static `popup` does both).
func configure(text: String, toast_kind := Kind.INFO) -> void:
	kind = toast_kind
	_label.text = text
	_icon.texture = UiIcons.get_icon(ICONS[kind])
	_label.add_theme_color_override(&"font_color", text_color(kind))


## Fade in, wait `duration` seconds, fade out and free.
func play(duration := 3.0) -> void:
	modulate.a = 0.0
	var tween := create_tween()
	tween.tween_property(self, ^"modulate:a", 1.0, 0.15)
	tween.tween_interval(duration)
	tween.tween_property(self, ^"modulate:a", 0.0, 0.3)
	tween.tween_callback(_finish)


static func text_color(toast_kind: Kind) -> Color:
	match toast_kind:
		Kind.SUCCESS:
			return UiColors.SUCCESS
		Kind.WARNING:
			return UiColors.WARNING
		Kind.ERROR:
			return UiColors.DANGER
	return UiColors.TEXT


## Show a toast inside `parent` (normally the HUD root or a CanvasLayer).
static func popup(parent: Node, text: String, toast_kind := Kind.INFO, duration := 3.0) -> Toast:
	var stack: VBoxContainer = parent.get_node_or_null(STACK_NAME)
	if stack == null:
		stack = VBoxContainer.new()
		stack.name = STACK_NAME
		stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
		parent.add_child(stack)
		stack.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
		stack.offset_top = 84.0
	var toast: Toast = (load(SCENE) as PackedScene).instantiate()
	toast.configure(text, toast_kind)
	stack.add_child(toast)
	toast.play(duration)
	return toast


func _finish() -> void:
	dismissed.emit()
	queue_free()
