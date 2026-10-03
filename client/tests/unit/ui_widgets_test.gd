extends TestCase

const THEME_PATH := "res://ui/theme/main_theme.tres"
const WIDGETS: Array[String] = [
	"resource_chip", "resource_bar", "timer_progress_bar", "icon_button",
	"panel_frame", "cost_row", "toast", "confirm_dialog",
]


func test_every_listed_icon_exists() -> void:
	for icon in UiIcons.NAMES:
		assert_true(UiIcons.has_icon(icon), "icon %s" % icon)


func test_every_building_model_has_an_icon() -> void:
	var count := 0
	for file in DirAccess.get_files_at("res://assets/models/"):
		if file.ends_with(".glb"):
			count += 1
			# models are <kind>_t<tier>.glb (docs/ART_BIBLE.md); icons are per kind
			var kind := file.get_basename().rsplit("_t", true, 1)[0]
			assert_true(UiIcons.has_icon(StringName(kind)), "icon for %s" % file)
	assert_true(count > 0, "found building models")


func test_display_name() -> void:
	assert_eq(UiIcons.display_name(&"food"), "Food")
	assert_eq(UiIcons.display_name(&"lumber_mill"), "Lumber Mill")


func test_theme_is_the_project_default_and_has_variations() -> void:
	assert_eq(ProjectSettings.get_setting("gui/theme/custom"), THEME_PATH)
	var theme: Theme = load(THEME_PATH)
	for variation: StringName in [&"ButtonPrimary", &"ButtonGold", &"ButtonDanger", &"IconSlot", &"CloseButton"]:
		assert_eq(theme.get_type_variation_base(variation), &"Button", variation)
	for variation: StringName in [&"HeaderLarge", &"Header", &"Body", &"Caption", &"ResourceValue", &"TimerValue", &"BodyInk"]:
		assert_eq(theme.get_type_variation_base(variation), &"Label", variation)
	for variation: StringName in [&"PanelWood", &"PanelParchment", &"PanelCard", &"PanelChip", &"PanelPlaque", &"PanelInset"]:
		assert_true(theme.has_stylebox(&"panel", variation), variation)
	assert_eq(theme.get_type_variation_base(&"ConstructionBar"), &"ProgressBar")
	assert_true(theme.has_stylebox(&"fill", &"ConstructionBar"), "construction fill")


func test_widget_scenes_instantiate() -> void:
	for widget in WIDGETS:
		var scene: PackedScene = load("res://ui/widgets/%s.tscn" % widget)
		var node := scene.instantiate()
		assert_true(node is Control, widget)
		node.free()


func test_cost_row_missing() -> void:
	var costs := {"food": 1200, "wood": 8400, "stone": 0}
	assert_eq(CostRow.missing(costs, {"food": 1200, "wood": 6100}), {"wood": 2300})
	assert_eq(CostRow.missing(costs, {"food": 5000, "wood": 9000}), {})
	assert_eq(CostRow.missing(costs, {}), {"food": 1200, "wood": 8400}, "nothing owned")


func test_cost_row_orders_resources_and_skips_zero() -> void:
	var kinds := CostRow.ordered_kinds({"gold": 5, "relic": 1, "wood": 10, "stone": 0, "food": 3})
	var expected: Array[StringName] = [&"food", &"wood", &"gold", &"relic"]
	assert_eq(kinds, expected)


func test_cost_row_affordability_and_entries() -> void:
	var row := CostRow.new()
	row.set_costs({"food": 100, "wood": 200}, {"food": 100, "wood": 150}, 60.0)
	assert_true(not row.is_affordable(), "short on wood")
	assert_eq(row.get_child_count(), 3, "food, wood, time")
	row.set_available({"food": 100, "wood": 200})
	assert_true(row.is_affordable(), "exactly enough")
	row.free()


func test_resource_chip_text_and_tooltip() -> void:
	var chip := ResourceChip.new()
	chip.kind = &"wood"
	chip.set_amount(12431, 50000)
	assert_eq(chip.tooltip_text, "Wood: 12,431 / 50,000")
	assert_true(not chip.is_full())
	chip.set_amount(50000, 50000)
	assert_true(chip.is_full())
	assert_eq(chip.tooltip_text, "Wood: 50,000 / 50,000 (full)")
	assert_eq(ResourceChip.tooltip_for(&"food", 950), "Food: 950")
	chip.free()


func test_resource_bar_routes_amounts_to_chips() -> void:
	var bar := ResourceBar.new()
	bar.set_amounts({"food": 1500, "gold": 7, "unknown": 1})
	assert_eq(bar.get_chip(&"food").amount, 1500)
	assert_eq(bar.get_chip(&"gold").amount, 7)
	assert_eq(bar.get_chip(&"wood").amount, 0)
	assert_true(bar.get_chip(&"unknown") == null, "unknown kinds are ignored")
	bar.free()


func test_timer_progress_bar() -> void:
	var bar := TimerProgressBar.new()
	bar.set_timer(7985, 14400)
	assert_true(bar.is_running())
	assert_true(is_equal_approx(bar.value, 1.0 - 7985.0 / 14400.0), "progress value")
	bar.set_timer(0, 14400)
	assert_true(not bar.is_running())
	assert_eq(bar.value, 1.0)
	bar.free()


func test_toast_kinds_have_icons() -> void:
	for kind: Toast.Kind in Toast.Kind.values():
		assert_true(UiIcons.has_icon(Toast.ICONS[kind]), "toast kind %d" % kind)
