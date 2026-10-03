//! Authoritative server for a single kingdom.
//!
//! The client is untrusted: it sends requests, and this server validates and
//! applies every one of them through the pure rules in `game-core`.

mod session;
mod state;

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
    let listener = TcpListener::bind(addr).await?;
    on_bound(listener.local_addr()?);
    let kingdom = Arc::new(Kingdom::new(data));
    axum::serve(listener, router(kingdom)).await?;
    Ok(())
}
