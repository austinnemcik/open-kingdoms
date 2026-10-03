# 10 — UI / UX flows

Conventions: [00](00-overview.md). Every screen lists **what it shows**, **what
the player can do** (and the message sent), and **states to handle**. Layouts
are our own; do not imitate another game's screens. Message payloads are
defined in the spec named in the catalogue (§A).

## 1. Principles

1. **Server truth.** The client renders `*_update` pushes. After sending a
   request it disables the triggering control until `ok`/`error` arrives
   (timeout 10 s → toast "No answer from server", control re-enabled).
2. **Timers** are drawn from `completes_at − (local_now + clock_offset)`, where
   `clock_offset` comes from `server_time` on every push (smoothed: keep the minimum latency sample of the last 10).
3. **No dark patterns**: no pop-up offers, no red-dot spam. A badge appears only for: claimable rewards, unread mail, open help requests, incoming attacks, idle builder/academy.
4. **Reference resolution** 1280×720 landscape, UI scales with `canvas_items` stretch, minimum touch target 48 px. Works with mouse + keyboard and with touch (tap, drag, pinch).
5. **Reading order**: one primary action per panel, bottom-right, accent colour; destructive actions need a confirm dialog.
6. Numbers: thousands separators; ≥ 1,000,000 shown as `1.25M`, ≥ 10,000 as `12.5K` in compact places (HUD); full numbers in tooltips. Durations `2d 03:15:20` / `03:15:20` / `15:20`.
7. All text goes through `tr()` with keys in `client/locale/en.csv`. Data ids map to keys `<file>.<id>.name` / `.desc`.
8. Colours: resources food `#D9A441`, wood `#8A5A2B`, stone `#9AA3AD`, gold `#F2C94C`; troop types infantry blue, cavalry red, archer green, siege grey; rarity veteran green, renowned blue, legendary amber. Counter arrows use the troop colours.

## 2. App shell

| Scene | File | Purpose |
|---|---|---|
| Boot / login | `scenes/login.tscn` (exists) | server URL, name, connect; later kingdom list (09 §2) |
| City | `scenes/city.tscn` (exists) | 3D city, HUD |
| World | `scenes/world.tscn` | 3D world map, same HUD |
| Panels | `scenes/ui/panels/*.tscn`, script per panel extending `PanelBase` | pushed on a `PanelStack` autoload; Esc / back gesture pops |

- **HUD** (shared by City and World): top bar = player badge (name, power, Renown level; opens Profile §9.3), four resource counters (tap → Storehouse breakdown), stamina meter on the world map; left edge = **queue cards** (builders ×2, research, each training building, hospital, each army) showing name + countdown, tap → jumps to the thing; bottom-right dock = City/World toggle, Commanders, Alliance, Quests, Inventory, Mail, More (Events, Leaderboards, Settings); bottom-left = chat ticker (last line, tap → Chat §8).
- **Login flow**: connect → `hello` → `welcome` (check protocol version; mismatch → "Update required" screen) → `login` → `logged_in` → `game_data` → `city_state` → City scene. First login: starter commander choice (§4.1) after the first tutorial step.
- **Reconnect**: on socket close show a non-blocking banner "Reconnecting…" with exponential backoff 1, 2, 4, 8, 15 s (cap 15); on success re-`login` and re-request `get_city`, `map_view` if on the world scene. Panels stay open and refresh.
- **Errors**: `error.code` maps to `tr("error." + code)`; shown as a toast; `insufficient_resources` instead opens the "missing resources" sheet (what is missing, buttons: use resource items, go gather).

## 3. City

### 3.1 City view

- Shows: buildings on the 40×40 grid (models by kind/level band 1–9, 10–16, 17–25), construction scaffolding with a floating countdown, collect bubbles over production buildings when the buffer ≥ 5 % of capacity, "help" hand icon over jobs that can request help, wounded icon over the hospital.
- Tap ground: nothing. Drag: pan. Pinch/wheel: zoom. Tap bubble → `collect_resources { building_id }` (a floating "+1,234" rises). Tap building → §3.2.
- Empty-plot build: the **Build** button in the dock (visible in City) → §3.3.

### 3.2 Building ring

Tapping a building shows a ring of 2–5 buttons around it and a name plate ("Farm · Level 7"):
`Info` (stats table: this level vs next), `Upgrade` (§3.4), the building's function (`Train`, `Research`, `Heal`, `Commanders`, `Scout`, `Alliance`, `Caravan`), `Move` (ghost follows pointer, green/red footprint, confirm → `move_building`), and while upgrading: `Speed up` (§3.8), `Help` (`request_help`), `Cancel` (confirm with the 50 % refund amount → `cancel_build`), `Free` when the remaining time ≤ free-finish threshold (→ `finish_build_free`).

### 3.3 Build menu

- Shows: tabs Economy / Military / Other; a card per building kind: icon, name, count `built/max`, cost, time, lock reason ("Needs City Hall 5").
- Action: choose card → placement mode (ghost, valid tiles highlighted) → confirm → `build_building { kind, x, y }`.
- States: no free builder → card button reads "Builders busy" and opens the queue card; insufficient resources → missing-resources sheet.

### 3.4 Upgrade panel

- Shows: current → next level stat rows (every stat in `levels[]`, changed values highlighted), cost per resource (red when lacking), time after modifiers, requirement rows with ✔/✖ and a "Go" button that focuses the required building, power gain.
- Actions: `Upgrade` → `upgrade_building`. Max level → panel shows "Maximum level".

### 3.5 Training panel (barracks, archery range, stable, siege workshop)

- Shows: tier tabs T1–T5 (locked tiers show the requirement: building level and research node), unit portrait, stats (attack/defense/health/speed/load/power/upkeep), slider + number field up to `batch_cap`, total cost and time (live), owned count.
- Actions: `Train` → `train_troops`; `Promote` toggle (choose a lower tier owned → `promote_troops`, shows cost/time difference); during training: progress, `Speed up`, `Help`, `Cancel` → `cancel_training`. `Dismiss` lives under Info (confirm dialog; `dismiss_troops`).

### 3.6 Hospital panel

- Shows: capacity bar (used/total across all hospitals), rows of wounded by troop with sliders (default: all, greedy by highest tier if resources are short), total cost and time.
- Actions: `Heal` → `heal_troops`; while healing: `Speed up`, `Help`, `Cancel` → `cancel_healing`.
- State: over capacity warning text before battles is shown on the march composer (§5.3), not here.

### 3.7 Research panel (academy)

- Shows: two tabs (Economy, Military); a scrollable node graph (columns by academy level requirement, edges = prerequisites); node chip = icon, `level/max`, state (locked / available / in progress / maxed). Selecting a node opens a side sheet: effect now → next, cost, time, requirements with ✔/✖.
- Actions: `Research` → `start_research`; when running: `Speed up`, `Help`, `Cancel` → `cancel_research`, `Free` → `finish_research_free`.

### 3.8 Speedup picker

- Shows: remaining time, list of usable items for this timer kind (specific first, then universal) with owned counts and a stepper each; "Auto-fill" picks the fewest items that finish the timer wasting the least time (largest first, then one smaller to cover the rest).
- Action: `Use` → one `use_speedup { target, item_id, count }` per item type. Warn when a use would waste more than 5 minutes.

### 3.9 Bonuses panel

Opened from the player badge. Sends `get_modifier_breakdown`. Shows every
non-zero modifier key grouped as Economy / Military / March, with its total and
an expandable list of sources (Research, Buildings, Alliance research,
Territory & Sanctums, Renown, Title, Items, Season). Keys are labelled via
`modifier.<key>.name`. Clamped values (03 §1.5) show "(max)".

### 3.10 Inventory

- Tabs: Speedups, Resources, Commanders, Map, Buffs. Item card: icon, name, count. Selecting shows the description and a `Use` button with a count stepper where allowed (`use_item`; shields → `use_shield`; teleports switch to the world map in placement mode → `teleport`; tomes open the commander picker → `use_xp_item`).
- Active buffs are listed at the top of the Buffs tab with remaining time.

### 3.11 Quests and Renown

- Tabs: **Chapter** (objectives with progress and `Claim` → `claim_objective`; chapter reward and `claim_chapter`), **Daily** (activity bar 0–100 with five chest markers → `claim_daily_chest`; task list with progress and a "Go" shortcut per task), **Renown** (level, points to next, current bonuses, next level's bonuses and rewards).
- Data: `get_quests` on open, then `quest_update` pushes.

## 4. Commanders

### 4.1 Starter choice

Full-screen, three cards (portrait, name, troop focus, skill 1 summary). `Choose` → confirm → `choose_starter`. Cannot be dismissed.

### 4.2 Roster

Grid sorted: owned first (rarity, level), then locked. Card: portrait, level, stars, sculpture progress bar toward the next unlock/star. Header: universal sculpture counts and the Hall of Heroes daily claim button (opens picker → `claim_daily_sculptures`). Data: `get_commanders`, `commander_update`.

### 4.3 Commander detail

- **Overview**: level/XP bar (`Use tomes` → `use_xp_item`), stars (`Star up` when at cap with enough sculptures → `star_up`; `Convert` universal → `convert_sculptures`), power, role tags.
- **Skills**: four skills with level, text generated from data (`{potency}` etc. filled from the level's numbers), `Upgrade` → `upgrade_skill` showing sculpture cost. Locked skills show the star needed.
- **Talents**: three tree tabs, nodes with rank pips, points left; edits are local until `Save` → `set_talents`; `Reset` (free if available, else shows when it becomes free).
- Locked commander: `Unlock` (10 sculptures) → `unlock_commander`.

## 5. World map

### 5.1 Map view

- Shows: terrain chunks (`map_chunk`), fog as cloud cover over unexplored cells, objects (`map_objects`/updates) with level plates, alliance territory tint + border, armies as banners moving along paths with a line to the destination (own: solid, allied: blue, hostile toward me: red pulsing), battle markers.
- Camera move/zoom → `map_view { x, y, w, h, lod }`, debounced 150 ms; LOD thresholds per 06 §14. Coordinates readout and a "go to (x, y)" field. `Home` button recentres on own city.
- Zoomed fully out switches to §5.6.

### 5.2 Object pop-ups (tap an object)

| Object | Shows | Actions |
|---|---|---|
| Own city | name, power, shield | Enter city; Garrison commanders (`set_garrison_commanders`); Shield / Teleport (inventory) |
| Other city | owner, alliance, power, kills, shield state | Scout (`scout`), Attack, Rally (`start_rally`), Reinforce (ally), Caravan (ally), Mail, Profile |
| Node | resource, level, remaining, occupant | Gather (`march kind: gather`); Attack occupant if hostile |
| Barbarian | level, troop estimate, recommended power, rewards, stamina cost | Attack (disabled with reason if level too high or stamina short) |
| Warcamp | level, troops, rewards | Rally |
| Pass / Sanctum / Throne | state (sealed with opening countdown / guarded / held by), durability, buff, garrison size (allies only) | Attack, Rally, Reinforce (if held by own alliance), Scout |
| Banner / Stronghold | alliance, durability, state | Attack / Rally (hostile); Reinforce, Remove (own, rank ≥ 4) |
| Army | owner, alliance, commander portraits, troop estimate (own: exact) | own: Recall (`recall_army`), Redirect (`order_army`); hostile: Attack, Scout |
| Empty tile | coordinates, zone, territory owner | Move army here; Teleport here; Place structure (rank ≥ 4); Set marker (rank ≥ 3) |

### 5.3 March composer

- Opens from any Attack/Gather/Reinforce/Rally/Join action. Shows: target summary, primary + secondary commander pickers (secondary locked until primary ★3), troop rows with sliders (healthy in city), `Max` (fills by highest tier up to capacity), capacity `used/max`, army power, load, travel time and arrival clock, stamina cost, free march slots, saved presets (5 local presets).
- Warnings: counter matchup hint versus scouted target; "hospital would overflow" if `army size × 40 %` exceeds free hospital capacity; "this will remove your peace shield" (confirm).
- Action: `March` → `march` / `reinforce` / `start_rally` (with preparation time choice) / `join_rally`.

### 5.4 Army list

Queue cards for each army: state, destination, countdown / gathered amount, troop health bar; tap → focus on map; buttons Recall / Redirect.

### 5.5 Battle overlay

When an own army (or a watched one) is engaged: two opposing bars over the armies (healthy share), rage ring on the primary portrait, floating damage numbers per tick from `battle_update.last_tick`, skill name flash when `skill_id` is set. Ends with a summary toast linking to the report.

### 5.6 Kingdom overview (LOD 2)

Static map from `get_map_overview`: zones, mountain rings, passes and sites with holder colours, territory, own/alliance cities, markers. Tap → fly to location.

### 5.7 Search

`search_map`: pick node type + level or barbarian level → camera flies to the result and opens its pop-up; `not_found` → "None in explored land".

## 6. Mail and reports

- Tabs by category (System, Battle, Scout, Alliance, Player, Rewards) with unread counts. List rows: icon, subject, time, attachment icon. `Claim all` per tab.
- **Battle report** view (05 §11): header (result, place, time), both sides' commanders, troop table (start / healthy / lightly / severely wounded / dead / kills) per troop id, loot, rewards, XP, a timeline strip (damage per 10 ticks, skill casts as pins), "Share to alliance chat" (posts a link `report:<id>`).
- **Scout report** view (06 §10.2): fields present per accuracy; "Attack" shortcut.

## 7. Alliance

### 7.1 No alliance

Search list (`search_alliances`): name, tag, members, power, join mode; `Join` / `Apply`; invitations list; `Create` form (name, tag, join mode; shows cost).

### 7.2 Home tab

Banner, name, tag, leader, power, members `n/cap`, announcement, your credits, buttons: Help all (badge with open count → `help_all`), Donate shortcut, Gifts (badge).

### 7.3 Members tab

Grouped by rank; row: name, power, online dot / last seen, donated this week. Row menu by permission: Promote/Demote (`set_rank`), Kick, Mail, Transfer leadership. Applications sub-tab for rank ≥ 4.

### 7.4 Research tab

Tech cards: level, progress bar `points/points_per_level`, effect, "Recommended" star; `Donate` (`donate`) with charges `n/15` and next-charge countdown, cost shown; hold to repeat.

### 7.5 War tab

- **Rallies**: one card per `rally_update` — leader, target (tap → map), countdown to launch, `joined/capacity` troops, participant list; `Join` → march composer; leader sees `Cancel`.
- **Incoming**: attacks/rallies against members that the member's watchtower reveals (`incoming_update` relayed for allies who opted to share, default on).
- **Markers**: the ten marker slots with jump/clear.
- **Structures**: Strongholds/Banners with durability and "under attack" flags.

### 7.6 Shop and gifts

Shop grid with price, weekly limit `bought/limit`, `Buy` (`alliance_shop_buy`). Gifts list with tier, expiry, `Claim` / `Claim all`, daily counter `n/10`.

### 7.7 Territory placement

From the map empty-tile pop-up: choose Banner/Stronghold → ghost with territory square preview and validity reasons → `place_structure`.

## 8. Chat

Channels as tabs (Kingdom, Alliance, private conversations list; Faction during seasons). Message row: tag + name, text, time; tap name → profile; coordinates and report links are tappable. Input 300 chars with counter. `chat_history` on open and on scroll-up. Block/mute from the name menu.

## 9. Other screens

### 9.1 Events

Cards for running and upcoming events (`get_events`): name, time left, points, three threshold markers with `Claim`, bracket leaderboard link.

### 9.2 Leaderboards

Board selector, 50 rows per page, own row pinned (`get_leaderboard`).

### 9.3 Profile

Own or other player: name, alliance, power breakdown (buildings, research, troops, commanders), kill points, milestones/badges, title; own: rename (once free, then 7-day cooldown), settings link. Other: Mail, Block, Invite.

### 9.4 Kingdom and season

Kingdom info (day, upcoming openings, ruling alliance, titles; Sovereign sees `grant_title` controls). Season screen (09 §5–6): phase, faction table, own contribution with thresholds, medal shop, Enter/Leave.

### 9.5 Settings

Graphics quality (3 levels), sound/music volumes, language, notifications toggles, account (log out), credits/licence page.

## 10. Notifications

| Trigger | UI |
|---|---|
| Timer done (build, research, training, healing) | toast + queue card flashes |
| Incoming attack/rally on own city | persistent red banner with countdown, tap → map; alarm sound once |
| Scouted | toast → mail |
| Battle finished | toast → report |
| Rally started by ally | toast → War tab |
| Rewards granted (`rewards_granted`) | reward strip listing items (auto-hides after 4 s) |
| Renown level up | modal with new bonuses |
| Shield about to expire (≤ 10 min) | toast |

Desktop/mobile OS push notifications are out of scope until Phase 6.

## 11. Client architecture notes

- `GameState` autoload holds the last `CityView`, commanders, inventory, alliance view, quests, map cache; emits one signal per entity kind. Panels subscribe; no panel talks to `Net` for pushes directly.
- `Net.request(msg) -> Signal` assigns `req`, returns a one-shot awaited result `{ok, payload | error}`.
- `GameData` autoload stores `game_data` and offers typed lookups (`building_level(kind, level)` …) plus the shared formula helpers mirrored from `game-core` (display only).
- Tests: each panel has a headless unit test feeding fixture JSON into `GameState` and asserting node text/states; `screenshot.gd` gains a `--panel <name> <fixture>` mode for visual checks.

## A. Protocol message catalogue

Client → server requests (every one carries `req` and gets `ok`/`error`):

| Area | Messages | Spec |
|---|---|---|
| Session | `hello`, `login`, `ping` (existing), `get_kingdom_info` | protocol crate, 09 §7 |
| City | `get_city`, `build_building`, `upgrade_building`, `cancel_build`, `finish_build_free`, `move_building`, `collect_resources`, `use_speedup` | 01 §10 |
| Troops | `train_troops`, `promote_troops`, `cancel_training`, `dismiss_troops`, `heal_troops`, `cancel_healing` | 02 §8 |
| Research | `start_research`, `cancel_research`, `finish_research_free`, `get_modifier_breakdown` | 03 §5 |
| Commanders | `get_commanders`, `choose_starter`, `unlock_commander`, `convert_sculptures`, `claim_daily_sculptures`, `star_up`, `upgrade_skill`, `set_talents`, `use_xp_item` | 04 §8 |
| Combat | `set_garrison_commanders`, `start_rally`, `join_rally`, `cancel_rally`, `reinforce`, `get_battle_report` | 05 §14 |
| Map | `map_view`, `get_map_overview`, `march`, `order_army`, `recall_army`, `scout`, `scout_explore`, `teleport`, `use_shield`, `search_map` | 06 §14 |
| Alliance | `create_alliance`, `search_alliances`, `get_alliance`, `join_alliance`, `apply_alliance`, `answer_application`, `invite_player`, `answer_invite`, `leave_alliance`, `kick_member`, `set_rank`, `transfer_leadership`, `disband_alliance`, `edit_alliance`, `request_help`, `help_all`, `donate`, `set_recommended_tech`, `alliance_shop_buy`, `claim_gift`, `claim_all_gifts`, `place_structure`, `remove_structure`, `set_marker`, `clear_marker`, `send_caravan`, `mute_member` | 07 §11 |
| Chat / mail | `chat_send`, `chat_history`, `block_player`, `get_mail`, `read_mail`, `claim_mail`, `claim_all_mail`, `delete_mail`, `send_mail`, `send_alliance_mail` | 07 §10 |
| Items / quests / events | `get_inventory`, `use_item`, `get_quests`, `claim_objective`, `claim_chapter`, `claim_daily_chest`, `get_events`, `claim_event_reward`, `get_leaderboard` | 08 §8 |
| Kingdom / season | `grant_title`, `migrate`, `enter_season`, `leave_season`, `get_season`, `claim_season_threshold`, `medal_shop_buy` | 09 §7 |
| Profile | `get_profile { player_id }`, `rename { name }`, `report_player { player_id, reason, message_id? }` | 10 §9.3, 11 §5 |
| Moderation (moderator accounts only) | `mod_mute`, `mod_rename`, `mod_ban`, `mod_reports` | 11 §5 |

Server → client:

| Area | Messages | Spec |
|---|---|---|
| Session | `welcome`, `logged_in`, `pong`, `ok`, `error`, `game_data`, `player_update` (name, power, Renown, alliance id, credits, medals, unread counters, stamina) | 00 §1.1, 01 §10 |
| City | `city_state`, `city_update` | 01 §10 |
| Commanders | `commander_update` | 04 §8 |
| Combat | `battle_update`, `rally_update`, `incoming_update` | 05 §14 |
| Map | `map_chunk`, `map_objects`, `map_object_update`, `map_object_remove`, `army_update`, `fog_update`, `stamina_update` | 06 §14 |
| Alliance | `alliance_update`, `help_requests`, `gifts_update` | 07 §11 |
| Chat / mail | `chat_message`, `mail_new` | 07 §10 |
| Items / quests / events | `inventory_update`, `quest_update`, `event_update`, `rewards_granted` | 08 §8 |
| Kingdom / season | `kingdom_update`, `season_update` | 09 §7 |

A consistency test (`protocol` crate + `client/tests/unit/protocol_test.gd`)
must assert that both sides know exactly this set as it grows task by task.
