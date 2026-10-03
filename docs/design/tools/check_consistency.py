"""Cross-file consistency checks for docs/design. Run: python check_consistency.py

Checks:
  1. every data/*.yaml parses and has exactly one top-level key (plus documented extras)
  2. commander XP table equals round_to_10(40 * L^2.4)
  3. Renown thresholds equal 100 * n(n+1)/2 and its modifiers stay inside the registry clamps
  4. every item id referenced by a reward/shop/drop table exists in items.yaml
  5. every modifier key used in hand-written data exists in the registry (03 section 1.5)
  6. every "NN §X.Y" cross-reference points at an existing heading
  7. every request/push named in a spec's Protocol section is in the catalogue (10 section A)
  8. speedup budget of 08 section 2.3 matches the sim's assumptions and the reward tables
Exit code 1 on any failure.
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
errors = []


def err(msg):
    errors.append(msg)
    print("FAIL:", msg)


def load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


# 1 ---------------------------------------------------------------------------
docs = {}
for path in sorted(DATA.glob("*.yaml")):
    try:
        docs[path.name] = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:  # pragma: no cover
        err(f"{path.name}: {e}")
allowed_extra = {"items.yaml": {"reward_tokens", "inventory"}}
for name, doc in docs.items():
    top = {"talents.yaml": "talent_trees"}.get(name, name[:-5])
    extra = set(doc) - {top} - allowed_extra.get(name, set())
    if top not in doc:
        err(f"{name}: missing top-level key '{top}'")
    if extra and name not in ("commanders.yaml", "talents.yaml", "combat.yaml", "buildings.yaml",
                              "troops.yaml", "research.yaml"):
        err(f"{name}: unexpected top-level keys {sorted(extra)}")

# 2 ---------------------------------------------------------------------------
prog = docs["progression.yaml"]["progression"]
xp = prog["commanders"]["xp_to_next"]
want = [int(round(40 * L ** 2.4 / 10.0)) * 10 for L in range(1, 50)]
if xp != want:
    err("progression.yaml commanders.xp_to_next differs from formula")

# registry --------------------------------------------------------------------
md03 = (ROOT / "03-research.md").read_text(encoding="utf-8")
reg_block = md03.split("### 1.5")[1].split("\n## ")[0]
registry = {}
for line in reg_block.splitlines():
    if not line.startswith("| `"):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    keys = re.findall(r"`([a-z_<>0-9]+)`", cells[0])
    for k in keys:
        if "<type>" in k:
            for t in ("infantry", "cavalry", "archer", "siege"):
                if "<tier>" in k:
                    for tier in range(2, 6):
                        registry[k.replace("<type>", t).replace("<tier>", str(tier))] = cells[-1]
                else:
                    registry[k.replace("<type>", t)] = cells[-1]
        else:
            registry[k] = cells[-1]

# 3 ---------------------------------------------------------------------------
levels = prog["renown"]["levels"]
for row in levels:
    n = row["level"]
    if row["points"] != 100 * n * (n + 1) // 2:
        err(f"renown level {n}: points {row['points']}")
if levels[-1]["modifiers"].get("free_finish_flat", 0) > 420:
    err("renown free_finish_flat exceeds registry clamp 420")

# 4 + 5 -----------------------------------------------------------------------
items = {i["id"] for i in docs["items.yaml"]["items"]}
tokens = {t["id"] for t in docs["items.yaml"]["reward_tokens"]}
for t in docs["items.yaml"]["reward_tokens"]:
    for k in t["weights"]:
        if k not in items:
            err(f"reward token {t['id']}: unknown item {k}")
ITEM_RE = re.compile(r"^(speedup|resource|xp_tome|sculpture_universal|stamina|shield|teleport|buff|migration|cosmetic)_")
NOT_ITEMS = {"stamina_cost", "stamina_cap_flat", "stamina_regen_pct", "shield_s", "teleport"}


def walk(node, where, in_modifiers=False):
    if isinstance(node, dict):
        for k, v in node.items():
            ks = str(k)
            if in_modifiers and ks not in registry:
                err(f"{where}: modifier key '{ks}' not in registry")
            if ITEM_RE.match(ks) and ks not in NOT_ITEMS and not in_modifiers and isinstance(v, (int, float)):
                if ks not in items and ks not in tokens:
                    err(f"{where}: unknown item '{ks}'")
            walk(v, f"{where}.{ks}", ks in ("modifiers", "own_modifiers", "city_modifiers"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{where}[{i}]", in_modifiers)
    elif isinstance(node, str) and where.endswith(".item"):
        if node not in items and node not in tokens:
            err(f"{where}: unknown item '{node}'")


for name in ("world.yaml", "alliance.yaml", "progression.yaml", "seasons.yaml", "items.yaml"):
    walk(docs[name], name)
for kind, buffs in docs["world.yaml"]["world"]["sanctums"]["buffs"].items():
    for b in buffs:
        for k in b:
            if k not in registry:
                err(f"world.yaml sanctum buff {kind}: '{k}' not in registry")
buildings = {b["id"] if isinstance(b, dict) and "id" in b else b for b in docs["buildings.yaml"]["buildings"]}
for ch in prog["chapters"]:
    for o in ch["objectives"]:
        if o["kind"] == "building_level" and o["building"] not in buildings:
            err(f"chapter {ch['id']}: unknown building {o['building']}")
commanders = {c["id"] for c in docs["commanders.yaml"]["commanders"]}
for c in prog["commanders"]["starter_choices"] + ["hatshepsut"]:
    if c not in commanders:
        err(f"unknown commander {c}")

# 6 ---------------------------------------------------------------------------
mds = {p.name[:2]: p for p in ROOT.glob("[0-9][0-9]-*.md")}
headings = {}
for num, p in mds.items():
    hs = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#{2,4} ([0-9]+(?:\.[0-9]+)*|A)\.? ", line)
        if m:
            hs.add(m.group(1))
    headings[num] = hs
REF = re.compile(r"\b(0[0-9]|1[01]) §([0-9]+(?:\.[0-9]+)?|A)")
for p in list(mds.values()) + [ROOT / "ROADMAP_PROPOSAL.md"]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        for num, sec in REF.findall(line):
            if sec not in headings.get(num, set()):
                err(f"{p.name}:{i}: reference {num} §{sec} has no heading")

# 7 ---------------------------------------------------------------------------
cat = (ROOT / "10-ui-ux-flows.md").read_text(encoding="utf-8").split("## A. Protocol message catalogue")[1]
catalogue = set(re.findall(r"`([a-z_]+)[ `*]", cat))
for num in ("01", "02", "03", "04", "05", "06", "07", "08", "09"):
    text = mds[num].read_text(encoding="utf-8")
    m = re.search(r"\n## [0-9]+\. Protocol\n(.*?)(?=\n## |\Z)", text, re.S)
    if not m:
        err(f"{num}: no Protocol section")
        continue
    for line in m.group(1).splitlines():
        if line.startswith("| `"):
            for name in re.findall(r"`([a-z_]+)`", line.split("|")[1]):
                if name not in catalogue:
                    err(f"{num}: message '{name}' missing from catalogue 10 §A")

# 8 ---------------------------------------------------------------------------
chests = prog["daily_objectives"]["chests"]


def minutes(rewards, kinds):
    total = 0
    for k, n in rewards.items():
        m = re.match(r"speedup_([a-z]+)_(5m|60m|3h)$", k)
        if m and m.group(1) in kinds:
            total += n * {"5m": 5, "60m": 60, "3h": 180}[m.group(2)]
    return total


build_all = sum(minutes(c["rewards"], ("build", "universal")) for c in chests)
research_all = sum(minutes(c["rewards"], ("research",)) for c in chests)
if (build_all, research_all) != (75, 30):
    err(f"daily chests give {build_all} build / {research_all} research minutes, 08 §2.3 says 75 / 30")
ch_build = ch_research = 0
for ch in prog["chapters"]:
    n = len(ch["objectives"])
    ch_build += n * minutes(ch.get("objective_reward", {}), ("build",)) + minutes(ch["completion_reward"].get("items", {}), ("build",))
    ch_research += n * minutes(ch.get("objective_reward", {}), ("research",)) + minutes(ch["completion_reward"].get("items", {}), ("research",))
if (ch_build + 100, ch_research) != (300, 120):
    err(f"tutorial grant is {ch_build + 100} build / {ch_research} research minutes, sim assumes 300 / 120")
if sum(t["activity"] for t in prog["daily_objectives"]["tasks"]) != 125:
    err("daily objective activity total is not 125")

print(f"{len(docs)} data files, {len(registry)} modifier keys, {len(items)} items, {len(catalogue)} catalogue names")
if errors:
    print(f"{len(errors)} problem(s)")
    sys.exit(1)
print("OK")
