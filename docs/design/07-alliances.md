# 07 — Alliances

Conventions: [00](00-overview.md). Data: [`data/alliance.yaml`](data/alliance.yaml).
Rallies and reinforcement combat rules are in [05 §8–9](05-combat.md); this file
covers the organisation, its economy, its territory, and chat/mail.

## 1. Model

```text
Alliance { id, name, tag, leader_id, created_at, join_mode: open|apply|invite_only,
           min_city_hall, description, announcement,
           members: [Member], funds: u64, research: {tech_id: {level, points}},
           recommended_tech: Option<tech_id>, structures: [id], applications, invites }
Member   { player_id, rank: 1..5, joined_at, donated_today, donated_total, helps_today, helps_total }
Player   { alliance_id?, alliance_credits: u64, left_alliance_at?, donation_charges, donation_charges_at,
           shop_bought_this_week: {item: n}, gifts: [Gift] }
```

Alliance power = Σ member power. Member cap = `50 + 5 × level(al_fellowship)` (max 100).

## 2. Lifecycle

- **Create** (`create_alliance { name, tag, join_mode }`): needs `alliance_hall` level ≥ 1,
  City Hall ≥ 4, 20,000 food + 20,000 wood, no current alliance, not within the
  rejoin cooldown. Name 3–20 characters (letters, digits, spaces; trimmed; unique
  case-insensitively); tag 3–4 letters/digits (unique case-insensitively).
- **Join**: `open` → `join_alliance { alliance_id }` succeeds at once if below the
  cap and City Hall ≥ `min_city_hall`. `apply` → `apply_alliance` creates an
  application (max 5 pending per player, expire after 72 h); rank ≥ 4 answers with
  `answer_application { player_id, accept }`. `invite_only` → only `invite_player`
  (rank ≥ 4; invitations expire after 72 h; `answer_invite`).
  Requires an `alliance_hall`. New members start at rank 1.
- **Leave** (`leave_alliance`): not allowed while taking part in a rally or
  while the city is in battle. Effects: reinforcing armies in both directions and
  structure garrisons are sent home, pending help requests are deleted, caravans
  in flight still deliver, alliance credits are **kept**, alliance modifiers
  are removed, rejoin cooldown 1 h starts. The leader cannot leave while other
  members remain (transfer first).
- **Kick** (`kick_member`): rank ≥ 4, target rank lower than the actor's. Same effects as leaving.
- **Transfer** (`transfer_leadership { player_id }`): leader only; old leader becomes rank 4.
- **Succession**: if the leader has not logged in for 7 days, the daily reset
  promotes the highest-rank member seen in the last 48 h (ties: highest power,
  then earliest `joined_at`); the old leader becomes rank 4.
- **Disband** (`disband_alliance`): leader only; only when the alliance holds no
  Pass/Sanctum. All structures are destroyed, members are removed as if leaving (no cooldown).

### 2.1 Ranks and permissions

Ranks: 1 Recruit, 2 Member, 3 Veteran, 4 Officer (max 8), 5 Leader (exactly 1).

| Action | Minimum rank |
|---|---:|
| Chat, help, donate, shop, join rallies, reinforce, use caravans | 1 |
| Start a rally | 2 |
| Place map markers (§8) | 3 |
| Accept applications, invite, kick lower ranks, set ranks 1–3, mute in alliance chat | 4 |
| Set the recommended tech, edit announcement, send alliance mail, build/remove Banners and Strongholds | 4 |
| Set ranks up to 4, edit name/tag/description/join settings, transfer, disband | 5 |

`set_rank { player_id, rank }`: actor rank must exceed both the target's current and new rank.

## 3. Daily and weekly resets

At 00:00 UTC: `donated_today`, `helps_today`, gift claim counters and caravan
daily totals reset. Monday 00:00 UTC: `shop_bought_this_week` resets.

## 4. Help

- A player in an alliance may send `request_help { kind, id }` once per job for a
  running build (per building), research, healing batch or training batch.
  The request is created with `helps_needed = help_limit`, where
  `help_limit = help_limit(alliance_hall level) + help_limit_flat` (01 §3; 5 + L//2, +0…5 from `al_solidarity`).
- Any other member can help each request once: `help_all {}` helps every open
  request they have not yet helped (the client shows one "Help all" button).
- Each help: `job.completes_at −= max(60, floor(0.01 × job.total_time_s)) × 1000`,
  clamped to `now` (the job then completes on that tick). `total_time_s` is the
  job's sampled duration at start.
- The request closes when `helps_needed` reaches 0, the job ends or is cancelled, or the requester leaves the alliance.
- The helper earns 5 alliance credits per help, at most 200 credits per game day
  (further helps still work, without credits).
- Pushes: `help_requests` (the open list) to all online members on every change.

Example: a 20-hour upgrade with alliance hall level 10 (`help_limit` 10): each help removes
720 s, ten helps remove 2 h (10 %).

## 5. Alliance research

- 14 techs (table below). Each level needs `points_per_level` research points.
  Reaching the threshold levels the tech up **immediately** (no timer); overflow carries over.
  Any number of techs can progress in parallel; members choose where each donation goes.
- **Donation** (`donate { tech_id }`): costs one donation charge and
  `500 × City Hall level` of both food and wood. Gives the tech 100 points, the
  alliance 100 funds, and the donor 50 credits (+10 if it is the officers'
  `recommended_tech`). Charges: cap 15, +1 per hour (lazy regen), so at most 24 + 15 per day.
  A maxed tech cannot receive donations.
- Member modifiers: `level × per-level value`, Account scope (03 §1.2), applied on join, removed on leave.
- Tuning anchor: 30 donors × 20 donations/day = 60,000 points/day ≈ 420,000/week,
  i.e. about one level each of Shared Scaffolds, Shared Archives and Common Fields
  per week plus a little military. The pacing sim (01 §9) assumes exactly that for the three economy techs.

| Tech | Levels | Points / level | Effect per level |
|---|---:|---:|---|
| `al_construction` Shared Scaffolds | 10 | 100,000 | `build_speed_pct` +0.5 |
| `al_scholarship` Shared Archives | 10 | 100,000 | `research_speed_pct` +0.5 |
| `al_harvest` Common Fields | 10 | 100,000 | `gather_speed_pct` +1 |
| `al_drill` Joint Drill | 10 | 120,000 | `train_speed_pct` +1 |
| `al_field_hospitals` Field Hospitals | 10 | 120,000 | `heal_speed_pct` +2 |
| `al_arms` Allied Arms | 10 | 150,000 | `attack_pct` +0.5 |
| `al_bulwark` Allied Bulwark | 10 | 150,000 | `defense_pct` +0.5 |
| `al_vigor` Allied Vigor | 10 | 150,000 | `health_pct` +0.5 |
| `al_logistics` Waystations | 10 | 120,000 | `march_speed_pct` +0.5 |
| `al_war_councils` Grand Councils | 10 | 120,000 | `rally_capacity_pct` +1 |
| `al_solidarity` Solidarity | 5 | 150,000 | `help_limit_flat` +1 |
| `al_fellowship` Fellowship | 10 | 80,000 | member cap +5 |
| `al_banners` Standard Bearers | 10 | 80,000 | Banner limit +5 |
| `al_strongholds` Master Masons | 2 | 400,000 | Stronghold limit +1 |

## 6. Credits, shop and gifts

**Alliance credits** are personal, kept when leaving, never transferable.
Sources: donations (50/60), helps (5, cap 200/day), gifts (below), Warcamp and
structure rewards (08 §5). Expected: active ≈ 1,200/day, regular ≈ 600/day.

**Shop** (`alliance_shop_buy { item, count }`): fixed catalogue in
`alliance.yaml` → `shop`, unlimited stock, per-player weekly limits. Requires
current alliance membership. Highlights: 60-minute speedups 100–150 credits
(10/week each), `sculpture_universal_legendary` 1,200 (5/week),
`sculpture_universal_renowned` 400 (10/week), `teleport_targeted` 1,000 (1/week),
`teleport_territory` 400 (2/week), `shield_8h` 300 (3/week).

**Gifts**: when a rally defeats a Warcamp (06 §6) or the alliance captures a
Pass/Sanctum for the first time (tier 5), every member at that moment receives a
`Gift { id, tier, expires_at = now + 24 h }`. `claim_gift { id }` / `claim_all_gifts`
grant the tier's contents. A player can claim at most **10 gifts per game day**;
unclaimed gifts expire. (The cap keeps speedup income inside the 08 §2 budget.)

| Tier | Credits | Items |
|---:|---:|---|
| 1 | 30 | 1 × `speedup_any_5m` |
| 2 | 50 | 2 × `speedup_any_5m` |
| 3 | 80 | 3 × `speedup_any_5m` |
| 4 | 120 | 1 × `speedup_any_60m` |
| 5 | 200 | 2 × `speedup_any_60m`, 1 × `sculpture_universal_renowned` |

## 7. Territory

### 7.1 Structures

| | Stronghold | Banner |
|---|---:|---:|
| Footprint | 3×3 | 1×1 |
| Territory (square, Chebyshev radius from centre) | 12 (25×25 tiles) | 4 (9×9 tiles) |
| Durability | 600,000 | 60,000 |
| Build time | 4 h | 30 min |
| Cost (alliance funds) | 100,000 | 8,000 |
| Garrison capacity (troops, all members together) | 500,000 | none |
| Limit | 1 + `al_strongholds` (max 3) | 10 + 5 × `al_banners` (max 60) |

### 7.2 Placement and construction

`place_structure { kind, x, y }` (rank ≥ 4):

- Footprint free (06 §3), not inside another alliance's territory, at least 12
  tiles from any Pass, Sanctum-type site or Throne footprint.
- Stronghold: anywhere in a zone the alliance can reach (Outlands always;
  Heartlands/Crown only if the alliance holds a pass of level 2/3).
- Banner: its tile must lie inside own **active** territory or within 1 tile of it
  (so chains grow outward by up to 5 tiles per Banner).
- Funds are deducted at placement. The structure appears at once in state
  `building` with 25 % durability, projects no territory, can be attacked, and
  becomes `active` (full durability) when the timer ends. No speedups or helps.
- `remove_structure { id }` (rank ≥ 4): instant, no refund.

### 7.3 Territory rules

- Territory is a per-tile `alliance_id` grid. A tile belongs to the **earliest
  completed** active structure whose square covers it; later structures never take over a claimed tile.
- **Connectivity**: a Banner is `active` only while it is linked to an active
  Stronghold of its alliance through a chain of active structures, where two
  structures are linked if each one's centre lies within the other's territory
  square expanded by 1 tile. After any structure completes or is destroyed, recompute
  links (BFS from Strongholds) and then the tile grid in completion order.
  Unlinked Banners stay on the map as `inactive` (no territory) and relink automatically.
- Effects inside **own** territory:
  - armies gathering there: `gather_speed_pct +10` (Army scope, sampled on arrival);
  - a city located there: `garrison_defense_pct +5` (Account scope; recomputed on territory change and teleport);
  - `teleport_territory` destination (06 §13); fog always explored (06 §10).
- Effects on **others**: cannot teleport into it, cannot place structures in it.
  They may march, gather and fight there freely.
- Garrisoning a Stronghold: `reinforce` with the Stronghold as target (05 §9
  rules, garrison commander = highest-rank member present, ties earliest
  arrival). Lightly wounded heal on entering (02 §7).

### 7.4 Attack and destruction

- Anyone outside the alliance may attack an enemy Banner or Stronghold (05 §10).
  Attacking removes the attacker's peace shield (06 §12).
- **Banner** at 0 durability: removed. **Stronghold** at 0: removed, garrison
  armies return home, the alliance cannot place a new Stronghold for 12 h, and
  every member is mailed. The attackers' alliance members who dealt durability
  damage share `20,000` alliance credits proportional to damage (rounded down).
- Territory and links are recomputed immediately. Cities left outside territory are unaffected except for losing the bonus.
- An alliance with zero Strongholds keeps its Banners (all inactive).

## 8. War coordination

- Rallies: 05 §8; the War tab (10 §7.5) lists `rally_update` data for all current rallies by and against members.
- **Markers**: rank ≥ 3 may place up to 10 alliance map markers
  (`set_marker { slot: 0..9, x, y, icon: attack|defend|gather|rally, text ≤ 40 }`, `clear_marker { slot }`).
  Markers are visible to members on the map and listed on the War tab.
- Members' cities and armies are shown in alliance colour on the map; `get_map_overview` (06 §14) returns member city positions.
- Reinforcing a member's city: `reinforce` (05 §9); capacity = host's `reinforcement_capacity`.

## 9. Caravans

- Requires a `caravan_post` and that sender and recipient have both been in the
  same alliance for ≥ 24 h.
- `send_caravan { to_player_id, resources }`: `Σ resources ≤ caravan_load(level)`;
  resources are deducted at once; the recipient will receive
  `floor(amount × (1 − caravan_tax_pct/100))` of each (tax 19 % at level 1 down to 4 % at level 25).
  Gold can only be sent to recipients with City Hall ≥ 10, stone to City Hall ≥ 4.
- The caravan is a map object moving at 30 tiles/min on a normal path (06 §11.3);
  it cannot be attacked, uses no march slot and no commander. At most 2 caravans out per player.
- Daily limit: total sent per game day ≤ `5 × caravan_load`.
- On arrival resources are added to the recipient's stockpile, even if the
  recipient has since left the alliance. If no path exists the request fails (`invalid_target`).
- If the recipient's city teleports, the caravan re-paths from its current position.

## 10. Chat and mail

### 10.1 Chat

| Channel | Who | Key |
|---|---|---|
| `kingdom` | everyone with City Hall ≥ 5 | — |
| `alliance` | members | alliance id |
| `private` | two players | ordered pair of player ids |

- `chat_send { channel, to_player_id?, text }`: text 1–300 characters after
  trimming; control characters stripped. Server stores the last 200 messages per channel key.
- `chat_history { channel, to_player_id?, before_id? }` → up to 50 messages.
- Push `chat_message { channel, id, from: {player_id, name, alliance_tag, rank?}, text, sent_at }`.
- A message may contain coordinate links written as `(x,y)`; the client makes them tappable. No other markup.
- `block_player { player_id, blocked }`: blocked players' private and kingdom messages are not delivered to the blocker (max 200 blocks).
- Officers can mute a member in alliance chat for 1 h (`mute_member`). Kingdom-wide moderation and rate limits: 11 §4–5.

### 10.2 Mail

```text
Mail { id, category: system|battle|scout|alliance|player|reward, from?, subject, body, sent_at,
       read: bool, attachments?: Rewards, claimed: bool, report_id? }
```

- Retention: 30 days, and at most 200 per category per player (oldest read mail
  without unclaimed attachments is dropped first; mail with unclaimed attachments is never dropped before 30 days).
- `get_mail { category, before_id? }` → 30 summaries; `read_mail { id }` → full mail;
  `claim_mail { id }` / `claim_all_mail { category }`; `delete_mail { ids }` (not if unclaimed attachments).
- `send_mail { to_player_id, subject ≤ 60, body ≤ 2000 }`: player mail; sender City Hall ≥ 5.
- `send_alliance_mail { subject, body }`: rank ≥ 4, at most 5 per alliance per game day, delivered to all members (category `alliance`).
- Battle and scout reports are mail with `report_id` (05 §11, 06 §10); reports are stored once and shared by reference.
- Push `mail_new { category, id, subject, from? }` and an unread counter per category in `player_update`.

## 11. Protocol

Requests (all with `req`): `create_alliance`, `search_alliances { query?, page }`,
`get_alliance { alliance_id }`, `join_alliance`, `apply_alliance`, `answer_application`,
`invite_player`, `answer_invite`, `leave_alliance`, `kick_member`, `set_rank`,
`transfer_leadership`, `disband_alliance`, `edit_alliance { description?, announcement?, join_mode?, min_city_hall?, name?, tag? }`,
`request_help`, `help_all`, `donate`, `set_recommended_tech { tech_id? }`,
`alliance_shop_buy`, `claim_gift`, `claim_all_gifts`, `place_structure`, `remove_structure`,
`set_marker`, `clear_marker`, `send_caravan`, `mute_member`, and the chat/mail requests of §10.

Pushes: `alliance_update { alliance }` (full `AllianceView`: header, members with
online flag/power/rank, research, funds, structures, markers, recommended tech) to
all online members on any change, throttled to once per second;
`help_requests { requests }`; `gifts_update { gifts }`; `chat_message`; `mail_new`.
Changing name or tag costs 50,000 alliance funds.

System error codes added: `name_taken`, `tag_taken`, `alliance_full`, `rank_too_low`, `already_in_alliance`.

## 12. Edge cases

- Member cap is checked at accept time, not at application time.
- Donations in the same tick that complete a level: overflow points go to the next level; at max level overflow is discarded.
- A help arriving after the job finished is ignored (no credits).
- A job using both speedups and helps: order does not matter, both subtract from `completes_at`.
- Leader deleted/banned: succession runs immediately.
- Alliance dropping below 1 member: disbanded automatically.
- Two structures completing on the same tick: lower structure id counts as earlier.
- A Banner placed next to territory that becomes inactive before the Banner completes: completes as `inactive`.
- Pass/Sanctum held by an alliance that disbands or reaches zero members: reverts to `guarded` with guardians restored.
- Shop purchase when inventory stack would overflow `u32`: rejected with `limit_reached`.
