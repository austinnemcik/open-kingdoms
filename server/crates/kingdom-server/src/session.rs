use std::sync::Arc;

use axum::extract::ws::{Message, WebSocket};
use futures_util::{SinkExt, StreamExt};
use game_core::PlayerId;
use protocol::{ClientMsg, ErrorCode, PROTOCOL_VERSION, ServerMsg};

use crate::state::Kingdom;

/// Per-connection handshake progress.
#[derive(Clone)]
enum Phase {
    AwaitingHello,
    AwaitingLogin,
    Playing(PlayerId),
}

/// Drive one client connection until it closes.
pub async fn run(socket: WebSocket, kingdom: Arc<Kingdom>) {
    let (mut tx, mut rx) = socket.split();
    let mut phase = Phase::AwaitingHello;

    let mut failures = 0;
    while let Some(Ok(frame)) = rx.next().await {
        let text = match frame {
            Message::Text(t) => t,
            Message::Close(_) => break,
            _ => continue,
        };
        let replies = match ClientMsg::from_json(&text) {
            Ok(msg) => {
                let kingdom = kingdom.clone();
                let mut worker_phase = phase.clone();
                match tokio::task::spawn_blocking(move || {
                    let replies = handle(&kingdom, &mut worker_phase, msg);
                    (worker_phase, replies)
                })
                .await
                {
                    Ok((next_phase, replies)) => {
                        phase = next_phase;
                        replies
                    }
                    Err(_) => return,
                }
            }
            Err(e) => vec![ServerMsg::error(ErrorCode::BadMessage, e.to_string())],
        };
        if !matches!(phase, Phase::Playing(_))
            && replies.iter().any(|r| matches!(r, ServerMsg::Error { .. }))
        {
            failures += 1;
        }
        for reply in replies {
            if tx
                .send(Message::Text(reply.to_json().into()))
                .await
                .is_err()
            {
                return;
            }
        }
        if failures >= 5 {
            let _ = tx.send(Message::Close(None)).await;
            break;
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

        (Phase::AwaitingLogin, ClientMsg::Login { name, password }) => {
            authenticated(phase, kingdom.login(&name, &password))
        }
        (Phase::AwaitingLogin, ClientMsg::Resume { token }) => {
            authenticated(phase, kingdom.resume(&token))
        }
        (Phase::AwaitingLogin, _) => {
            vec![ServerMsg::error(ErrorCode::NotLoggedIn, "log in first")]
        }

        (
            Phase::Playing(_),
            ClientMsg::Hello { .. } | ClientMsg::Login { .. } | ClientMsg::Resume { .. },
        ) => {
            vec![ServerMsg::error(
                ErrorCode::AlreadyLoggedIn,
                "already logged in",
            )]
        }
        (Phase::Playing(player), ClientMsg::GetCity) => match kingdom.city_view(*player) {
            Ok(city) => vec![ServerMsg::CityState { city }],
            Err(code) => vec![ServerMsg::error(code, "city unavailable")],
        },
    }
}

fn authenticated(phase: &mut Phase, result: Result<ServerMsg, ErrorCode>) -> Vec<ServerMsg> {
    match result {
        Ok(reply @ ServerMsg::LoggedIn { player_id, .. }) => {
            *phase = Phase::Playing(player_id);
            vec![reply]
        }
        _ => vec![ServerMsg::error(
            ErrorCode::InvalidCredentials,
            "invalid credentials",
        )],
    }
}
