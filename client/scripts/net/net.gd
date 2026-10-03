extends Node
## Autoload "Net": the single WebSocket connection to the kingdom server.
## Runs the hello -> login -> get_city handshake and re-emits server messages.

signal status_changed(text: String)
signal logged_in(player_id: int, player_name: String)
signal city_received(city: Dictionary)
signal server_error(code: String, message: String)
signal message_received(msg: Dictionary)

const DEFAULT_URL := "ws://127.0.0.1:7777/ws"

var _socket := WebSocketPeer.new()
var _last_state := WebSocketPeer.STATE_CLOSED
var _pending_login := ""
var _pending_password := ""
var _resume_token := ""
var session_token := ""


## Connect and log in as `player_name`; progress is reported via signals.
func login(player_name: String, password: String, url: String = DEFAULT_URL) -> void:
	_pending_login = player_name
	_pending_password = password
	_resume_token = ""
	_connect(url)


## Reconnect using an in-memory bearer token.
func resume(token: String, url: String = DEFAULT_URL) -> void:
	_pending_password = ""
	_resume_token = token
	_connect(url)


func _connect(url: String) -> void:
	_socket = WebSocketPeer.new()
	_last_state = WebSocketPeer.STATE_CLOSED
	var err := _socket.connect_to_url(url)
	if err != OK:
		status_changed.emit("Could not connect (%s)" % error_string(err))
	else:
		status_changed.emit("Connecting to %s..." % url)


func send(msg: Dictionary) -> void:
	if is_open():
		_socket.send_text(Protocol.encode(msg))


func is_open() -> bool:
	return _socket.get_ready_state() == WebSocketPeer.STATE_OPEN


func _process(_delta: float) -> void:
	_socket.poll()
	var state := _socket.get_ready_state()
	if state != _last_state:
		_last_state = state
		if state == WebSocketPeer.STATE_OPEN:
			status_changed.emit("Connected")
			send(Protocol.hello())
		elif state == WebSocketPeer.STATE_CLOSED:
			status_changed.emit("Disconnected")
	while is_open() and _socket.get_available_packet_count() > 0:
		var msg := Protocol.decode(_socket.get_packet().get_string_from_utf8())
		if not msg.is_empty():
			_handle(msg)


func _handle(msg: Dictionary) -> void:
	match msg.type:
		"welcome":
			send(Protocol.resume(_resume_token) if not _resume_token.is_empty() else Protocol.login(_pending_login, _pending_password))
			_pending_password = ""
		"logged_in":
			session_token = msg.token
			logged_in.emit(int(msg.player_id), msg.name)
			send(Protocol.get_city())
		"city_state":
			city_received.emit(msg.city)
		"error":
			server_error.emit(msg.code, msg.message)
			status_changed.emit("Error: %s" % msg.message)
	message_received.emit(msg)
