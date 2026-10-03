"""Economy pacing simulation: when does a player reach each City Hall level?

Models the rules in 01-city-economy.md / 03-research.md / 08-events-and-progression.md:
two builders, one research slot, prerequisites, lazy production with a 10 h
buffer, gathering marches, alliance helps, earned speedups, Renown and alliance
research speed bonuses. Deliberately pessimistic about player skill: actions only
happen during fixed play sessions.

Usage: python sim_economy.py [--markdown]
"""

from __future__ import annotations

import sys

import okdata as d

PROFILES = {
    # sessions (hour of day), session length s, build speedup min/day, research speedup min/day,
    # fraction of help limit received, gathering duty cycle, renown points per day
    "active": dict(sessions=(7, 10, 13, 16, 19, 22), session_len=20 * 60, build_sp=150, research_sp=90,
                   help_frac=0.8, gather_duty=0.80, renown_per_day=100),
    "regular": dict(sessions=(8, 13, 21), session_len=15 * 60, build_sp=90, research_sp=60,
                    help_frac=0.6, gather_duty=0.60, renown_per_day=70),
}

GATHER_RATE = {"food": 18000, "wood": 18000, "stone": 13500, "gold": 9000}  # per march-hour (06-world-map)
TROOP_SPEND_SHARE = 0.30  # share of income an average player spends on troops/healing
RESEARCH_PRIORITY = [
    "masonry", "scholarship", "crop_rotation", "sawpits", "foraging", "timber_hauling", "drill",
    "stonecutting", "quarry_camps", "pack_saddles", "engineering", "encyclopedia", "coinage", "prospecting",
    "infantry_attack", "infantry_t2", "infantry_defense", "infantry_health", "infantry_t3", "mustering",
    "forced_march", "infantry_t4", "hospital_wards", "field_medicine", "granaries", "fortification",
]
SIDE_PRIORITY = ["wall", "academy", "farm", "lumber_mill", "quarry", "goldmine", "barracks", "hospital", "storehouse",
                 "alliance_hall", "archery_range", "stable", "scout_camp", "siege_workshop", "war_hall",
                 "watchtower", "hall_of_heroes", "caravan_post"]
RENOWN_THRESHOLDS = [100 * n * (n + 1) // 2 for n in range(1, 16)]  # cumulative points for level n


def renown_level(points: float) -> int:
    return sum(points >= t for t in RENOWN_THRESHOLDS)


class Sim:
    def __init__(self, profile: str):
        self.p = PROFILES[profile]
        self.t = 7 * 3600.0
        self.res = {"food": 1000.0, "wood": 1000.0, "stone": 0.0, "gold": 0.0}
        self.levels: dict[str, list[int]] = {b: [] for b in d.BUILDING_IDS}
        for b in ("city_hall", "farm", "lumber_mill", "barracks", "wall"):
            self.levels[b] = [1]
        self.jobs: list[list] = []  # [finish, bid, idx, critical]
        self.research: dict[str, int] = {}
        self.rjob = None  # [finish, node, level]
        self.nodes = {n["id"]: n for n in d.research_nodes()}
        self.build_sp = 300.0 * 60  # tutorial grant (08: chapter 1 rewards)
        self.research_sp = 120.0 * 60
        self.last_collect = self.t
        self.reached = {1: 0.0}
        self.wait_res = 0.0
        self.renown_pts = 0.0

    # ---- modifiers -------------------------------------------------------
    def mod(self, key: str) -> float:
        total = 0.0
        for nid, lvl in self.research.items():
            n = self.nodes[nid]
            if n["effect"] == key:
                total += n["levels"][lvl - 1]["value"]
        r = renown_level(self.renown_pts)
        if key in ("build_speed_pct", "research_speed_pct"):
            total += min(r, 10) * 1.0
            total += min(5.0, 0.5 * (self.t / d.DAY // 7))  # alliance research (07)
        if key.startswith("gather_speed"):
            total += min(r, 10) * 1.0 + min(10.0, 1.0 * (self.t / d.DAY // 7))
        return total

    @property
    def ch(self) -> int:
        return self.levels["city_hall"][0]

    def lvl(self, bid: str) -> int:
        return max(self.levels[bid], default=0)

    def busy(self, bid: str, idx: int) -> bool:
        return any(j[1] == bid and j[2] == idx for j in self.jobs)

    def can_afford(self, cost: dict, reserve: dict | None = None) -> bool:
        return all(self.res[r] >= cost[r] + (reserve[r] if reserve else 0) for r in d.RES)

    def pay(self, cost: dict) -> None:
        for r in d.RES:
            self.res[r] -= cost[r]

    # ---- income ----------------------------------------------------------
    def collect(self) -> None:
        dt = self.t - self.last_collect
        if dt <= 0:
            return
        hours = dt / 3600
        income = {r: 0.0 for r in d.RES}
        prod_key = {"farm": "food", "lumber_mill": "wood", "quarry": "stone", "goldmine": "gold"}
        for bid, r in prod_key.items():
            for lv in self.levels[bid]:
                rate = d.production_per_hour(bid, lv) * (1 + self.mod(f"{r}_production_pct") / 100)
                income[r] += rate * min(hours, d.BUFFER_HOURS)
        # gathering: each march goes to whichever unlocked resource is scarcest relative to the cost mix
        if self.ch >= 2:
            share = d.mix_for_level(2 if self.ch < 4 else 6 if self.ch < 10 else 12)
            cap = 0.7 * d.march_capacity(self.ch) * 9 * (1 + self.mod("troop_load_pct") / 100)
            for _ in range(d.march_slots(self.ch)):
                r = min((x for x in d.RES if share[x] > 0), key=lambda x: (self.res[x] + income[x]) / share[x])
                rate = GATHER_RATE[r] * (1 + self.mod(f"gather_speed_{r}_pct") / 100)
                income[r] += min(cap * max(1.0, hours / 4), rate * hours * self.p["gather_duty"])
        keep = 1.0 if self.ch < 4 else 1.0 - TROOP_SPEND_SHARE
        for r in d.RES:
            self.res[r] += income[r] * keep
        self.last_collect = self.t

    # ---- building --------------------------------------------------------
    def start_build(self, bid: str, idx: int, critical: bool) -> bool:
        cur = self.levels[bid][idx] if idx < len(self.levels[bid]) else 0
        spec = d.building_level(bid, cur + 1)
        if not self.can_afford(spec["cost"]):
            return False
        self.pay(spec["cost"])
        dur = spec["time_s"] / (1 + self.mod("build_speed_pct") / 100)
        ah = self.lvl("alliance_hall")
        if ah and self.t > d.DAY:
            helps = int(self.p["help_frac"] * d.building_stats("alliance_hall", ah)["help_limit"])
            dur = max(0.0, dur - helps * max(60.0, 0.01 * dur))
        if idx >= len(self.levels[bid]):
            self.levels[bid].append(0)
        self.jobs.append([self.t + dur, bid, idx, critical])
        return True

    def critical_targets(self) -> list[tuple[str, int]]:
        nxt = self.ch + 1
        if nxt > d.MAX_LEVEL:
            return []
        req = d.building_requires("city_hall", nxt)
        todo = []
        for bid, need in req.items():
            if not self.levels[bid]:
                todo.append((bid, 0))
            elif self.levels[bid][0] < need:
                todo.append((bid, 0))
        return todo or [("city_hall", 0)]

    def side_target(self, max_dur: float):
        best = None
        for bid in SIDE_PRIORITY:
            b = next(x for x in d.BUILDINGS if x[0] == bid)
            if self.ch < b[4]:
                continue
            count = len(self.levels[bid])
            cands = [(i, self.levels[bid][i]) for i in range(count)]
            if count < b[3]:
                cands.append((count, 0))
            for idx, cur in cands:
                if cur >= self.ch or self.busy(bid, idx):
                    continue
                spec = d.building_level(bid, cur + 1)
                if spec["time_s"] > max_dur:
                    continue
                upcoming = any(d.CH_SECOND_PREREQ.get(n) == bid for n in range(self.ch + 2, self.ch + 6))
                eco = bid in ("farm", "lumber_mill", "quarry", "goldmine", "academy") and cur < self.ch - 3
                key = (0 if eco else 1 if upcoming or bid == "wall" else 2, cur, SIDE_PRIORITY.index(bid))
                if best is None or key < best[0]:
                    best = (key, bid, idx, spec)
        return best

    def assign_builders(self) -> None:
        while len(self.jobs) < 2:
            started = False
            crit = [c for c in self.critical_targets() if not self.busy(*c)]
            for bid, idx in crit:
                if self.start_build(bid, idx, True):
                    started = True
                    break
            if started:
                continue
            # Side work: only things that finish before the critical job, and keep a reserve.
            crit_remaining = max((j[0] - self.t for j in self.jobs if j[3]), default=0.0)
            if crit and not any(j[3] for j in self.jobs):
                break  # waiting on resources for the critical path; don't spend elsewhere
            side = self.side_target(max(crit_remaining * 1.2, 600))
            if side is None:
                break
            _, bid, idx, spec = side
            nxt_cost = d.building_level("city_hall", min(self.ch + 1, d.MAX_LEVEL))["cost"]
            reserve = {r: nxt_cost[r] * 0.5 for r in d.RES}
            if not self.can_afford(spec["cost"], reserve) or not self.start_build(bid, idx, False):
                break

    def assign_research(self) -> None:
        if self.rjob or not self.levels["academy"]:
            return
        acad = self.lvl("academy")
        order = RESEARCH_PRIORITY + [n for n in self.nodes if n not in RESEARCH_PRIORITY]
        for nid in order:
            n = self.nodes[nid]
            cur = self.research.get(nid, 0)
            if cur >= n["max_level"]:
                continue
            lv = n["levels"][cur]
            if lv["academy"] > acad:
                continue
            if any(self.research.get(k, 0) < v for k, v in n["requires"].items()):
                continue
            nxt_cost = d.building_level("city_hall", min(self.ch + 1, d.MAX_LEVEL))["cost"]
            if not self.can_afford(lv["cost"], {r: nxt_cost[r] * 0.5 for r in d.RES}):
                continue
            self.pay(lv["cost"])
            dur = lv["time_s"] / (1 + self.mod("research_speed_pct") / 100)
            self.rjob = [self.t + dur, nid, cur + 1]
            return

    def complete(self) -> None:
        for j in [j for j in self.jobs if j[0] <= self.t]:
            self.jobs.remove(j)
            self.levels[j[1]][j[2]] += 1
            if j[1] == "city_hall":
                lv = self.ch
                self.reached[lv] = j[0]
                if lv <= 10:  # chapter quest reward (08): next level's City Hall cost
                    for r, v in d.building_level("city_hall", lv + 1)["cost"].items():
                        self.res[r] += v
        if self.rjob and self.rjob[0] <= self.t:
            self.research[self.rjob[1]] = self.rjob[2]
            self.rjob = None

    def use_speedups(self) -> None:
        for j in sorted(self.jobs, key=lambda j: j[0]):
            if j[3] and self.build_sp > 0:
                use = min(self.build_sp, j[0] - self.t)
                j[0] -= use
                self.build_sp -= use
        if self.rjob and self.research_sp > 0:
            use = min(self.research_sp, self.rjob[0] - self.t)
            self.rjob[0] -= use
            self.research_sp -= use

    def session(self, start: float) -> None:
        end = start + self.p["session_len"]
        self.t = start
        while True:
            self.collect()
            self.complete()
            self.assign_builders()
            self.assign_research()
            self.use_speedups()
            self.complete()
            self.assign_builders()
            self.assign_research()
            nxt = min([j[0] for j in self.jobs] + ([self.rjob[0]] if self.rjob else []), default=None)
            if nxt is None or nxt > end:
                break
            self.t = max(self.t, nxt)
        if len(self.jobs) < 2 and not any(j[3] for j in self.jobs):
            self.wait_res += 1

    def run(self, days: int = 240) -> dict[int, float]:
        for day in range(days):
            if day > 0:
                self.build_sp += self.p["build_sp"] * 60
                self.research_sp += self.p["research_sp"] * 60
            self.renown_pts += self.p["renown_per_day"]
            for h in self.p["sessions"]:
                self.session(day * d.DAY + h * 3600)
            if self.ch >= d.MAX_LEVEL:
                break
        return self.reached


def main() -> None:
    results = {name: Sim(name) for name in PROFILES}
    for s in results.values():
        s.run()
    md = "--markdown" in sys.argv
    print("| City Hall | Active player (day) | Regular player (day) |")
    print("|---:|---:|---:|")
    for lv in range(2, d.MAX_LEVEL + 1):
        cells = []
        for s in results.values():
            cells.append(f"{s.reached[lv] / d.DAY:.1f}" if lv in s.reached else "-")
        print(f"| {lv} | {cells[0]} | {cells[1]} |")
    if not md:
        for name, s in results.items():
            done = sum(s.research.values())
            total = sum(n["max_level"] for n in s.nodes.values())
            print(f"{name}: sessions blocked on resources={s.wait_res:.0f}, research levels {done}/{total}, "
                  f"renown {renown_level(s.renown_pts)}, academy {s.lvl('academy')}, "
                  f"res={ {k: int(v) for k, v in s.res.items()} }")
            print("  levels:", {k: v for k, v in s.levels.items()})


if __name__ == "__main__":
    main()
