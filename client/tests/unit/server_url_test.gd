extends TestCase

const Connection = preload("res://scripts/net/net.gd")


func test_page_origin_becomes_websocket_endpoint() -> void:
	assert_eq(Connection.url_from_location("http:", "localhost:8123"), "ws://localhost:8123/ws")
	assert_eq(Connection.url_from_location("https:", "kingdom.example"), "wss://kingdom.example/ws")
	assert_eq(Connection.url_from_location("https:", "kingdom.example:8443"), "wss://kingdom.example:8443/ws")
	assert_eq(Connection.url_from_location("http:", "[::1]:7777"), "ws://[::1]:7777/ws")


func test_missing_or_unsupported_location_uses_desktop_default() -> void:
	assert_eq(Connection.url_from_location("", ""), Connection.DEFAULT_URL)
	assert_eq(Connection.url_from_location("file:", ""), Connection.DEFAULT_URL)
	assert_eq(Connection.url_from_location("https:", ""), Connection.DEFAULT_URL)
	assert_eq(Net.default_url(), Connection.DEFAULT_URL)
