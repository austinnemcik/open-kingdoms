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
    let mut updates = kingdom.subscribe();
    loop {
        let frame = tokio::select! {
            frame = rx.next() => match frame { Some(Ok(frame)) => frame, _ => break },
            update = updates.recv() => {
                let reply = match (&phase, update) {
                    (Phase::Playing(player), Ok((owner, city))) if *player == owner => Some(ServerMsg::CityUpdate { city }),
                    (Phase::Playing(player), Err(tokio::sync::broadcast::error::RecvError::Lagged(_))) => {
                        let kingdom = kingdom.clone(); let player = *player;
                        tokio::task::spawn_blocking(move || kingdom.city_view(player)).await.ok().and_then(Result::ok).map(|city| ServerMsg::CityUpdate { city })
                    }
                    _ => None,
                };
                if let Some(reply) = reply && tx.send(Message::Text(reply.to_json().into())).await.is_err() { break; }
                continue;
            }
        };
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
        (Phase::Playing(player), ClientMsg::BuildBuilding { kind, x, y }) => kingdom
            .change_city(*player, |city, now, data| {
                city.build_building(&kind, x, y, now, data).map(|_| ())
            })
            .err()
            .map(|(code, message)| ServerMsg::error(code, message))
            .into_iter()
            .collect(),
        (Phase::Playing(player), ClientMsg::UpgradeBuilding { building_id }) => kingdom
            .change_city(*player, |city, now, data| {
                city.upgrade_building(building_id, now, data)
            })
            .err()
            .map(|(code, message)| ServerMsg::error(code, message))
            .into_iter()
            .collect(),
        (Phase::Playing(player), ClientMsg::CancelUpgrade { building_id }) => kingdom
            .change_city(*player, |city, now, data| {
                city.cancel_upgrade(building_id, now, data)
            })
            .err()
            .map(|(code, message)| ServerMsg::error(code, message))
            .into_iter()
            .collect(),
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
