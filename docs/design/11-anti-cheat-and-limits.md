# 11 — Anti-cheat, validation and limits

Conventions: [00](00-overview.md). Data: [`data/limits.yaml`](data/limits.yaml).
The client is open source; assume every client is modified. Security comes
from the server deciding everything, not from hiding anything.

## 1. Threat model

| Threat | Defence |
|---|---|
| Forged requests (free builds, negative counts, other players' ids) | §2 validation pipeline; every rule in specs 01–09 is enforced in `game-core` |
| Speed/time hacks | the server clock is the only clock (00 §1); clients never send times |
| Map hacks (seeing through fog, hidden troop counts) | the server never sends what the player may not know (06 §10, §14; 01 §3 intel tiers) |
| Replay / duplicate requests | per-request state checks make every request idempotent or rejected; grants keyed by source id (§6) |
| Flooding | §3–4 limits and buckets |
| Bots / automation | §7 heuristics → review; core loops give little to automate (buffers cap at 10 h, stamina caps) |
| Multi-account feeding | §8 |
| Chat abuse | §5 |
| Account theft | §9 |

Out of scope: client integrity checks, obfuscation, anti-debugging (pointless for an open client).

## 2. Validation pipeline

Every client message passes these steps in order; the first failure answers `error` and stops:

1. **Size and parse**: ≤ 16,384 bytes, valid UTF-8 JSON, known `type`, all fields of the right type, no unknown fields ignored silently (unknown fields → `bad_message`). → `bad_message`
2. **Session**: logged in (except `hello`, `login`, `ping`). → `not_logged_in`
3. **Rate limit** (§4). → `rate_limited`
4. **Field ranges** (§3). → `bad_message`
5. **Ownership and existence**: every id in the request resolves to an entity the player owns or may act on. → `not_found` (never reveal whether a foreign id exists: same code for "does not exist" and "not yours")
6. **State and rules**: the `game-core` function for the action is called with `(state, request, now)`; it returns the new state or a typed error. → specific code
7. **Commit**: state change + audit entry in one database transaction; then `ok` and pushes.

Rules for step 6 code:

- All arithmetic on resources, counts and times uses checked operations; overflow → `bad_message`.
- Never use a client-sent quantity as a result ("I collected 500") — only as an intent ("collect building 7").
- Derived values (cost, time, capacity, speed, path) are computed by the server from data + state; the client's copies are for display.
- Float inputs do not exist in the protocol: coordinates and counts are integers.
- A `game-core` function must be total: no panics on any input (fuzz test, §11).

## 3. Field limits

| Field | Limit |
|---|---|
| Any count (troops, items) | 1 … 10,000,000; item `count` ≤ owned |
| Coordinates | 0 … 1199 (world), 0 … 39 (city) |
| `req` | u32; echoed, not interpreted |
| Player name | 3–16 chars: letters, digits, space, `_`, `-`; trimmed; unique case-insensitively; no leading/trailing space; rename cooldown 7 days |
| Alliance name / tag | 07 §2 |
| Chat text | 1–300 chars; mail subject ≤ 60, body ≤ 2,000; marker text ≤ 40; alliance description/announcement ≤ 500 |
| `ArmySpec` | ≤ 20 troop rows, each troop id valid and count ≥ 1, total ≤ capacity (04 §7) |
| `set_talents` | ≤ 27 entries, ranks within node max, total ≤ points, prerequisites satisfied |
| `map_view` | `w, h` ≤ 150 at lod 0, ≤ 400 at lod 1 |
| Lists (`delete_mail.ids` …) | ≤ 100 elements |

Text is stored as sent after stripping control characters (U+0000–U+001F, U+007F, bidi overrides U+202A–U+202E, U+2066–U+2069) and collapsing runs of whitespace. The client must render text as plain text (BBCode disabled on labels showing user text).

## 4. Rate limits

Token buckets per player (`burst` capacity, refill per minute), each request costs one token of its class:

| Class | Requests | Burst | Per minute |
|---|---|---:|---:|
| `read` | `get_*`, `search_*`, `chat_history`, `read_mail` | 30 | 120 |
| `action` (default) | city, troops, research, commanders, items, quests, alliance admin | 20 | 60 |
| `march` | `march`, `order_army`, `recall_army`, `scout*`, `reinforce`, rally requests | 10 | 30 |
| `map_view` | `map_view` | 20 | 240 |
| `collect` | `collect_resources` | 20 | 60 |
| `help` | `help_all`, `request_help` | 5 | 20 |
| `donate` | `donate` | 15 | 60 |
| `chat` | `chat_send` | 5 | 12 |
| `mail` | `send_mail`, `send_alliance_mail` | 3 | 6 |
| `report` | `report_player` | 3 | 1 |

Connection level: at most 30 messages per second (exceeding closes the socket),
8 connections per IP, 10 login attempts per IP per minute, idle timeout 90 s
(the client pings every 30 s). 20 `rate_limited` answers within 60 s close the
connection. One session per character: a new login closes the old session.

Gameplay limits that double as anti-abuse (defined in their specs): donation
charges, help credits cap, gift claim cap, caravan daily limit and tax, shop
weekly limits, stamina, scout count, march slots, application/invite caps, alliance mail per day.

## 5. Chat moderation and reports

- Kingdom chat needs City Hall ≥ 5 (throwaway accounts cannot spam it). Identical text in the same channel within 30 s is rejected (`cooldown`).
- `report_player { player_id, reason: spam|abuse|cheating|name, message_id? }` stores the report with the reported message text. Five distinct reporters within 10 minutes against kingdom-chat messages of one player → automatic 1 h kingdom-chat mute pending review; reports are deduplicated per reporter per day.
- **Moderators** (account flag set by the operator in the database/CLI): commands via admin requests `mod_mute { player_id, duration_s ∈ 3600|86400|604800 }`, `mod_rename` (forces a neutral name `Player<id>`), `mod_ban` (§9), `mod_reports` (list). Every moderator action is audited.
- No automated word filter on the server (unreliable across languages); the client offers an optional local filter list and the block list (07 §10.1).
- Operators self-host: `docs/` must ship a short moderation guide with the admin CLI (roadmap P6).

## 6. Audit log

Append-only table `audit(id, at, player_id, kind, source, delta_json)`; one row per committed state change that grants or removes value:

- resources (delta per type with reason: build, train, research, heal, loot, gather, caravan, item, reward, refund),
- items (grant/use with source id), sculptures, credits, medals,
- troops created/lost/healed (per battle id), commander XP,
- alliance membership changes, structure placement/removal, title grants, sanctions.

Every `grant()` (08 §1) carries a **source key** (`chapter:3`, `daily:2026-10-03:chest:4`, `event:hunt:1790812800:1`, `gift:<id>`, `mail:<id>`); a unique index on `(player_id, source)` makes rewards exactly-once even if a request is replayed or the server restarts mid-commit. Retention 90 days, then aggregated per day.

An offline checker (`tools/audit_check`, Phase 5) replays a player's audit rows and asserts the final balances equal the stored state; any mismatch is a bug or an exploit.

## 7. Automation heuristics

Computed by a background job every hour from the audit log and request timestamps; each produces a **flag** for review, never an automatic sanction:

| Signal | Flag when |
|---|---|
| Uninterrupted activity | actions with no 30-minute gap for ≥ 20 h |
| Metronome timing | coefficient of variation of intervals < 0.05 over ≥ 200 repeated same-type actions (gather sends, barbarian attacks, help_all) |
| Inhuman reaction | median delay between a push (army returned, node spawned in view) and the dependent request < 150 ms over ≥ 100 samples |
| Unknown message shapes | any `bad_message` after login (official clients never produce one) — counts per day |
| Sniping | repeated gather marches to nodes within 2 s of their spawn outside the player's current `map_view` |

Design-side dampers make botting low-value: production buffers stop at 10 h,
stamina caps PvE, gathering is limited by march slots, daily objectives cap at
100 activity, and nothing rewards being online 24 h.

## 8. Multi-account feeding

- Caravans: tax 4–19 %, daily cap, 24 h same-alliance requirement, both ends audited (07 §9).
- Flag: an account that over 7 days receives ≥ 10× what it sends from ≥ 5 distinct senders; ≥ 4 characters in one kingdom logging in from one IP **and** sending caravans or reinforcements to a common recipient.
- "Farm" cities being attacked by their owner's main: loot is already limited by storehouse protection and load (01 §7); the flag is repeated zero-defence attacks between the same pair (≥ 10 per week) from a shared IP.
- Shared IP alone is never sanctioned (families, schools).

## 9. Accounts, sessions, sanctions

- Passwords: Argon2id (memory 19 MiB, 2 iterations, 1 lane), per-user salt; minimum length 8; never logged. Session token: 256-bit random, stored hashed, expires after 30 days idle. From Phase 5 the gateway issues tickets (09 §2).
- Transport: `wss://` in production (TLS terminated by the reverse proxy); the server refuses non-loopback plain `ws://` unless started with `--insecure`.
- Sanction ladder (manual, by a moderator, with a mailed reason): warning → chat mute (1 h / 24 h / 7 d) → temporary ban (1 / 7 / 30 days: character cannot log in, city gets a shield for the duration and its armies return) → permanent ban (city removed from the map, excluded from leaderboards) → rollback of specific grants via audit rows for exploit abuse.
- Appeals: operator contact shown on the ban screen (configured per server).

## 10. Server robustness

- **Tick budget**: the 1 s tick processes timers, marches, battles, spawns. Target ≤ 200 ms at 8,000 accounts / 5,000 moving armies / 500 battles; measure with a metrics histogram; if a tick overruns, the next starts immediately and the overrun is logged (no skipped ticks).
- **Ordering**: within a tick requests are applied in arrival order, then world systems in the fixed order timers → marches → battles (05 §2) → spawns → pushes.
- **Persistence**: write-behind per player every 30 s and on logout; value-granting commits (§6) are synchronous. Crash recovery replays nothing: timers are absolute timestamps, armies store path + departure time, battles store full state each tick in memory and every 10 ticks to disk (a crash rewinds a battle at most 10 s).
- **Lazy evaluation**: production, stamina, donation charges and healing are computed from timestamps on access, so offline players cost nothing per tick.

## 11. Tests required

- Property tests (`proptest`) per `game-core` action: random valid/invalid requests never panic, never make a resource negative, never create value without an audit delta.
- A fuzz target feeding arbitrary bytes to the message parser.
- Integration tests in `kingdom-server/tests/`: each rate-limit class, duplicate login, replayed `claim_*` requests (second gets `not_allowed`), foreign-id probing returns `not_found`, fog: a second client never receives objects in unexplored cells.
- Load test binary (`tools/loadbot`, Phase 5): N scripted clients performing the daily loop; asserts tick p99 < 200 ms.

## 12. Edge cases

- Rate-limit refill uses the server monotonic clock, lazily on each request.
- A request that fails validation still consumes its token (prevents free probing).
- `ok` lost in transit: the client re-syncs from the next `*_update` push; resending the same action is safe because step 6 re-checks state (e.g. a second `upgrade_building` finds the building already upgrading → `queue_full`/`requirements_not_met`).
- Clock moving backwards on the host: the server uses `max(last_now, wall_now)` for game time.
