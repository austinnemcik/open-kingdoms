class_name ResourceBar
extends HBoxContainer
## Row of `ResourceChip`s for the top of the HUD. Feed it state with
## `set_amounts({"food": 1200, ...})`; it never talks to the network.

## Which resources to show, in order.
@export var kinds: Array[StringName] = [&"food", &"wood", &"stone", &"gold"]:
	set(value):
		kinds = value
		_rebuild()

var _chips: Dictionary[StringName, ResourceChip] = {}


func _init() -> void:
	add_theme_constant_override(&"separation", 10)
	_rebuild()


## Update every chip present in `amounts` (resource id -> int). `capacities` is optional.
func set_amounts(amounts: Dictionary, capacities: Dictionary = {}) -> void:
	for key: Variant in amounts:
		set_amount(StringName(str(key)), int(amounts[key]), int(capacities.get(key, -1)))


func set_amount(kind: StringName, amount: int, capacity := -1) -> void:
	var chip := get_chip(kind)
	if chip != null:
		chip.set_amount(amount, capacity)


func get_chip(kind: StringName) -> ResourceChip:
	return _chips.get(kind)


func _rebuild() -> void:
	for chip: ResourceChip in _chips.values():
		remove_child(chip)
		chip.queue_free()
	_chips.clear()
	for kind in kinds:
		var chip := ResourceChip.new()
		chip.kind = kind
		add_child(chip)
		_chips[kind] = chip
