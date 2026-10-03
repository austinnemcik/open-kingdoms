use std::net::SocketAddr;
use std::path::PathBuf;

use data::GameData;
use tracing_subscriber::EnvFilter;

/// Environment:
/// - `ROK_ADDR`: listen address (default `127.0.0.1:7777`)
/// - `ROK_DATA_DIR`: path to the data files (default: the repo's `data/`)
/// - `ROK_DB`: SQLite file (default `kingdom.db`)
/// - `ROK_WEB_DIR`: optional directory containing the exported web client
/// - `RUST_LOG`: log filter (default `info`)
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let addr: SocketAddr = std::env::var("ROK_ADDR")
        .unwrap_or_else(|_| "127.0.0.1:7777".into())
        .parse()?;
    let data_dir = std::env::var("ROK_DATA_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| GameData::repo_data_dir());
    let data = GameData::load(&data_dir)?;

    let db = std::env::var("ROK_DB").unwrap_or_else(|_| "kingdom.db".into());
    let store =
        tokio::task::spawn_blocking(move || kingdom_server::store::SqliteStore::open(db)).await??;
    let kingdom = std::sync::Arc::new(kingdom_server::Kingdom::with_store(data, Box::new(store)));
    let web_dir = std::env::var_os("ROK_WEB_DIR").map(PathBuf::from);
    if let Some(dir) = &web_dir {
        anyhow::ensure!(
            dir.join("index.html").is_file(),
            "ROK_WEB_DIR must contain index.html: {}",
            dir.display()
        );
    }
    kingdom_server::serve_kingdom_with_web(addr, kingdom, web_dir.as_deref(), |bound| {
        tracing::info!("kingdom server listening on http://{bound} (WebSocket: /ws)");
    })
    .await
}
