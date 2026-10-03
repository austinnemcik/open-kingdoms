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
        self.receive().await
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
        let data = GameData::load(GameData::repo_data_dir()).unwrap();
        let clock = Arc::new(ManualClock::new(100));
        let kingdom = Arc::new(Kingdom::with_clock(
            data,
            Box::new(SqliteStore::open(":memory:").unwrap()),
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
