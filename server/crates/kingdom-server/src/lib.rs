//! Authoritative server for a single kingdom.
//!
//! The client is untrusted: it sends requests, and this server validates and
//! applies every one of them through the pure rules in `game-core`.

pub mod clock;
mod security;
mod session;
mod state;
pub mod store;

use std::net::SocketAddr;
use std::path::Path;
use std::sync::Arc;

use axum::Router;
use axum::extract::ws::WebSocketUpgrade;
use axum::extract::{ConnectInfo, State};
use axum::http::{HeaderName, HeaderValue};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use data::GameData;
use tokio::net::TcpListener;
use tower_http::services::ServeDir;
use tower_http::set_header::SetResponseHeaderLayer;

pub use state::Kingdom;

/// Build the HTTP router: `/ws` for the game protocol, `/health` for probes.
pub fn router(kingdom: Arc<Kingdom>) -> Router {
    Router::new()
        .route("/ws", get(ws_handler))
        .route("/health", get(|| async { "ok" }))
        .with_state(kingdom)
}

/// Add the exported web client without shadowing `/ws` or `/health`.
/// The directory must contain only public build output. Unknown paths stay 404.
pub fn router_with_web(kingdom: Arc<Kingdom>, web_dir: &Path) -> Router {
    router(kingdom)
        .fallback_service(ServeDir::new(web_dir))
        .layer(SetResponseHeaderLayer::overriding(
            HeaderName::from_static("cross-origin-opener-policy"),
            HeaderValue::from_static("same-origin"),
        ))
        .layer(SetResponseHeaderLayer::overriding(
            HeaderName::from_static("cross-origin-embedder-policy"),
            HeaderValue::from_static("require-corp"),
        ))
}

async fn ws_handler(
    ws: WebSocketUpgrade,
    State(kingdom): State<Arc<Kingdom>>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
) -> Response {
    let Some(permit) = kingdom.security.connect(addr.ip(), &kingdom.data.limits) else {
        return axum::http::StatusCode::TOO_MANY_REQUESTS.into_response();
    };
    ws.max_message_size(4096)
        .max_frame_size(4096)
        .on_upgrade(move |socket| session::run(socket, kingdom, addr.ip(), permit))
}

/// Bind `addr` and serve until the process is stopped. Reports the bound
/// address through `on_bound` (useful when `addr` uses port 0).
pub async fn serve(
    addr: SocketAddr,
    data: GameData,
    on_bound: impl FnOnce(SocketAddr),
) -> anyhow::Result<()> {
    let kingdom = Arc::new(tokio::task::spawn_blocking(move || Kingdom::new(data)).await??);
    serve_kingdom(addr, kingdom, on_bound).await
}

/// Serve an injected kingdom; persistent deployments create their store off-runtime.
pub async fn serve_kingdom(
    addr: SocketAddr,
    kingdom: Arc<Kingdom>,
    on_bound: impl FnOnce(SocketAddr),
) -> anyhow::Result<()> {
    serve_kingdom_with_web(addr, kingdom, None, on_bound).await
}

/// Serve an injected kingdom with an optional directory of public web assets.
pub async fn serve_kingdom_with_web(
    addr: SocketAddr,
    kingdom: Arc<Kingdom>,
    web_dir: Option<&Path>,
    on_bound: impl FnOnce(SocketAddr),
) -> anyhow::Result<()> {
    let app = match web_dir {
        Some(dir) => router_with_web(kingdom.clone(), dir),
        None => router(kingdom.clone()),
    };
    let listener = TcpListener::bind(addr).await?;
    on_bound(listener.local_addr()?);
    // Both futures belong to this serve call: cancelling it also drops the ticker.
    tokio::select! {
        result = axum::serve(listener, app.into_make_service_with_connect_info::<SocketAddr>()) => { result?; }
        () = tick_loop(kingdom) => {}
    }
    Ok(())
}

async fn tick_loop(kingdom: Arc<Kingdom>) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(1));
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    loop {
        interval.tick().await;
        let kingdom = kingdom.clone();
        match tokio::task::spawn_blocking(move || kingdom.tick()).await {
            Ok(Ok(())) => {}
            error => tracing::error!(?error, "server tick failed"),
        }
    }
}
