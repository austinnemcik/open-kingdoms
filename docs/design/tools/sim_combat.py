"""Reference implementation of the battle tick in 05-combat.md.

Pure and deterministic: only + - * / sqrt and floor on IEEE-754 doubles, armies
processed in ascending id order, all damage computed from the tick-start
snapshot and then applied simultaneously. The Rust engine in `game-core` must
reproduce the numbers printed by `python sim_combat.py` exactly (they are the
worked example / golden test in 05-combat.md section 12).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import okdata as d

K_DAMAGE = 200.0
SMALL_ARMY_THRESHOLD = 200
COUNTER_ADVANTAGE = 1.20
COUNTER_DISADVANTAGE = 0.90
RAGE_PER_ATTACK = 90
RAGE_PER_COUNTER = 10
RAGE_COUNTER_CAP = 30
RAGE_MAX = 1000
SEVERE_RATIO = 0.40
MIN_FACTOR = 0.1
COUNTERS = {"infantry": "cavalry", "cavalry": "archer", "archer": "infantry"}  # key beats value

TROOPS = {t["id"]: t for t in d.ALL_TROOPS}


@dataclass
class Group:
    troop: str
    healthy: int
    lost: int = 0          # cumulative troops knocked out this battle
    carry: float = 0.0     # fractional loss carried to the next tick

    @property
    def severe(self) -> int:
        return math.floor(self.lost * SEVERE_RATIO)

    @property
    def light(self) -> int:
        return self.lost - self.severe


@dataclass
class Army:
    id: int
    name: str
    groups: list[Group]
    target: int | None = None
    mods: dict[str, float] = field(default_factory=dict)
    skill_potency: float = 0.0   # 0 = no commander
    rage: int = 0

    @property
    def n(self) -> int:
        return sum(g.healthy for g in self.groups)

    def mod(self, key: str) -> float:
        return self.mods.get(key, 0.0)

    def stat(self, g: Group, stat: str) -> float:
        t = TROOPS[g.troop]
        pct = self.mod(f"{stat}_pct") + self.mod(f"{t['type']}_{stat}_pct")
        return t[stat] * max(MIN_FACTOR, 1 + pct / 100)

    def army_attack(self) -> float:
        n = self.n
        return sum(g.healthy * self.stat(g, "attack") for g in self.groups) / n if n else 0.0


def counter_multiplier(att: Army, dfn: Army) -> float:
    n, m = att.n, dfn.n
    if n == 0 or m == 0:
        return 1.0
    total = 0.0
    for a in att.groups:
        ta = TROOPS[a.troop]["type"]
        for b in dfn.groups:
            tb = TROOPS[b.troop]["type"]
            c = COUNTER_ADVANTAGE if COUNTERS.get(ta) == tb else COUNTER_DISADVANTAGE if COUNTERS.get(tb) == ta else 1.0
            total += (a.healthy / n) * (b.healthy / m) * c
    return total


def size_term(n: int) -> float:
    if n >= SMALL_ARMY_THRESHOLD:
        return math.sqrt(n)
    return n / math.sqrt(SMALL_ARMY_THRESHOLD)


def base_damage(att: Army, dfn: Army, potency: float, kind: str) -> float:
    f = lambda pct: max(MIN_FACTOR, 1 + pct / 100)  # noqa: E731
    b = K_DAMAGE * (potency / 100) * size_term(att.n) * att.army_attack() * counter_multiplier(att, dfn)
    b *= f(att.mod("damage_dealt_pct")) * f(dfn.mod("damage_taken_pct")) * f(att.mod(f"{kind}_damage_pct"))
    if kind == "skill":
        b *= f(dfn.mod("skill_damage_taken_pct"))
    return b


def apply_damage(dfn: Army, snapshot: list[int], dmg: float) -> int:
    """Distribute `dmg` over the defender's groups (by tick-start share) and return troops lost."""
    m = sum(snapshot)
    lost_total = 0
    for g, count in zip(dfn.groups, snapshot):
        if count == 0:
            continue
        kills = dmg * (count / m) / (dfn.stat(g, "defense") * dfn.stat(g, "health")) + g.carry
        whole = min(g.healthy, math.floor(kills))
        g.carry = kills - math.floor(kills) if whole < g.healthy else 0.0
        g.healthy -= whole
        g.lost += whole
        lost_total += whole
    return lost_total


def tick(armies: dict[int, Army]) -> dict[int, dict]:
    """Advance one battle tick. Returns per-army log entries."""
    ids = sorted(armies)
    snap = {i: [g.healthy for g in armies[i].groups] for i in ids}
    incoming: dict[int, float] = {i: 0.0 for i in ids}
    log = {i: {"attack": 0.0, "counter": 0.0, "skill": 0.0, "lost": 0, "skill_fired": False} for i in ids}
    rage_gain = {i: 0 for i in ids}
    for i in ids:
        a = armies[i]
        if a.n == 0:
            continue
        if a.target is not None and armies[a.target].n > 0:
            t = armies[a.target]
            if a.skill_potency and a.rage >= RAGE_MAX:
                dmg = base_damage(a, t, a.skill_potency, "skill")
                incoming[t.id] += dmg
                log[i]["skill"] = dmg
                log[i]["skill_fired"] = True
                a.rage = 0
            dmg = base_damage(a, t, 100, "normal")
            incoming[t.id] += dmg
            log[i]["attack"] = dmg
            rage_gain[i] += RAGE_PER_ATTACK
        counters = 0
        for j in ids:
            b = armies[j]
            if j != i and b.target == i and b.n > 0:
                dmg = base_damage(a, b, 100, "counter")
                incoming[j] += dmg
                log[i]["counter"] += dmg
                counters += 1
        rage_gain[i] += min(RAGE_COUNTER_CAP, RAGE_PER_COUNTER * counters)
    for i in ids:
        a = armies[i]
        if incoming[i] > 0:
            log[i]["lost"] = apply_damage(a, snap[i], incoming[i])
        if a.skill_potency:
            gain = math.floor(rage_gain[i] * max(MIN_FACTOR, 1 + a.mod("rage_gain_pct") / 100))
            a.rage = min(RAGE_MAX, a.rage + gain)
    return log


def run(armies: dict[int, Army], max_ticks: int = 3600, show: int = 3, quiet: bool = False) -> int:
    t = 0
    while all(a.n > 0 for a in armies.values()) and t < max_ticks:
        t += 1
        log = tick(armies)
        if not quiet and (t <= show or any(e["skill_fired"] for e in log.values()) and t <= 12):
            for i, a in armies.items():
                e = log[i]
                skill = f" skill={e['skill']:.1f}" if e["skill_fired"] else ""
                print(f"tick {t:>3} {a.name}: attack={e['attack']:.1f} counter={e['counter']:.1f}{skill} "
                      f"lost={e['lost']} healthy={[g.healthy for g in a.groups]} rage={a.rage}")
    if not quiet:
        print(f"battle ends after tick {t}")
        for a in armies.values():
            print(f"  {a.name}: " + ", ".join(
                f"{g.troop} healthy={g.healthy} light={g.light} severe={g.severe}" for g in a.groups))
    return t


def example(skill: bool) -> dict[int, Army]:
    a = Army(1, "A", [Group("infantry_t4", 10000), Group("archer_t3", 5000)], target=2,
             skill_potency=600.0 if skill else 0.0, mods={"infantry_attack_pct": 10.0} if skill else {})
    b = Army(2, "B", [Group("cavalry_t4", 12000)], target=1)
    return {1: a, 2: b}


def main() -> None:
    print("== Example 1: no commanders ==")
    run(example(False))
    print("== Example 2: A has a commander (active skill potency 600, +10% infantry attack) ==")
    run(example(True))
    print("== Durations (mirror infantry_t4, no commanders) ==")
    for n in (1000, 10000, 100000, 200000):
        arm = {1: Army(1, "X", [Group("infantry_t4", n)], target=2), 2: Army(2, "Y", [Group("infantry_t4", n)], target=1)}
        print(f"  {n:>7} vs {n:>7}: {run(arm, quiet=True)} ticks")


if __name__ == "__main__":
    main()
