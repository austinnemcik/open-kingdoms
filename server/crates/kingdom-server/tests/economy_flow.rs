//! Economy integration through real WebSockets with an injected game clock.
use data::GameData;
use futures_util::{SinkExt, StreamExt};
use kingdom_server::{Kingdom, clock::ManualClock, store::SqliteStore};
use protocol::{CityView, PROTOCOL_VERSION, ServerMsg};
use std::{sync::Arc, time::Duration};
use tokio::{net::TcpStream, sync::oneshot, task::JoinHandle};
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream, tungstenite::Message};

struct Client(WebSocketStream<MaybeTlsStream<TcpStream>>);
impl Client {
    async fn request(&mut self, msg: serde_json::Value) -> ServerMsg {
        self.0
            .send(Message::Text(msg.to_string().into()))
            .await
            .unwrap();
        loop {
            let reply = self.receive().await;
            if msg["type"] == "get_city" && matches!(reply, ServerMsg::CityUpdate { .. }) {
                continue;
            }
            return reply;
        }
    }
    async fn receive(&mut self) -> ServerMsg {
        tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                if let Message::Text(text) = self.0.next().await.unwrap().unwrap() {
                    return serde_json::from_str(&text).unwrap();
                }
            }
        })
        .await
        .expect("server response timed out")
    }
    async fn city(&mut self) -> CityView {
        let ServerMsg::CityState { city } =
            self.request(serde_json::json!({"type":"get_city"})).await
        else {
            panic!("expected city")
        };
        city
    }
}
struct TestServer {
    task: JoinHandle<()>,
    clock: Arc<ManualClock>,
    addr: std::net::SocketAddr,
}
impl Drop for TestServer {
    fn drop(&mut self) {
        self.task.abort();
    }
}
impl TestServer {
    async fn start() -> Self {
        Self::open(":memory:", 100).await
    }
    async fn open(path: impl AsRef<std::path::Path>, now: u64) -> Self {
        let data = GameData::load(GameData::repo_data_dir()).unwrap();
        let clock = Arc::new(ManualClock::new(now));
        let kingdom = Arc::new(Kingdom::with_clock(
            data,
            Box::new(SqliteStore::open(path).unwrap()),
            clock.clone(),
        ));
        let (tx, rx) = oneshot::channel();
        let task = tokio::spawn(async move {
            kingdom_server::serve_kingdom("127.0.0.1:0".parse().unwrap(), kingdom, move |addr| {
                let _ = tx.send(addr);
            })
            .await
            .unwrap();
        });
        Self {
            task,
            clock,
            addr: rx.await.unwrap(),
        }
    }
    async fn login(&self, name: &str) -> Client {
        let mut client = Client(
            tokio_tungstenite::connect_async(format!("ws://{}/ws", self.addr))
                .await
                .unwrap()
                .0,
        );
        assert!(matches!(
            client
                .request(serde_json::json!({"type":"hello","protocol":PROTOCOL_VERSION}))
                .await,
            ServerMsg::Welcome { .. }
        ));
        assert!(matches!(
            client
                .request(serde_json::json!({"type":"login","name":name,"password":"password123"}))
                .await,
            ServerMsg::LoggedIn { .. }
        ));
        client
    }
}
#[tokio::test]
async fn collection_uses_server_time_and_survives_reconnect() {
    let server = TestServer::start().await;
    let mut c = server.login("alice").await;
    let start = c.city().await;
    assert_eq!(start.as_of, 100);
    assert_eq!(start.rates_per_hour.food, 600);
    server.clock.set(3700);
    let after = c.city().await;
    assert_eq!(after.resources.food, start.resources.food + 600);
    assert_eq!(after.as_of, 3700);
    let mut reconnect = server.login("alice").await;
    assert_eq!(reconnect.city().await, after);
    server.clock.set(200);
    assert_eq!(c.city().await, after);
    server.clock.set(u64::MAX);
    let capped = c.city().await;
    assert_eq!(capped.resources.food, capped.capacity.food);
    assert!(matches!(
        c.request(serde_json::json!({"type":"set_resources","food":999999}))
            .await,
        ServerMsg::Error { .. }
    ));
}

fn update(msg: ServerMsg) -> CityView {
    let ServerMsg::CityUpdate { city } = msg else {
        panic!("expected update, got {msg:?}")
    };
    city
}
fn rejected(msg: ServerMsg, expected: &str) {
    assert!(
        matches!(msg, ServerMsg::Error { code: protocol::ErrorCode::InvalidAction, ref message } if message == expected),
        "{msg:?}"
    );
}
#[tokio::test]
async fn upgrade_queue_refund_tick_and_owner_isolation() {
    use serde_json::json;
    let server = TestServer::start().await;
    let mut alice = server.login("alice").await;
    let mut other_session = server.login("alice").await;
    let mut bob = server.login("bob").await;
    let bob_before = bob.city().await;
    rejected(
        alice
            .request(json!({"type":"upgrade_building","building_id":2}))
            .await,
        "upgrade City Hall first",
    );
    let started = update(
        alice
            .request(json!({"type":"upgrade_building","building_id":1}))
            .await,
    );
    assert_eq!(started.resources.food, 700);
    assert_eq!(
        started.buildings[0].state,
        protocol::BuildingState::Upgrading
    );
    assert_eq!(started.buildings[0].completes_at, Some(220));
    assert_eq!(update(other_session.receive().await), started);
    assert_eq!(bob.city().await, bob_before);
    assert!(
        tokio::time::timeout(Duration::from_millis(50), bob.0.next())
            .await
            .is_err()
    );
    server.clock.set(220);
    let done = update(alice.receive().await);
    assert_eq!(done.buildings[0].level, 2);
    assert_eq!(done.buildings[0].state, protocol::BuildingState::Ready);
    assert_eq!(update(other_session.receive().await), done);
    let farm = update(
        alice
            .request(json!({"type":"upgrade_building","building_id":2}))
            .await,
    );
    update(
        alice
            .request(json!({"type":"upgrade_building","building_id":3}))
            .await,
    );
    rejected(
        alice
            .request(json!({"type":"upgrade_building","building_id":4}))
            .await,
        "all builders are busy",
    );
    rejected(
        alice
            .request(json!({"type":"upgrade_building","building_id":2}))
            .await,
        "building already has a job",
    );
    let cancelled = update(
        alice
            .request(json!({"type":"cancel_upgrade","building_id":2}))
            .await,
    );
    assert_eq!(cancelled.resources.wood, farm.resources.wood + 80);
    assert_eq!(cancelled.buildings[1].state, protocol::BuildingState::Ready);
    update(
        alice
            .request(json!({"type":"upgrade_building","building_id":4}))
            .await,
    );
}
#[tokio::test]
async fn persisted_upgrade_completes_after_restart() {
    use serde_json::json;
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("jobs.db");
    let server = TestServer::open(&path, 100).await;
    let mut client = server.login("alice").await;
    update(
        client
            .request(json!({"type":"upgrade_building","building_id":1}))
            .await,
    );
    client.0.close(None).await.unwrap();
    drop(client);
    drop(server);
    let server = TestServer::open(&path, 220).await;
    let mut client = server.login("alice").await;
    let city = client.city().await;
    assert_eq!(city.buildings[0].level, 2);
    assert!(city.buildings[0].completes_at.is_none());
    assert_eq!(city.resources.food, 720);
}
