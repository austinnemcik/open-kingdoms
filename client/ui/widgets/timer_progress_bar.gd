class_name TimerProgressBar
extends ProgressBar
## Progress bar with a countdown label ("02:13:05") for construction, training
## and research. Call `set_timer(remaining, total)` whenever the server sends a
## completion time; between updates it counts down locally for smooth motion.

## Emitted once when the countdown reaches zero.
signal finished

## Count down locally every frame. Turn off to drive it entirely from outside.
@export var auto_tick := true
## Optional text before the time, e.g. "Upgrading".
@export var prefix := "":
	set(value):
		prefix = value
		_refresh()

var total_seconds := 0.0
var remaining_seconds := 0.0

var _label: Label


func _init() -> void:
	theme_type_variation = &"ConstructionBar"
	show_percentage = false
	min_value = 0.0
	max_value = 1.0
	step = 0.0
	custom_minimum_size = Vector2(160, 28)
	_label = Label.new()
	_label.theme_type_variation = &"TimerValue"
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_label)
	_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_label.offset_top = -1.0
	_refresh()


func set_timer(remaining: float, total: float) -> void:
	total_seconds = maxf(total, 0.0)
	remaining_seconds = clampf(remaining, 0.0, total_seconds)
	_refresh()


func is_running() -> bool:
	return remaining_seconds > 0.0


func _process(delta: float) -> void:
	if not auto_tick or remaining_seconds <= 0.0:
		return
	remaining_seconds = maxf(remaining_seconds - delta, 0.0)
	_refresh()
	if remaining_seconds == 0.0:
		finished.emit()


func _refresh() -> void:
	if _label == null:
		return
	value = UiFormat.progress(remaining_seconds, total_seconds)
	var time := UiFormat.duration(remaining_seconds)
	_label.text = time if prefix.is_empty() else "%s  %s" % [prefix, time]
