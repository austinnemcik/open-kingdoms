class_name Protocol
## GDScript mirror of server/crates/protocol. Messages are JSON objects with a
## snake_case "type" field. Keep in sync with the Rust crate and bump VERSION
## together with PROTOCOL_VERSION on breaking changes.

const VERSION := 1


static func encode(msg: Dictionary) -> String:
	assert(msg.has("type"), "protocol messages need a type")
	return JSON.stringify(msg)


## Returns the decoded message, or an empty Dictionary if the text is not a
## JSON object with a string "type".
static func decode(text: String) -> Dictionary:
	var json := JSON.new()
	if json.parse(text) != OK:
		return {}
	var parsed: Variant = json.data
	if parsed is Dictionary and parsed.get("type") is String:
		return parsed
	return {}


static func hello() -> Dictionary:
	return {"type": "hello", "protocol": VERSION}


static func login(player_name: String) -> Dictionary:
	return {"type": "login", "name": player_name}


static func get_city() -> Dictionary:
	return {"type": "get_city"}
