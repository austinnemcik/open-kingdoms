extends Control
## Login screen: enter a name, connect, then switch to the city view.

@onready var _name_edit: LineEdit = %NameEdit
@onready var _server_edit: LineEdit = %ServerEdit
@onready var _status: Label = %Status
@onready var _play_button: Button = %PlayButton


func _ready() -> void:
	_server_edit.text = Net.DEFAULT_URL
	_play_button.pressed.connect(_on_play)
	_name_edit.text_submitted.connect(func(_t: String) -> void: _on_play())
	Net.status_changed.connect(func(text: String) -> void: _status.text = text)
	Net.logged_in.connect(_on_logged_in)
	Net.city_received.connect(_on_city_received)
	_name_edit.grab_focus()


func _on_play() -> void:
	_play_button.disabled = true
	Net.login(_name_edit.text.strip_edges(), _server_edit.text.strip_edges())
	get_tree().create_timer(3.0).timeout.connect(func() -> void: _play_button.disabled = false)


func _on_logged_in(player_id: int, player_name: String) -> void:
	GameState.player_id = player_id
	GameState.player_name = player_name


func _on_city_received(city: Dictionary) -> void:
	GameState.city = city
	get_tree().change_scene_to_file("res://scenes/city.tscn")
