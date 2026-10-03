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

    let logged_in = c
        .request(r#"{"type":"login","name":"alice","password":"password123"}"#)
        .await;
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
    let again = c2
        .request(r#"{"type":"login","name":"alice","password":"password123"}"#)
        .await;
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

#[tokio::test]
async fn wrong_password_resume_and_failure_limit() {
    let addr = start_server().await;
    let mut c = Client::connect(addr).await;
    c.hello().await;
    let ServerMsg::LoggedIn {
        player_id, token, ..
    } = c
        .request(r#"{"type":"login","name":"alice","password":"password123"}"#)
        .await
    else {
        panic!()
    };
    let mut resumed = Client::connect(addr).await;
    resumed.hello().await;
    assert!(
        matches!(resumed.request(&serde_json::json!({"type":"resume","token":token}).to_string()).await, ServerMsg::LoggedIn { player_id: p, .. } if p == player_id)
    );
    let mut bad = Client::connect(addr).await;
    bad.hello().await;
    for _ in 0..5 {
        assert_eq!(
            bad.request(r#"{"type":"login","name":"alice","password":"incorrect"}"#)
                .await,
            ServerMsg::error(ErrorCode::InvalidCredentials, "invalid credentials")
        );
    }
    assert!(matches!(bad.ws.next().await, Some(Ok(Message::Close(_)))));
    let mut forged = Client::connect(addr).await;
    forged.hello().await;
    assert_eq!(
        forged
            .request(r#"{"type":"resume","token":"forged"}"#)
            .await,
        ServerMsg::error(ErrorCode::InvalidCredentials, "invalid credentials")
    );
}

struct ServerProcess(std::process::Child);
impl Drop for ServerProcess {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}
async fn start_persistent(path: &std::path::Path) -> (ServerProcess, SocketAddr) {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let addr = listener.local_addr().unwrap();
    drop(listener);
    let child = std::process::Command::new(env!("CARGO_BIN_EXE_kingdom-server"))
        .env("ROK_ADDR", addr.to_string())
        .env("ROK_DB", path)
        .env("ROK_DATA_DIR", GameData::repo_data_dir())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .unwrap();
    let process = ServerProcess(child);
    for _ in 0..100 {
        if tokio::net::TcpStream::connect(addr).await.is_ok() {
            return (process, addr);
        }
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    }
    panic!("server did not start");
}

#[tokio::test]
async fn password_session_and_city_survive_process_restart() {
    let dir = tempfile::tempdir().unwrap();
    let db = dir.path().join("kingdom.db");
    let (process, addr) = start_persistent(&db).await;
    let mut c = Client::connect(addr).await;
    c.hello().await;
    let ServerMsg::LoggedIn {
        player_id, token, ..
    } = c
        .request(r#"{"type":"login","name":"persisted","password":"password123"}"#)
        .await
    else {
        panic!()
    };
    let city = c.request(r#"{"type":"get_city"}"#).await;
    drop(c);
    drop(process);
    let (_process, addr) = start_persistent(&db).await;
    let mut c = Client::connect(addr).await;
    c.hello().await;
    assert_eq!(
        c.request(r#"{"type":"login","name":"persisted","password":"wrongpass"}"#)
            .await,
        ServerMsg::error(ErrorCode::InvalidCredentials, "invalid credentials")
    );
    assert!(
        matches!(c.request(r#"{"type":"login","name":"persisted","password":"password123"}"#).await, ServerMsg::LoggedIn { player_id: p, .. } if p == player_id)
    );
    assert_same_persisted_city(&city, &c.request(r#"{"type":"get_city"}"#).await);
    let mut resumed = Client::connect(addr).await;
    resumed.hello().await;
    assert!(
        matches!(resumed.request(&serde_json::json!({"type":"resume","token":token}).to_string()).await, ServerMsg::LoggedIn { player_id: p, .. } if p == player_id)
    );
    assert_same_persisted_city(&city, &resumed.request(r#"{"type":"get_city"}"#).await);
}

#[tokio::test]
async fn injected_clock_drives_the_one_second_tick() {
    use kingdom_server::{Kingdom, clock::ManualClock, store::SqliteStore};
    use std::sync::Arc;
    let clock = Arc::new(ManualClock::new(100));
    let kingdom = Arc::new(Kingdom::with_clock(
        GameData::load(GameData::repo_data_dir()).unwrap(),
        Box::new(SqliteStore::open(":memory:").unwrap()),
        clock.clone(),
    ));
    let (tx, rx) = oneshot::channel();
    let task = tokio::spawn(kingdom_server::serve_kingdom(
        "127.0.0.1:0".parse().unwrap(),
        kingdom.clone(),
        move |addr| {
            let _ = tx.send(addr);
        },
    ));
    let mut client = Client::connect(rx.await.unwrap()).await;
    assert!(matches!(client.hello().await, ServerMsg::Welcome { .. }));
    for expected in [100, 250] {
        clock.set(expected);
        tokio::time::timeout(std::time::Duration::from_secs(3), async {
            while kingdom.last_tick() != expected {
                tokio::time::sleep(std::time::Duration::from_millis(10)).await;
            }
        })
        .await
        .unwrap();
    }
    task.abort();
    let _ = task.await;
}

fn assert_same_persisted_city(before: &ServerMsg, after: &ServerMsg) {
    let (ServerMsg::CityState { city: before }, ServerMsg::CityState { city: after }) =
        (before, after)
    else {
        panic!("expected city snapshots")
    };
    assert_eq!(before.buildings, after.buildings);
    assert_eq!(before.size, after.size);
    assert_eq!(before.rates_per_hour, after.rates_per_hour);
    assert!(after.as_of >= before.as_of);
    assert!(after.resources.food >= before.resources.food);
}
