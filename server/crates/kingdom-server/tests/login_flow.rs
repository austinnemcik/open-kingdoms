//! End-to-end: real server on a random port, real WebSocket client.

use std::net::SocketAddr;

use data::GameData;
use futures_util::{SinkExt, StreamExt};
use protocol::{ErrorCode, PROTOCOL_VERSION, ServerMsg};
use tokio::net::TcpStream;
use tokio::sync::oneshot;
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream};

async fn start_server() -> SocketAddr {
    let data = GameData::load(GameData::repo_data_dir()).unwrap();
    let (tx, rx) = oneshot::channel();
    tokio::spawn(kingdom_server::serve(
        "127.0.0.1:0".parse().unwrap(),
        data,
        move |addr| tx.send(addr).unwrap(),
    ));
    rx.await.unwrap()
}

struct Client {
    ws: WebSocketStream<MaybeTlsStream<TcpStream>>,
}

impl Client {
    async fn connect(addr: SocketAddr) -> Self {
        let (ws, _) = tokio_tungstenite::connect_async(format!("ws://{addr}/ws"))
            .await
            .unwrap();
        Self { ws }
    }

    async fn request(&mut self, json: &str) -> ServerMsg {
        self.ws.send(Message::Text(json.into())).await.unwrap();
        loop {
            if let Message::Text(t) = self.ws.next().await.unwrap().unwrap() {
                return serde_json::from_str(&t).unwrap();
            }
        }
    }

    async fn hello(&mut self) -> ServerMsg {
        self.request(&format!(
            r#"{{"type":"hello","protocol":{PROTOCOL_VERSION}}}"#
        ))
        .await
    }
}

#[tokio::test]
async fn hello_login_and_fetch_city() {
    let addr = start_server().await;
    let mut c = Client::connect(addr).await;

    let welcome = c.hello().await;
    assert!(matches!(welcome, ServerMsg::Welcome { .. }), "{welcome:?}");

    let logged_in = c.request(r#"{"type":"login","name":"alice"}"#).await;
    let ServerMsg::LoggedIn { player_id, .. } = logged_in else {
        panic!("expected logged_in, got {logged_in:?}");
    };

    let ServerMsg::CityState { city } = c.request(r#"{"type":"get_city"}"#).await else {
        panic!("expected city_state");
    };
    assert!(city.buildings.iter().any(|b| b.kind == "city_hall"));

    // Reconnecting with the same name returns the same player.
    let mut c2 = Client::connect(addr).await;
    c2.hello().await;
    let again = c2.request(r#"{"type":"login","name":"alice"}"#).await;
    assert!(matches!(again, ServerMsg::LoggedIn { player_id: p, .. } if p == player_id));
}

#[tokio::test]
async fn requests_out_of_order_are_rejected() {
    let addr = start_server().await;
    let mut c = Client::connect(addr).await;
    let reply = c.request(r#"{"type":"get_city"}"#).await;
    assert!(matches!(
        reply,
        ServerMsg::Error {
            code: ErrorCode::BadMessage,
            ..
        }
    ));

    c.hello().await;
    let reply = c.request(r#"{"type":"get_city"}"#).await;
    assert!(matches!(
        reply,
        ServerMsg::Error {
            code: ErrorCode::NotLoggedIn,
            ..
        }
    ));
}

#[tokio::test]
async fn wrong_protocol_version_is_rejected() {
    let addr = start_server().await;
    let mut c = Client::connect(addr).await;
    let reply = c.request(r#"{"type":"hello","protocol":9999}"#).await;
    assert!(matches!(
        reply,
        ServerMsg::Error {
            code: ErrorCode::ProtocolMismatch,
            ..
        }
    ));
}
