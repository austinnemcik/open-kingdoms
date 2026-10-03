extends Node
## Autoload "GameState": the client's copy of server state. The server is the
## source of truth; this only caches what it last sent.

var player_id := 0
var player_name := ""
var city: Dictionary = {}
