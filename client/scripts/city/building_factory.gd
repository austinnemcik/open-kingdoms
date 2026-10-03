class_name BuildingFactory
## Creates the 3D node for a building kind. Uses the Blender-generated model in
## res://assets/models/<kind>.glb when present, otherwise a coloured box so new
## building kinds are visible before their art exists.

const MODEL_DIR := "res://assets/models/"


static func model_path(kind: String) -> String:
	return MODEL_DIR + kind + ".glb"


static func create(kind: String, footprint: int) -> Node3D:
	var path := model_path(kind)
	if ResourceLoader.exists(path):
		var scene: PackedScene = load(path)
		if scene:
			return scene.instantiate()
	return _placeholder(kind, footprint)


static func _placeholder(kind: String, footprint: int) -> Node3D:
	var mesh := BoxMesh.new()
	var height := 0.6 * footprint
	mesh.size = Vector3(footprint * 0.85, height, footprint * 0.85)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color.from_hsv(float(kind.hash() % 360) / 360.0, 0.45, 0.8)
	mesh.material = material
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.position.y = height / 2.0
	var root := Node3D.new()
	root.add_child(instance)
	return root
