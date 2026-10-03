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

/// Drive one bounded connection until close, overload, or its deadline.
pub async fn run(
    socket: WebSocket,
    kingdom: Arc<Kingdom>,
    ip: std::net::IpAddr,
    _permit: crate::security::ConnectionPermit,
) {
    use tokio::time::{Duration, Instant, timeout_at};
    let limits = &kingdom.data.limits;
    let (mut tx, mut rx) = socket.split();
    let mut phase = Phase::AwaitingHello;
    let started = Instant::now();
    let handshake = started + Duration::from_millis(limits.handshake_timeout_ms);
    let mut idle = started + Duration::from_millis(limits.idle_timeout_ms);
    let mut bucket = game_core::rate_limit::TokenBucket::new(limits.message_burst, 0);
    let mut failures = 0;
    let mut updates = kingdom.subscribe();
    loop {
        let deadline = if matches!(phase, Phase::Playing(_)) {
            idle
        } else {
            handshake.min(idle)
        };
        let frame = tokio::select! {
            biased;
            () = tokio::time::sleep_until(deadline) => break,
            frame = rx.next() => match frame { Some(Ok(frame)) => frame, _ => break },
            update = updates.recv() => {
                let reply = match (&phase, update) {
                    (Phase::Playing(player), Ok((owner, city))) if *player == owner => Some(ServerMsg::CityUpdate { city }),
                    (Phase::Playing(player), Err(tokio::sync::broadcast::error::RecvError::Lagged(_))) => {
                        let kingdom = kingdom.clone(); let player = *player;
                        match timeout_at(deadline, tokio::task::spawn_blocking(move || kingdom.city_view(player))).await {
                            Ok(Ok(Ok(city))) => Some(ServerMsg::CityUpdate { city }),
                            _ => break,
                        }
                    }
                    _ => None,
                };
                if let Some(reply) = reply && !matches!(timeout_at(deadline, tx.send(Message::Text(reply.to_json().into()))).await, Ok(Ok(()))) { break; }
                continue;
            }
        };
        if !bucket.allow(
            started.elapsed().as_millis().min(u128::from(u64::MAX)) as u64,
            limits.messages_per_second,
            limits.message_burst,
        ) {
            break;
        }
        idle = Instant::now() + Duration::from_millis(limits.idle_timeout_ms);
        let text = match frame {
            Message::Text(t) => t,
            Message::Close(_) => break,
            _ => continue,
        };
        let replies = match ClientMsg::from_json(&text) {
            // Ping needs neither a database lock nor a blocking worker.
            Ok(ClientMsg::Ping { nonce }) => vec![ServerMsg::Pong { nonce }],
            Ok(msg) => {
                let kingdom = kingdom.clone();
                let mut worker_phase = phase.clone();
                match timeout_at(
                    deadline,
                    tokio::task::spawn_blocking(move || {
                        let replies = handle(&kingdom, &mut worker_phase, msg, ip);
                        (worker_phase, replies)
                    }),
                )
                .await
                {
                    Ok(Ok((next_phase, replies))) => {
                        phase = next_phase;
                        replies
                    }
                    _ => break,
                }
            }
            Err(e) => vec![ServerMsg::error(ErrorCode::BadMessage, e.to_string())],
        };
        if !matches!(phase, Phase::Playing(_)) && replies.iter().any(|r| matches!(r, ServerMsg::Error { code, .. } if !matches!(code, ErrorCode::Internal | ErrorCode::RateLimited))) { failures += 1; }
        for reply in replies {
            if !matches!(
                timeout_at(deadline, tx.send(Message::Text(reply.to_json().into()))).await,
                Ok(Ok(()))
            ) {
                return;
            }
        }
        if failures >= limits.max_auth_failures {
            break;
        }
    }
    let _ = tokio::time::timeout(
        Duration::from_millis(limits.handshake_timeout_ms),
        tx.send(Message::Close(None)),
    )
    .await;
}

fn handle(
    kingdom: &Kingdom,
    phase: &mut Phase,
    msg: ClientMsg,
    ip: std::net::IpAddr,
) -> Vec<ServerMsg> {
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
            authenticated(phase, kingdom.login_from(ip, &name, &password))
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
        Err(code) => vec![ServerMsg::error(
            code,
            match code {
                ErrorCode::InvalidCredentials => "invalid credentials",
                ErrorCode::RateLimited => "authentication rate limited",
                _ => "authentication unavailable",
            },
        )],
        _ => vec![ServerMsg::error(
            ErrorCode::Internal,
            "authentication unavailable",
        )],
    }
}
