-- Legacy bearer tokens are deliberately revoked: their creation time is unknown.
DROP TABLE sessions;
CREATE TABLE sessions (
    token_hash BLOB PRIMARY KEY CHECK(length(token_hash) = 32),
    player_id INTEGER NOT NULL REFERENCES players(id),
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL CHECK(expires_at > created_at)
);
CREATE INDEX sessions_player_created ON sessions(player_id, created_at);
CREATE INDEX sessions_expiry ON sessions(expires_at);
PRAGMA user_version = 2;
