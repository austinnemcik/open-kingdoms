use std::sync::Arc;

use axum::body::{Body, to_bytes};
use axum::http::{Request, StatusCode};
use data::GameData;
use futures_util::{SinkExt, StreamExt};
use kingdom_server::{Kingdom, router, router_with_web};
use tower::ServiceExt;

#[tokio::test]
async fn serves_web_assets_with_mime_types_and_isolation_headers() {
    let dir = tempfile::tempdir().unwrap();
    let public = dir.path().join("public");
    std::fs::create_dir(&public).unwrap();
    std::fs::write(dir.path().join("secret.txt"), "private").unwrap();
    let files: [(&str, &[u8], &str); 4] = [
        ("index.html", b"<html>Open Kingdoms</html>", "text/html"),
        ("index.wasm", b"\0asm", "application/wasm"),
        ("index.pck", b"GDPC", "application/octet-stream"),
        ("index.js", b"// loader", "text/javascript"),
    ];
    for (name, body, _) in files {
        std::fs::write(public.join(name), body).unwrap();
    }
    // Static files cannot replace API routes.
    std::fs::write(public.join("health"), "wrong health").unwrap();
    std::fs::write(public.join("ws"), "wrong ws").unwrap();
    let kingdom =
        Arc::new(Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap()).unwrap());
    let app = router_with_web(kingdom, &public);
    for (name, expected, mime) in files {
        for path in if name == "index.html" {
            vec!["/".to_owned(), format!("/{name}")]
        } else {
            vec![format!("/{name}")]
        } {
            let response = app
                .clone()
                .oneshot(Request::builder().uri(path).body(Body::empty()).unwrap())
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK);
            assert_eq!(response.headers()["content-type"], mime);
            assert_eq!(
                response.headers()["cross-origin-opener-policy"],
                "same-origin"
            );
            assert_eq!(
                response.headers()["cross-origin-embedder-policy"],
                "require-corp"
            );
            assert_eq!(
                to_bytes(response.into_body(), 1024).await.unwrap(),
                expected
            );
        }
    }
    for path in ["/missing.wasm", "/%2e%2e/secret.txt", "/..%2fsecret.txt"] {
        let response = app
            .clone()
            .oneshot(Request::builder().uri(path).body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::NOT_FOUND, "{path}");
        assert_eq!(
            response.headers()["cross-origin-embedder-policy"],
            "require-corp"
        );
    }
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("HEAD")
                .uri("/index.wasm")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(response.headers()["content-type"], "application/wasm");
    assert!(
        to_bytes(response.into_body(), 1024)
            .await
            .unwrap()
            .is_empty()
    );
    let health = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(health.status(), StatusCode::OK);
    assert_eq!(to_bytes(health.into_body(), 1024).await.unwrap(), "ok");
    let ws = app
        .oneshot(Request::builder().uri("/ws").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(
        ws.status(),
        StatusCode::BAD_REQUEST,
        "WebSocket upgrade is still required"
    );
}

#[tokio::test]
async fn web_hosting_is_opt_in() {
    let kingdom =
        Arc::new(Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap()).unwrap());
    let response = router(kingdom)
        .oneshot(Request::builder().uri("/").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn web_server_preserves_websocket_peer_admission_and_handshake() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("index.html"), "web client").unwrap();
    let kingdom =
        Arc::new(Kingdom::new(GameData::load(GameData::repo_data_dir()).unwrap()).unwrap());
    let (bound_tx, bound_rx) = tokio::sync::oneshot::channel();
    let server = tokio::spawn(async move {
        kingdom_server::serve_kingdom_with_web(
            "127.0.0.1:0".parse().unwrap(),
            kingdom,
            Some(dir.path()),
            |addr| {
                let _ = bound_tx.send(addr);
            },
        )
        .await
        .unwrap();
    });
    tokio::time::timeout(std::time::Duration::from_secs(5), async {
        let addr = bound_rx.await.unwrap();
        let (mut ws, response) = tokio_tungstenite::connect_async(format!("ws://{addr}/ws"))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::SWITCHING_PROTOCOLS);
        assert_eq!(
            response.headers()["cross-origin-opener-policy"],
            "same-origin"
        );
        ws.send(tokio_tungstenite::tungstenite::Message::Text(
            serde_json::json!({"type": "hello", "protocol": protocol::PROTOCOL_VERSION})
                .to_string()
                .into(),
        ))
        .await
        .unwrap();
        let reply = ws.next().await.unwrap().unwrap().into_text().unwrap();
        assert_eq!(
            serde_json::from_str::<serde_json::Value>(&reply).unwrap()["type"],
            "welcome"
        );
        ws.close(None).await.unwrap();
    })
    .await
    .expect("web-enabled server must complete the WebSocket handshake");
    server.abort();
    let _ = server.await;
}
