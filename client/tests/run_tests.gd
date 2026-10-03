extends SceneTree
## Headless unit-test runner. Exit code 0 = all passed.
##   godot --headless --path client -s res://tests/run_tests.gd

const UNIT_DIR := "res://tests/unit/"


func _initialize() -> void:
	var passed := 0
	var failed := 0
	for file in DirAccess.get_files_at(UNIT_DIR):
		if not file.ends_with("_test.gd"):
			continue
		var script: GDScript = load(UNIT_DIR + file)
		for method in script.get_script_method_list():
			var test_name: String = method.name
			if not test_name.begins_with("test_"):
				continue
			var test: TestCase = script.new()
			test.call(test_name)
			if test.failures.is_empty():
				passed += 1
			else:
				failed += 1
				for f in test.failures:
					printerr("FAIL %s::%s  %s" % [file, test_name, f])
	print("%d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 or passed == 0 else 0)
