# 09 — Kingdom lifecycle, titles, migration, seasons

Conventions: [00](00-overview.md). Data: [`data/seasons.yaml`](data/seasons.yaml).
World rules: [06](06-world-map.md). This is Phase 5 content; everything before
§5 can ship with a single kingdom.

## 1. Kingdom lifecycle

A kingdom is one `kingdom-server` process with its own database, map seed and
**epoch** (creation time). `kingdom_day = floor((now − epoch) / 86,400,000)`.

| Kingdom day | What happens |
|---:|---|
| 0 | Opens. New accounts spawn in the Outlands (06 §13). 72 h new-player shields. |
| 3 | Level-1 passes open (06 §8) |
| 7 | Shrines open (06 §9) |
| 14 | Level-2 passes open |
| 21 | Sanctums open |
| 28 | Level-3 passes open |
| 30 | Registration closes (earlier if 8,000 accounts exist); the gateway sends new players to the newest open kingdom |
| 35 | Great Sanctums open |
| 49 | The Throne opens |
| 60 | Kingdom accepts migrants (§4) |
| 84 | Eligible for the Convergence (§5) |

Cities of accounts with City Hall ≤ 5 that have not logged in for 30 days are
removed from the map (the account and city data are kept; on next login the
city is placed with the spawn rule).

## 2. Accounts, gateway and kingdoms

- One account can own **one character per kingdom**. Characters are independent.
- A stateless **gateway** service (new crate `gateway`, Phase 5) owns accounts
  and the kingdom directory: `list_kingdoms` → `[{id, name, day, open, population, ws_url}]`,
  issues a signed session ticket `{account_id, kingdom_id, expires_at}` (HMAC-SHA256
  with a secret shared with kingdom servers; valid 60 s), which the client presents
  in `login` to the kingdom server. Until Phase 5 the kingdom server keeps its own login (current behaviour).
- **Transfer** primitive (used by migration and seasons): the source server
  locks the character, serialises `PlayerRecord` (city, troops, commanders,
  inventory, research, quests, Renown, counters; **not** map position, alliance
  membership, mail or reports), sends it to the gateway; the target server
  imports it and places the city; the source marks the character `moved`.
  The operation is idempotent by `(account_id, transfer_id)`.

## 3. Titles

The alliance that holds the Throne (06 §9) is the **ruling alliance**; its
leader is the **Sovereign**. The Sovereign can grant five titles, each to one
player of the kingdom (any alliance):

| Title | Modifiers (Account scope) |
|---|---|
| Sovereign (automatic) | `attack_pct +3`, `defense_pct +3` |
| Marshal | `attack_pct +5` |
| Warden | `defense_pct +5` |
| Architect | `build_speed_pct +5` |
| Sage | `research_speed_pct +5` |
| Quartermaster | `gather_speed_pct +10`, `train_speed_pct +5` |

- `grant_title { title, player_id }`; each title can be reassigned at most once per hour.
  A player holds at most one title; granting a second replaces the first.
- Titles are cleared when the Throne changes hands or the ruling alliance changes leader.
- There are **no negative titles** (deliberate: no tool for harassment).
- Build/research timers sample modifiers at start (03 §1.3), so "title hopping" only helps timers started while holding the title.

## 4. Migration

A character can move to another kingdom with `migrate { kingdom_id }` (sent to the gateway through the current kingdom server):

- Target kingdom day ≥ 60 and not currently in a Convergence season; source likewise not in a season.
- Character: in no alliance, all armies home, no active timers in battle state, not under attack, 30 days since last migration.
- Cost: `1 + floor(power / 5,000,000)` × `migration_writ` (season medal shop, §6; also 1 granted by mail when a character first reaches City Hall 16).
- Carried resources are capped at 5M food, 5M wood, 4M stone, 2M gold (excess is left behind and lost; the client warns). Items, troops, commanders and research move in full.
- The city is placed with the spawn rule (06 §13) and receives an 8 h shield.
- If the target already has a character for this account → `not_allowed`.

## 5. Seasons — the Convergence

A season is a 56-day war between up to 8 kingdoms on a separate **season map**,
followed by 14 days of rest (70-day cycle).

### 5.1 Matchmaking

- At a global cycle boundary (gateway, every 70 days), all kingdoms with day ≥ 84 are eligible.
- Sort eligible kingdoms by `Σ power of their 300 strongest characters`, descending;
  cut into consecutive groups of 8. A last group smaller than 8 is kept if it has ≥ 2
  kingdoms; a single leftover kingdom joins the previous group (9).
- Each group gets a season server (`kingdom-server --mode season`) with seed
  `splitmix64(season_number ^ group_index)`.

### 5.2 Season map

Generated with the 06 §2 algorithm and these overrides: **8 sectors** (spokes
at 22.5° + 45°k, eight level-2 passes at 45°k, 16 Shrines), no province names.
Each kingdom (a **faction**) is assigned one Outlands sector, in sort order.

### 5.3 Entering and leaving

- Registration opens 3 days before the start. `enter_season {}` (City Hall ≥ 16):
  uses the Transfer primitive to the season server; the city is placed in the
  faction's sector by the spawn rule. Alliance membership is mirrored: the
  season server creates a shadow alliance with the same id/name/tag/ranks on first
  entry, and its research levels are copied once at season start. Alliance structures start from nothing.
- `leave_season {}`: armies home, not in battle → transfer back; the city is
  placed in the home kingdom with `teleport_territory` semantics if the alliance
  has territory there, else the spawn rule. Re-entry allowed after 24 h.
- At season end every character is transferred home automatically.
- The home kingdom keeps running; characters who stay home play normally.

### 5.4 Rules on the season map

- All characters of one faction are **allied**: they cannot attack each other and may reinforce each other. Alliances remain the unit for structures, rallies, helps and chat; a `faction` chat channel is added.
- Phases (season day): 1–14 **Muster** (all passes sealed; PvE and growth inside the home sector); 15–28 **Borders** (level-1 passes and Shrines open); 29–42 **Heartlands** (level-2 passes, Sanctums); 43–56 **Crown** (level-3 passes, Great Sanctums, Throne).
- Passes, sites, territory, combat, scouting: exactly as 05–07, with "alliance holds" semantics; passage through a held pass is granted to the **whole faction** of the holder.
- Site buffs (06 §9) apply to the whole holding faction, only on the season map ("season buffs" in 03 §1.2).
- **Losses**: in battles between players on the season map, 50 % of severely wounded die outright before hospital capacity is applied (02 §7).
- Peace shield items cannot be used on the season map outside the faction's home sector.

### 5.5 Scoring

```text
faction_points  += per_hour[site kind]   for every site held by one of the faction's alliances, added each full hour
                   (pass L1 10, L2 30, L3 60, Shrine 20, Sanctum 60, Great Sanctum 150, Throne 500)
faction_points  += kill_points gained by members × 0.0001
contribution(p)  = 0.01 × kill_points + 0.01 × durability damage dealt + 50 × Σ levels of barbarians defeated
                   + 0.0001 × load units gathered            (all on the season map, this season)
```

The faction ranking is final at the end of day 56 (ties: higher total kill points).

## 6. Season medals and rewards

**Season medals** are a personal currency (kept across seasons, not transferable).

- Personal thresholds on `contribution`: 1,000 → 50 medals; 5,000 → 100; 20,000 → 200; 60,000 → 400; 150,000 → 800 (cumulative 1,550).
- At season end the sum earned is multiplied by the faction rank multiplier:
  1st ×2.0, 2nd ×1.6, 3rd ×1.4, 4th ×1.2, others ×1.0 (rounded down), mailed as a reward.
- The winning faction's characters get a cosmetic profile frame for the next season; the top 3 alliances by contribution get a cosmetic banner pattern.
- **Medal shop** (`medal_shop_buy`), limits per season: legendary sculpture 100 (×20), renowned sculpture 40 (×20), `migration_writ` 150 (×10), `teleport_targeted` 100 (×3), `shield_24h` 80 (×3), `xp_tome_50k` 50 (×20), 3 h train/heal speedups 30 (×20 each), `cosmetic_season_banner` 300 (×1).
  Nothing in the shop speeds up building or research, so City Hall pacing (01 §9) is unaffected.

## 7. Protocol

Gateway (HTTPS JSON): `POST /account/register`, `POST /account/login`, `GET /kingdoms`, `POST /ticket { kingdom_id }`.
Kingdom server requests: `get_kingdom_info` → `ok { day, phase?, ruling_alliance?, titles[], season? }`,
`grant_title`, `migrate`, `enter_season`, `leave_season`, `get_season` → `ok { factions[], phase, my_contribution, medals }`,
`claim_season_threshold { index }`, `medal_shop_buy { item, count }`.
Pushes: `kingdom_update` (titles, ruling alliance, day rollover), `season_update` (faction scores hourly, phase changes).
Error code added: `transfer_in_progress`.

## 8. Edge cases

- Transfer fails midway (target unreachable): the source keeps the lock for 120 s, then unlocks and reports `error`; the gateway deduplicates by `transfer_id` if the target did import.
- Player in a rally or with armies out sends `enter_season`: rejected (`requirements_not_met`).
- Season ends during a battle: battles are resolved as a retreat for all sides on the final tick; then transfers run.
- A kingdom eliminated from every site still scores through kill points.
- A character created after its kingdom's group was formed may still enter the season (City Hall ≥ 16).
- Throne holder alliance disbands: titles cleared, Throne reverts to `guarded` (07 §12).
- Migrating player's pending mail attachments are claimed automatically before transfer; unclaimed gifts are lost (client warns).
