use std::sync::Arc;

use axum::extract::ws::{Message, WebSocket};
use futures_util::{SinkExt, StreamExt};
use game_core::PlayerId;
use protocol::{ClientMsg, ErrorCode, PROTOCOL_VERSION, ServerMsg};

use crate::state::{Kingdom, valid_name};

/// Per-connection handshake progress.
enum Phase {
    AwaitingHello,
    AwaitingLogin,
    Playing(PlayerId),
}

/// Drive one client connection until it closes.
pub async fn run(socket: WebSocket, kingdom: Arc<Kingdom>) {
    let (mut tx, mut rx) = socket.split();
    let mut phase = Phase::AwaitingHello;

    while let Some(Ok(frame)) = rx.next().await {
        let text = match frame {
            Message::Text(t) => t,
            Message::Close(_) => break,
            _ => continue,
        };
        let replies = match ClientMsg::from_json(&text) {
            Ok(msg) => handle(&kingdom, &mut phase, msg),
            Err(e) => vec![ServerMsg::error(ErrorCode::BadMessage, e.to_string())],
        };
        for reply in replies {
            if tx
                .send(Message::Text(reply.to_json().into()))
                .await
                .is_err()
            {
                return;
            }
        }
    }
}

fn handle(kingdom: &Kingdom, phase: &mut Phase, msg: ClientMsg) -> Vec<ServerMsg> {
    match (&*phase, msg) {
        (_, ClientMsg::Ping { nonce }) => vec![ServerMsg::Pong { nonce }],

        (Phase::AwaitingHello, ClientMsg::Hello { protocol }) => {
            if protocol != PROTOCOL_VERSION {
                return vec![ServerMsg::error(
                    ErrorCode::ProtocolMismatch,
                    format!("server speaks protocol {PROTOCOL_VERSION}, client sent {protocol}"),
                )];
            }
            *phase = Phase::AwaitingLogin;
            vec![ServerMsg::Welcome {
                protocol: PROTOCOL_VERSION,
                server_version: env!("CARGO_PKG_VERSION").into(),
            }]
        }
        (Phase::AwaitingHello, _) => {
            vec![ServerMsg::error(ErrorCode::BadMessage, "send hello first")]
        }

        (Phase::AwaitingLogin, ClientMsg::Login { name }) => {
            if !valid_name(&name) {
                return vec![ServerMsg::error(
                    ErrorCode::InvalidName,
                    "names are 3-16 letters, digits or underscores",
                )];
            }
            let player_id = kingdom.login_or_register(&name);
            *phase = Phase::Playing(player_id);
            vec![ServerMsg::LoggedIn { player_id, name }]
        }
        (Phase::AwaitingLogin, _) => {
            vec![ServerMsg::error(ErrorCode::NotLoggedIn, "log in first")]
        }

        (Phase::Playing(_), ClientMsg::Hello { .. } | ClientMsg::Login { .. }) => {
            vec![ServerMsg::error(
                ErrorCode::AlreadyLoggedIn,
                "already logged in",
            )]
        }
        (Phase::Playing(player), ClientMsg::GetCity) => match kingdom.city_view(*player) {
            Some(city) => vec![ServerMsg::CityState { city }],
            None => vec![ServerMsg::error(
                ErrorCode::NotLoggedIn,
                "no city for player",
            )],
        },
    }
}
