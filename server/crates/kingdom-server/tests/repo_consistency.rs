//! Cross-checks between the data files and the rest of the repo, so data,
//! art and client never drift apart silently.

use std::path::Path;

use data::GameData;

/// Visual tiers per building: tier = 1 + (level - 1) / 5, see
/// `client/scripts/city/building_factory.gd` and `docs/ART_BIBLE.md`.
const MODEL_TIERS: u32 = 5;

#[test]
fn every_building_has_a_model_for_every_tier() {
    let data = GameData::load(GameData::repo_data_dir()).unwrap();
    let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../client/assets/models");
    let missing: Vec<_> = data
        .buildings()
        .flat_map(|b| (1..=MODEL_TIERS).map(move |tier| format!("{}_t{tier}.glb", b.id)))
        .filter(|file| {
            !models.join(file).exists() || !models.join(format!("{file}.import")).exists()
        })
        .collect();
    assert!(
        missing.is_empty(),
        "missing models (or their .import) for {missing:?}; add them to tools/blender/build_buildings.py          and run scripts/build_art.sh buildings"
    );
}

#[test]
fn client_tier_constants_match() {
    let gd = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../client/scripts/city/building_factory.gd");
    let text = std::fs::read_to_string(gd).unwrap();
    let expected = format!("const TIER_COUNT := {MODEL_TIERS}");
    assert!(
        text.contains(&expected),
        "client/scripts/city/building_factory.gd must declare `{expected}`"
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
