class_name TestCase
extends RefCounted
## Minimal unit-test base. Subclasses in tests/unit/*_test.gd define
## `func test_*()` methods; tests/run_tests.gd discovers and runs them.

var failures: PackedStringArray = []


func assert_eq(actual: Variant, expected: Variant, context := "") -> void:
	if actual != expected:
		failures.append("%sexpected %s, got %s" % [_prefix(context), var_to_str(expected), var_to_str(actual)])


func assert_true(condition: bool, context := "") -> void:
	if not condition:
		failures.append("%sexpected true" % _prefix(context))


func assert_almost_eq(actual: Vector3, expected: Vector3, context := "") -> void:
	if not actual.is_equal_approx(expected):
		failures.append("%sexpected %s, got %s" % [_prefix(context), expected, actual])


func _prefix(context: String) -> String:
	return context + ": " if context else ""
