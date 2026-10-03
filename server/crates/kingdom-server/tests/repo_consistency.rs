//! Cross-checks between the data files and the rest of the repo, so data,
//! art and client never drift apart silently.

use std::path::Path;

use data::GameData;

#[test]
fn every_building_has_a_model() {
    let data = GameData::load(GameData::repo_data_dir()).unwrap();
    let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../client/assets/models");
    let missing: Vec<_> = data
        .buildings()
        .map(|b| b.id.as_str())
        .filter(|id| !models.join(format!("{id}.glb")).exists())
        .collect();
    assert!(
        missing.is_empty(),
        "missing models for {missing:?}; add them to tools/blender/build_buildings.py and run it"
    );
}

#[test]
fn client_and_server_protocol_versions_match() {
    let gd = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../client/scripts/net/protocol.gd");
    let text = std::fs::read_to_string(gd).unwrap();
    let expected = format!("const VERSION := {}", protocol::PROTOCOL_VERSION);
    assert!(
        text.contains(&expected),
        "client/scripts/net/protocol.gd must declare `{expected}`"
    );
}
