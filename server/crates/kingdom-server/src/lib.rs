//! Authoritative server for a single kingdom.
//!
//! The client is untrusted: it sends requests, and this server validates and
//! applies every one of them through the pure rules in `game-core`.

pub mod clock;
mod session;
mod state;
pub mod store;

use std::net::SocketAddr;
use std::sync::Arc;

use axum::Router;
use axum::extract::State;
use axum::extract::ws::WebSocketUpgrade;
use axum::response::Response;
use axum::routing::get;
use data::GameData;
use tokio::net::TcpListener;

pub use state::Kingdom;

/// Build the HTTP router: `/ws` for the game protocol, `/health` for probes.
pub fn router(kingdom: Arc<Kingdom>) -> Router {
    Router::new()
        .route("/ws", get(ws_handler))
        .route("/health", get(|| async { "ok" }))
        .with_state(kingdom)
}

async fn ws_handler(ws: WebSocketUpgrade, State(kingdom): State<Arc<Kingdom>>) -> Response {
    ws.max_message_size(4096)
        .max_frame_size(4096)
        .on_upgrade(move |socket| session::run(socket, kingdom))
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
    let listener = TcpListener::bind(addr).await?;
    on_bound(listener.local_addr()?);
    // Both futures belong to this serve call: cancelling it also drops the ticker.
    tokio::select! {
        result = axum::serve(listener, router(kingdom.clone())) => { result?; }
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
