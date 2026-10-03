class_name CameraRig
extends Node3D
## Isometric-style strategy camera: a fixed pitch and yaw looking at a focus
## point. Pan with WASD/arrow keys or left-drag, zoom with the mouse wheel.

@export var pitch_degrees := 50.0
@export var yaw_degrees := 45.0
@export var distance := 30.0
@export var min_distance := 10.0
@export var max_distance := 60.0
@export var pan_speed := 20.0
## Half-extent of the square area the focus point may move within.
@export var bounds := 20.0

var camera := Camera3D.new()
var _dragging := false


func _ready() -> void:
	camera.fov = 35.0
	camera.far = 500.0
	add_child(camera)
	_update_camera()


func _process(delta: float) -> void:
	var input := Vector2(
		Input.get_axis(&"ui_left", &"ui_right"),
		Input.get_axis(&"ui_up", &"ui_down"),
	)
	if input != Vector2.ZERO:
		_pan(input * pan_speed * delta * (distance / 30.0))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		match event.button_index:
			MOUSE_BUTTON_WHEEL_UP:
				distance = maxf(min_distance, distance * 0.9)
				_update_camera()
			MOUSE_BUTTON_WHEEL_DOWN:
				distance = minf(max_distance, distance * 1.1)
				_update_camera()
			MOUSE_BUTTON_LEFT:
				_dragging = event.pressed
	elif event is InputEventMouseMotion and _dragging:
		_pan(-event.relative * 0.03 * (distance / 30.0))


## Move the focus point by `screen_delta`, interpreted in screen axes.
func _pan(screen_delta: Vector2) -> void:
	var yaw := deg_to_rad(yaw_degrees)
	var right := Vector3(cos(yaw), 0.0, -sin(yaw))
	var forward := Vector3(sin(yaw), 0.0, cos(yaw))
	position += right * screen_delta.x + forward * screen_delta.y
	position.x = clampf(position.x, -bounds, bounds)
	position.z = clampf(position.z, -bounds, bounds)


func _update_camera() -> void:
	var pitch := deg_to_rad(pitch_degrees)
	var yaw := deg_to_rad(yaw_degrees)
	var offset := Vector3(sin(yaw), 0.0, cos(yaw)) * cos(pitch) * distance + Vector3.UP * sin(pitch) * distance
	# Local transform: sit at `offset` and look back at the rig's origin.
	camera.transform = Transform3D(Basis.looking_at(-offset, Vector3.UP), offset)
