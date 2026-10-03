"""Single source of truth for the generated balance tables in docs/design.

Every number that appears in a generated table or in docs/design/data/*.yaml is
derived from the constants in this module. Edit here, then run
`python docs/design/tools/build_all.py` to regenerate YAML, doc tables and the
simulation outputs.

Conventions: times in seconds, costs in whole resource units, percentages as
plain numbers (5 == 5 %).
"""

from __future__ import annotations

import math

RES = ("food", "wood", "stone", "gold")
MAX_LEVEL = 25

# --------------------------------------------------------------------------
# City Hall backbone: every other building/research price is a fraction of it.
# --------------------------------------------------------------------------

MIN, HOUR, DAY = 60, 3600, 86400

# Seconds to upgrade City Hall *to* the given level (index = level).
CH_TIME = [
    0, 0,
    10, 60, 5 * MIN, 15 * MIN,                              # 2-5
    40 * MIN, 90 * MIN, 3 * HOUR, 5 * HOUR, 8 * HOUR,       # 6-10
    12 * HOUR, 17 * HOUR, 23 * HOUR, 30 * HOUR, 38 * HOUR,  # 11-15
    36 * HOUR, 44 * HOUR, 52 * HOUR, 63 * HOUR, 76 * HOUR,  # 16-20
    90 * HOUR, 108 * HOUR, 130 * HOUR, 155 * HOUR, 184 * HOUR,  # 21-25
]
# A reference time for "level 1" items (construction).
CH_TIME[1] = 5

# Total resource units to upgrade City Hall *to* the given level.
CH_COST = [
    0, 0,
    400, 900, 2_000, 4_500,
    10_000, 20_000, 38_000, 68_000, 120_000,
    190_000, 290_000, 440_000, 680_000, 1_050_000,
    1_500_000, 2_100_000, 3_000_000, 4_200_000, 5_900_000,
    8_200_000, 11_500_000, 16_000_000, 22_000_000, 30_000_000,
]
CH_COST[1] = 150


def mix_for_level(level: int) -> dict[str, float]:
    """Default resource mix of a cost at a given level (stone from 5, gold from 11)."""
    if level <= 4:
        return {"food": 0.5, "wood": 0.5, "stone": 0.0, "gold": 0.0}
    if level <= 10:
        return {"food": 0.4, "wood": 0.4, "stone": 0.2, "gold": 0.0}
    return {"food": 0.32, "wood": 0.32, "stone": 0.24, "gold": 0.12}


def nice_time(s: float) -> int:
    """Round a duration to a human-friendly value."""
    if s < 60:
        return max(1, round(s))
    if s < 10 * MIN:
        return int(round(s / 5) * 5)
    if s < 6 * HOUR:
        return int(round(s / 60) * 60)
    return int(round(s / 300) * 300)


def nice(v: float, sig: int = 3) -> int:
    """Round to `sig` significant digits."""
    if v <= 0:
        return 0
    mag = 10 ** (math.floor(math.log10(v)) - sig + 1)
    return int(round(v / mag) * mag)


def round_to(v: float, step: int) -> int:
    return int(round(v / step) * step)


def split_cost(total: float, mix: dict[str, float]) -> dict[str, int]:
    return {r: nice(total * mix[r]) for r in RES}


# --------------------------------------------------------------------------
# Buildings
# --------------------------------------------------------------------------

# City Hall level L additionally requires `wall` at L-1 and this building at L-1.
CH_SECOND_PREREQ = {
    3: "farm", 4: "barracks", 5: "storehouse", 6: "hospital", 7: "academy",
    8: "archery_range", 9: "scout_camp", 10: "alliance_hall", 11: "stable",
    12: "storehouse", 13: "war_hall", 14: "siege_workshop", 15: "watchtower",
    16: "academy", 17: "hospital", 18: "caravan_post", 19: "barracks",
    20: "hall_of_heroes", 21: "storehouse", 22: "alliance_hall", 23: "war_hall",
    24: "academy", 25: "watchtower",
}

# id, name, footprint, max_count, unlock CH, time/cost factor vs City Hall, cost mix override
BUILDINGS = [
    # id, name, footprint, max_count, requires_city_hall, factor, mix
    ("city_hall", "City Hall", 4, 1, 0, 1.00, None),
    ("wall", "City Wall", 2, 1, 1, 0.60, "stone_heavy"),
    ("farm", "Farm", 2, 4, 1, 0.20, "wood_heavy"),
    ("lumber_mill", "Lumber Mill", 2, 4, 1, 0.20, "food_heavy"),
    ("quarry", "Quarry", 2, 4, 4, 0.20, None),
    ("goldmine", "Goldmine", 2, 4, 10, 0.20, "no_gold"),
    ("storehouse", "Storehouse", 2, 1, 2, 0.40, None),
    ("barracks", "Barracks", 3, 1, 1, 0.55, None),
    ("archery_range", "Archery Range", 3, 1, 3, 0.55, None),
    ("stable", "Stable", 3, 1, 5, 0.55, None),
    ("siege_workshop", "Siege Workshop", 3, 1, 7, 0.55, None),
    ("hospital", "Hospital", 2, 4, 2, 0.30, None),
    ("academy", "Academy", 3, 1, 3, 0.70, None),
    ("scout_camp", "Scout Camp", 2, 1, 2, 0.35, None),
    ("watchtower", "Watchtower", 2, 1, 5, 0.45, "stone_heavy"),
    ("alliance_hall", "Alliance Hall", 3, 1, 3, 0.50, None),
    ("hall_of_heroes", "Hall of Heroes", 3, 1, 4, 0.50, None),
    ("war_hall", "War Hall", 3, 1, 8, 0.55, None),
    ("caravan_post", "Caravan Post", 2, 1, 9, 0.40, None),
]
BUILDING_IDS = [b[0] for b in BUILDINGS]


def _mix(kind: str | None, level: int) -> dict[str, float]:
    base = mix_for_level(level)
    if kind is None:
        return base
    if kind == "wood_heavy":  # farms are built from wood
        m = dict(base)
        m["wood"] += m["food"]
        m["food"] = 0.0
        return m
    if kind == "food_heavy":  # lumber mills are paid in food
        m = dict(base)
        m["food"] += m["wood"]
        m["wood"] = 0.0
        return m
    if kind == "stone_heavy":
        if level <= 4:
            return base
        m = dict(base)
        shift = 0.5 * m["food"]
        m["food"] -= shift
        m["stone"] += shift
        return m
    if kind == "no_gold":
        m = dict(base)
        m["food"] += m["gold"] / 2
        m["wood"] += m["gold"] / 2
        m["gold"] = 0.0
        return m
    raise ValueError(kind)


def production_per_hour(bid: str, level: int) -> int:
    base = 300 + 60 * level ** 1.9
    mult = {"farm": 1.0, "lumber_mill": 1.0, "quarry": 0.75, "goldmine": 0.5}[bid]
    return round_to(base * mult, 10)


BUFFER_HOURS = 10  # a production building stops accruing after this many hours uncollected


def march_slots(ch: int) -> int:
    return 1 + sum(ch >= t for t in (6, 11, 17, 22))


def march_capacity(ch: int) -> int:
    return round_to(500 * ch ** 1.77, 100)


def building_stats(bid: str, level: int) -> dict:
    """Per-level effect fields of a building (the non-cost columns)."""
    L = level
    if bid == "city_hall":
        return {"march_slots": march_slots(L), "march_capacity": march_capacity(L)}
    if bid in ("farm", "lumber_mill", "quarry", "goldmine"):
        p = production_per_hour(bid, L)
        return {"production_per_hour": p, "buffer_capacity": p * BUFFER_HOURS}
    if bid == "storehouse":
        base = round_to(2000 * L ** 2.2, 100)
        return {"protect_food": base, "protect_wood": base,
                "protect_stone": round_to(base * 0.75, 100), "protect_gold": round_to(base * 0.5, 100)}
    if bid in ("barracks", "archery_range", "stable", "siege_workshop"):
        return {"train_batch": round_to(50 * L ** 1.45, 10)}
    if bid == "hospital":
        return {"hospital_capacity": round_to(150 * L ** 1.65, 50)}
    if bid == "academy":
        return {}
    if bid == "wall":
        return {"wall_durability": round_to(5000 * L ** 1.5, 500), "garrison_defense_pct": round(0.4 * L, 1)}
    if bid == "watchtower":
        return {"tower_potency": 20 + 4 * L, "intel_tier": 1 + (L >= 5) + (L >= 10) + (L >= 15) + (L >= 20)}
    if bid == "scout_camp":
        return {"scouts": 1 + (L >= 8) + (L >= 16), "scout_speed": 120 + 6 * L, "scout_range": 300 + 40 * L}
    if bid == "alliance_hall":
        return {"help_limit": 5 + L // 2, "reinforcement_capacity": round_to(4000 * L ** 1.45, 1000)}
    if bid == "war_hall":
        return {"rally_capacity": round_to(10000 * L ** 1.4, 1000)}
    if bid == "caravan_post":
        return {"caravan_load": round_to(20000 * L ** 1.3, 1000), "caravan_tax_pct": max(4, 20 - round(L * 0.64))}
    if bid == "hall_of_heroes":
        return {"daily_sculptures": 1 + L // 8, "commander_xp_pct": L}
    raise ValueError(bid)


def building_requires(bid: str, level: int) -> dict[str, int]:
    """Prerequisite building levels (other than its own level-1)."""
    if bid == "city_hall":
        req = {}
        if level >= 3:
            req["wall"] = level - 1
            req[CH_SECOND_PREREQ[level]] = level - 1
        return req
    unlock = next(b[4] for b in BUILDINGS if b[0] == bid)
    return {"city_hall": max(unlock, level)}


def building_level(bid: str, level: int) -> dict:
    _, _, _, _, _, factor, mixkind = next(b for b in BUILDINGS if b[0] == bid)
    t = nice_time(CH_TIME[level] * factor) if not (bid == "city_hall" and level == 1) else 0
    total = CH_COST[level] * factor
    cost = split_cost(total, _mix(mixkind, level))
    if bid == "city_hall" and level == 1:
        cost = {r: 0 for r in RES}
    power = round(factor * 50 * level ** 2.3)
    return {"level": level, "cost": cost, "time_s": t, "requires": building_requires(bid, level),
            "power": power, **building_stats(bid, level)}


# --------------------------------------------------------------------------
# Troops
# --------------------------------------------------------------------------

TROOP_TYPES = ("infantry", "cavalry", "archer", "siege")
TIER_MULT = [None, 1.00, 1.30, 1.65, 2.05, 2.50]
TIER_COST_MULT = [None, 1.0, 1.6, 2.6, 4.2, 6.8]
TIER_TIME = [None, 10, 18, 30, 48, 75]
TIER_POWER = [None, 1, 2, 4, 7, 11]
TIER_LOAD_MULT = [None, 1.0, 1.15, 1.3, 1.45, 1.6]
TIER_UPKEEP = [None, 0.005, 0.008, 0.012, 0.018, 0.026]
TIER_GOLD = [None, 0, 0, 0, 10, 30]
TIER_BUILDING_LEVEL = [None, 1, 5, 10, 17, 25]
TROOP_BASE = {
    #            atk  def  hp  speed load  cost(food, wood, stone)
    "infantry": (95, 110, 115, 36, 10, (60, 40, 0)),
    "cavalry": (110, 95, 110, 54, 8, (60, 20, 20)),
    "archer": (115, 95, 100, 39, 6, (30, 70, 0)),
    "siege": (70, 80, 90, 27, 22, (20, 50, 40)),
}
TROOP_BUILDING = {"infantry": "barracks", "cavalry": "stable", "archer": "archery_range", "siege": "siege_workshop"}
TROOP_NAMES = {
    "infantry": ["Levy Spearmen", "Shieldbearers", "Men-at-Arms", "Halberdiers", "Iron Guard"],
    "cavalry": ["Outriders", "Lancers", "Horse Guard", "Cataphracts", "Storm Riders"],
    "archer": ["Slingers", "Bowmen", "Longbowmen", "Arbalesters", "Sky Wardens"],
    "siege": ["Battering Rams", "Mangonels", "Ballistae", "Trebuchets", "Siege Titans"],
}


def troop(ttype: str, tier: int) -> dict:
    atk, de, hp, speed, load, (f, w, s) = TROOP_BASE[ttype]
    m = TIER_MULT[tier]
    cm = TIER_COST_MULT[tier]
    time_mult = 1.2 if ttype == "siege" else 1.0
    return {
        "id": f"{ttype}_t{tier}", "name": TROOP_NAMES[ttype][tier - 1], "type": ttype, "tier": tier,
        "attack": round(atk * m), "defense": round(de * m), "health": round(hp * m),
        "speed": speed, "load": round(load * TIER_LOAD_MULT[tier]),
        "upkeep_food_per_hour": TIER_UPKEEP[tier], "power": TIER_POWER[tier],
        "cost": {"food": round(f * cm), "wood": round(w * cm), "stone": round(s * cm),
                 "gold": round(TIER_GOLD[tier] * (1.2 if ttype == "siege" else 1.0))},
        "train_time_s": round(TIER_TIME[tier] * time_mult),
        "building": TROOP_BUILDING[ttype], "building_level": TIER_BUILDING_LEVEL[tier],
        "research": None if tier == 1 else f"{ttype}_t{tier}",
    }


ALL_TROOPS = [troop(t, k) for t in TROOP_TYPES for k in range(1, 6)]

# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------

RESEARCH_FACTOR = 0.25  # node-level time as a fraction of City Hall time at the gating academy level
RESEARCH_COST_RATIO = 0.5  # research cost factor = time factor * this

# tree, id, name, max_level, effect key, value per level, first academy level, last academy level, prereqs
_R = [
    ("economy", "crop_rotation", "Crop Rotation", 10, "food_production_pct", 2.0, 3, 24, {}),
    ("economy", "sawpits", "Sawpits", 10, "wood_production_pct", 2.0, 3, 24, {}),
    ("economy", "masonry", "Masonry", 10, "build_speed_pct", 1.0, 3, 15, {}),
    ("economy", "scholarship", "Scholarship", 10, "research_speed_pct", 1.5, 4, 16, {"masonry": 1}),
    ("economy", "foraging", "Foraging", 10, "gather_speed_food_pct", 3.0, 4, 24, {"crop_rotation": 1}),
    ("economy", "timber_hauling", "Timber Hauling", 10, "gather_speed_wood_pct", 3.0, 4, 24, {"sawpits": 1}),
    ("economy", "stonecutting", "Stonecutting", 10, "stone_production_pct", 2.0, 5, 24, {"masonry": 2}),
    ("economy", "quarry_camps", "Quarry Camps", 10, "gather_speed_stone_pct", 3.0, 6, 24, {"stonecutting": 1}),
    ("economy", "pack_saddles", "Pack Saddles", 10, "troop_load_pct", 2.5, 6, 24, {"foraging": 2, "timber_hauling": 2}),
    ("economy", "granaries", "Hidden Granaries", 10, "storehouse_protection_pct", 5.0, 7, 25, {"crop_rotation": 3}),
    ("economy", "field_medicine", "Field Medicine", 10, "heal_speed_pct", 3.0, 8, 25, {"scholarship": 2}),
    ("economy", "cartography", "Cartography", 5, "scout_speed_pct", 6.0, 8, 20, {"scholarship": 1}),
    ("economy", "coinage", "Coinage", 10, "gold_production_pct", 2.0, 10, 25, {"stonecutting": 3}),
    ("economy", "prospecting", "Prospecting", 10, "gather_speed_gold_pct", 3.0, 11, 25, {"coinage": 1, "quarry_camps": 3}),
    ("economy", "engineering", "Engineering", 10, "build_speed_pct", 1.0, 16, 25, {"masonry": 10}),
    ("economy", "encyclopedia", "Encyclopedia", 10, "research_speed_pct", 1.5, 17, 25, {"scholarship": 10}),
    ("military", "drill", "Drill", 10, "train_speed_pct", 2.0, 3, 24, {}),
    ("military", "forced_march", "Forced March", 10, "march_speed_pct", 1.0, 6, 24, {"drill": 2}),
    ("military", "mustering", "Mustering", 10, "march_capacity_pct", 1.0, 8, 25, {"drill": 3}),
    ("military", "field_rations", "Field Rations", 5, "troop_upkeep_pct", -6.0, 8, 20, {"drill": 3}),
    ("military", "hospital_wards", "Hospital Wards", 10, "hospital_capacity_pct", 2.0, 8, 25, {"drill": 4}),
    ("military", "fortification", "Fortification", 10, "wall_durability_pct", 3.0, 9, 25, {"drill": 4}),
    ("military", "war_councils", "War Councils", 10, "rally_capacity_pct", 1.0, 12, 25, {"mustering": 3}),
]
_STAT_NAMES = {
    "infantry": ("Tempered Blades", "Shield Drill", "Hardened Marches"),
    "cavalry": ("Lance Drill", "Barding", "Remount Herds"),
    "archer": ("Fletching", "Pavise Lines", "Volley Discipline"),
    "siege": ("Counterweights", "Mantlets", "Seasoned Timber"),
}
_first = {"infantry": 4, "archer": 5, "cavalry": 6, "siege": 8}
for _t in TROOP_TYPES:
    for _i, _stat in enumerate(("attack", "defense", "health")):
        _R.append(("military", f"{_t}_{_stat}", _STAT_NAMES[_t][_i], 10, f"{_t}_{_stat}_pct", 1.0,
                   _first[_t] + _i, 25, {"drill": 1}))
_TIER_REQ_ACADEMY = {2: 5, 3: 10, 4: 17, 5: 25}
_TIER_FACTOR = {2: 0.5, 3: 0.75, 4: 1.0, 5: 1.5}
_TIER_UNLOCK_NAMES = {2: "Standing Army", 3: "Professional Army", 4: "Elite Army", 5: "Peerless Army"}
for _t in TROOP_TYPES:
    for _k in (2, 3, 4, 5):
        pre = {f"{_t}_attack": {2: 1, 3: 3, 4: 6, 5: 10}[_k]}
        if _k > 2:
            pre[f"{_t}_t{_k - 1}"] = 1
        _R.append(("military", f"{_t}_t{_k}", f"{_TIER_UNLOCK_NAMES[_k]}: {_t.title()}", 1,
                   f"unlock_{_t}_t{_k}", 1.0, _TIER_REQ_ACADEMY[_k], _TIER_REQ_ACADEMY[_k], pre))


def research_nodes() -> list[dict]:
    out = []
    for tree, rid, name, maxl, key, val, a0, a1, pre in _R:
        levels = []
        for n in range(1, maxl + 1):
            acad = a0 if maxl == 1 else round(a0 + (a1 - a0) * (n - 1) / (maxl - 1))
            factor = RESEARCH_FACTOR
            if key.startswith("unlock_"):
                factor = _TIER_FACTOR[int(rid[-1])]
            t = nice_time(max(CH_TIME[acad] * factor, 5))
            cost = split_cost(CH_COST[acad] * factor * RESEARCH_COST_RATIO, mix_for_level(acad))
            levels.append({"level": n, "academy": acad, "cost": cost, "time_s": t,
                           "value": round(val * n, 2), "power": round(factor * 40 * acad ** 2.0)})
        out.append({"tree": tree, "id": rid, "name": name, "max_level": maxl, "effect": key,
                    "requires": pre, "levels": levels})
    return out


def fmt_time(s: int) -> str:
    if s < 60:
        return f"{s}s"
    if s < HOUR:
        m, r = divmod(s, 60)
        return f"{m}m" + (f" {r}s" if r else "")
    if s < DAY:
        h, r = divmod(s, HOUR)
        return f"{h}h" + (f" {r // 60}m" if r else "")
    d, r = divmod(s, DAY)
    return f"{d}d" + (f" {r // HOUR}h" if r >= HOUR else "") + (f" {(r % HOUR) // 60}m" if r % HOUR else "")


def fmt_n(v: int) -> str:
    return f"{v:,}"
