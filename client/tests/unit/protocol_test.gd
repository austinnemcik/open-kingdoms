extends TestCase


func test_encode_decode_round_trip() -> void:
	var msg := Protocol.login("alice")
	assert_eq(Protocol.decode(Protocol.encode(msg)), msg)


func test_hello_carries_protocol_version() -> void:
	assert_eq(Protocol.hello(), {"type": "hello", "protocol": Protocol.VERSION})


func test_decode_rejects_non_messages() -> void:
	assert_eq(Protocol.decode("not json"), {}, "garbage")
	assert_eq(Protocol.decode("[1, 2]"), {}, "array")
	assert_eq(Protocol.decode("{\"no_type\": 1}"), {}, "missing type")
