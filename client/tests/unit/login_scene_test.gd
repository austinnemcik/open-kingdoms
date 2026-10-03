extends TestCase


func test_login_scene_loads_and_has_connection_fields() -> void:
	# The headless e2e enters the city directly; it missed a BOM that made this
	# main scene unparseable in the exported client.
	var scene: PackedScene = load("res://scenes/login.tscn")
	assert_true(scene != null, "login scene must parse")
	if scene == null:
		return
	var login: Control = scene.instantiate()
	assert_true(login.get_node("Center/Panel/NameEdit") is LineEdit)
	assert_true(login.get_node("Center/Panel/PasswordEdit") is LineEdit)
	assert_true(login.get_node("Center/Panel/ServerEdit") is LineEdit)
	login.free()
