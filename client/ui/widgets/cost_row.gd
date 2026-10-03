class_name CostRow
extends HBoxContainer
## Resource cost list ("icon 1.2K  icon 800  clock 2h 13m"). Entries the player
## cannot afford turn red. Display only: the server still validates every cost.

## Set when the row sits on a dark surface instead of parchment.
@export var on_dark := false:
	set(value):
		on_dark = value
		_rebuild()
## Icon size in px.
@export var icon_size := 28.0:
	set(value):
		icon_size = value
		_rebuild()

var _costs: Dictionary = {}
var _available: Dictionary = {}
var _duration := -1.0


func _init() -> void:
	add_theme_constant_override(&"separation", 14)


## `costs` and `available` map resource id -> amount. Zero costs are hidden.
## Pass `duration_s` >= 0 to append a time entry.
func set_costs(costs: Dictionary, available: Dictionary = {}, duration_s := -1.0) -> void:
	_costs = costs
	_available = available
	_duration = duration_s
	_rebuild()


## Update only what the player owns (e.g. as resources tick up).
func set_available(available: Dictionary) -> void:
	_available = available
	_rebuild()


func is_affordable() -> bool:
	return missing(_costs, _available).is_empty()


## Shortfall per resource: only the entries where `available` < `costs`.
static func missing(costs: Dictionary, available: Dictionary) -> Dictionary:
	var out := {}
	for key: Variant in costs:
		var short := int(costs[key]) - int(available.get(key, 0))
		if int(costs[key]) > 0 and short > 0:
			out[key] = short
	return out


## Resource ids with a non-zero cost: known resources first, then the rest by name.
static func ordered_kinds(costs: Dictionary) -> Array[StringName]:
	var present: Dictionary[StringName, bool] = {}
	for key: Variant in costs:
		if int(costs[key]) > 0:
			present[StringName(str(key))] = true
	var out: Array[StringName] = []
	for kind in UiIcons.RESOURCE_ORDER:
		if present.erase(kind):
			out.append(kind)
	var rest: Array[StringName] = present.keys()
	rest.sort_custom(func(a: StringName, b: StringName) -> bool: return String(a) < String(b))
	out.append_array(rest)
	return out


func _rebuild() -> void:
	for child in get_children():
		remove_child(child)
		child.queue_free()
	var short := missing(_costs, _available)
	for kind in ordered_kinds(_costs):
		var cost := int(_costs.get(kind, _costs.get(String(kind), 0)))
		var have := int(_available.get(kind, _available.get(String(kind), 0)))
		var lacking := short.has(kind) or short.has(String(kind))
		var tip := "%s: %s needed, %s available" % [UiIcons.display_name(kind), UiFormat.exact(cost), UiFormat.exact(have)]
		_add_entry(kind, UiFormat.compact(cost), lacking, tip)
	if _duration >= 0.0:
		_add_entry(&"time", UiFormat.duration_short(_duration), false, "Time: %s" % UiFormat.duration(_duration))


func _add_entry(icon: StringName, text: String, lacking: bool, tip: String) -> void:
	var entry := HBoxContainer.new()
	entry.add_theme_constant_override(&"separation", 5)
	entry.tooltip_text = tip
	entry.mouse_filter = Control.MOUSE_FILTER_PASS
	entry.add_child(UiIcons.make_rect(icon, icon_size))
	var label := Label.new()
	label.theme_type_variation = &"ResourceValue" if on_dark else &"ResourceValueInk"
	label.text = text
	if lacking:
		label.add_theme_color_override(&"font_color", UiColors.DANGER if on_dark else UiColors.INK_DANGER)
	entry.add_child(label)
	add_child(entry)
