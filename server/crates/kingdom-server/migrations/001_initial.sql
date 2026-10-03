CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE credentials (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    password_hash TEXT NOT NULL
);
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id)
);
CREATE TABLE cities (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    state_json TEXT NOT NULL
);
PRAGMA user_version = 1;
