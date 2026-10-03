class_name UiIcons
extends RefCounted
## Lookup for the generated icon set in `res://ui/icons/` (see tools/ui/build_icons.py).

const DIR := "res://ui/icons/"
const TEXTURE_DIR := "res://ui/theme/textures/"

## Every icon that ships. A unit test checks each one exists.
const NAMES: Array[StringName] = [
	&"food", &"wood", &"stone", &"gold", &"time", &"speedup", &"power",
	&"infantry", &"cavalry", &"archer", &"siege",
	&"city_hall", &"farm", &"lumber_mill", &"quarry", &"goldmine", &"storehouse",
	&"barracks", &"archery_range", &"stable", &"siege_workshop", &"hospital", &"academy",
	&"upgrade", &"build", &"research", &"commander", &"alliance", &"mail", &"map", &"city",
	&"settings", &"close", &"back", &"info", &"check", &"lock", &"warning",
]

## Player-facing names for resource ids used in tooltips.
const RESOURCE_NAMES: Dictionary[StringName, String] = {
	&"food": "Food", &"wood": "Wood", &"stone": "Stone", &"gold": "Gold",
}
## Display order for resources.
const RESOURCE_ORDER: Array[StringName] = [&"food", &"wood", &"stone", &"gold"]


static func has_icon(icon: StringName) -> bool:
	return ResourceLoader.exists(DIR + icon + ".png")


## Icon texture by id (a resource, troop or building id, or a glyph name), or null.
static func get_icon(icon: StringName) -> Texture2D:
	if not has_icon(icon):
		push_warning("UiIcons: no icon named '%s'" % icon)
		return null
	return load(DIR + icon + ".png")


## A theme texture such as "divider" or "portrait_frame".
static func get_texture(texture: StringName) -> Texture2D:
	return load(TEXTURE_DIR + texture + ".png")


## A square TextureRect showing `icon` at `size` px, filtered for clean downscaling.
static func make_rect(icon: StringName, size: float) -> TextureRect:
	var rect := TextureRect.new()
	rect.texture = get_icon(icon) if icon != &"" else null
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	rect.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	rect.custom_minimum_size = Vector2(size, size)
	rect.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rect


## Display name for an id: "lumber_mill" -> "Lumber Mill".
static func display_name(id: StringName) -> String:
	if RESOURCE_NAMES.has(id):
		return RESOURCE_NAMES[id]
	return String(id).capitalize()
