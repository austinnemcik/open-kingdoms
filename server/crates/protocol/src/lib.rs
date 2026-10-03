//! Wire protocol between the Godot client and the kingdom server.
//!
//! Messages are JSON text frames over a WebSocket. Every message is an object
//! with a `"type"` field in snake_case, e.g. `{"type":"login","name":"alice"}`.
//! The GDScript mirror lives in `client/scripts/net/protocol.gd`; keep both in
//! sync and bump [`PROTOCOL_VERSION`] on breaking changes.

use serde::{Deserialize, Serialize};

/// Bumped whenever a message shape changes incompatibly.
pub const PROTOCOL_VERSION: u32 = 2;

/// Messages sent by the client.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ClientMsg {
    /// First message on every connection.
    Hello {
        protocol: u32,
    },
    /// Log in (or register, if the name is new). Must follow `Hello`.
    Login {
        name: String,
        password: String,
    },
    /// Reconnect with a previously issued bearer token.
    Resume {
        token: String,
    },
    /// Request a full snapshot of the player's city.
    GetCity,
    /// Upgrade a building in the authenticated player's city.
    UpgradeBuilding {
        building_id: u32,
    },
    /// Construct a building in the authenticated owner's city.
    BuildBuilding {
        kind: String,
        x: u32,
        y: u32,
    },
    /// Cancel an unfinished upgrade and refund its paid cost.
    CancelUpgrade {
        building_id: u32,
    },
    Ping {
        nonce: u32,
    },
}

/// Messages sent by the server.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ServerMsg {
    Welcome {
        protocol: u32,
        server_version: String,
    },
    LoggedIn {
        player_id: u64,
        name: String,
        token: String,
    },
    /// Unsolicited full snapshot after a city change or timer completion.
    CityUpdate {
        city: CityView,
    },
    CityState {
        city: CityView,
    },
    Pong {
        nonce: u32,
    },
    Error {
        code: ErrorCode,
        message: String,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    BadMessage,
    ProtocolMismatch,
    NotLoggedIn,
    AlreadyLoggedIn,
    InvalidName,
    InvalidCredentials,
    Internal,
    InvalidAction,
}

/// Client-facing snapshot of a city.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CityView {
    /// Width/height of the square city grid, in tiles.
    pub size: u32,
    pub builder_slots: u32,
    pub resources: ResourcesView,
    /// Production rates in whole resource units per hour.
    pub rates_per_hour: ResourcesView,
    pub capacity: ResourcesView,
    /// Snapshot accounting time in Unix seconds.
    pub as_of: u64,
    pub buildings: Vec<BuildingView>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResourcesView {
    pub food: u64,
    pub wood: u64,
    pub stone: u64,
    pub gold: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BuildingView {
    pub id: u32,
    /// Building type id from `data/buildings.yaml`, e.g. `"city_hall"`.
    pub kind: String,
    /// Display name, so the client needs no copy of the data files yet.
    pub name: String,
    pub level: u32,
    /// Top-left tile of the footprint.
    pub x: u32,
    pub y: u32,
    /// Footprint edge length in tiles.
    pub footprint: u32,
    pub state: BuildingState,
    /// Unix seconds, null when no job is active.
    pub started_at: Option<u64>,
    pub completes_at: Option<u64>,
}

/// Renderable building lifecycle; level zero is under construction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BuildingState {
    Ready,
    Upgrading,
    UnderConstruction,
}

impl ClientMsg {
    pub fn from_json(text: &str) -> serde_json::Result<Self> {
        serde_json::from_str(text)
    }
}

impl ServerMsg {
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("ServerMsg is always serializable")
    }

    pub fn error(code: ErrorCode, message: impl Into<String>) -> Self {
        Self::Error {
            code,
            message: message.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn client_messages_use_snake_case_type_tags() {
        let msg =
            ClientMsg::from_json(r#"{"type":"login","name":"alice","password":"password123"}"#)
                .unwrap();
        assert_eq!(
            msg,
            ClientMsg::Login {
                name: "alice".into(),
                password: "password123".into()
            }
        );
        assert_eq!(
            ClientMsg::from_json(r#"{"type":"get_city"}"#).unwrap(),
            ClientMsg::GetCity
        );
    }

    #[test]
    fn server_error_serializes_flat() {
        let json = ServerMsg::error(ErrorCode::NotLoggedIn, "log in first").to_json();
        assert_eq!(
            json,
            r#"{"type":"error","code":"not_logged_in","message":"log in first"}"#
        );
    }

    #[test]
    fn unknown_type_is_rejected() {
        assert!(ClientMsg::from_json(r#"{"type":"nuke"}"#).is_err());
    }
    #[test]
    fn construction_shapes_and_coordinate_bounds() {
        assert_eq!(
            ClientMsg::from_json(r#"{"type":"build_building","kind":"farm","x":0,"y":38}"#)
                .unwrap(),
            ClientMsg::BuildBuilding {
                kind: "farm".into(),
                x: 0,
                y: 38
            }
        );
        for value in ["-1", "4294967296", "1.5"] {
            assert!(
                ClientMsg::from_json(&format!(
                    r#"{{"type":"build_building","kind":"farm","x":{value},"y":0}}"#
                ))
                .is_err()
            );
        }
        assert!(ClientMsg::from_json(r#"{"type":"build_building","kind":"farm","x":0}"#).is_err());
    }
}
