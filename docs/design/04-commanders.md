# 04 — Commanders

Conventions: [00](00-overview.md). Skill effect semantics: [05 §6](05-combat.md).
Data: [`data/commanders.yaml`](data/commanders.yaml), [`data/talents.yaml`](data/talents.yaml)
(hand-written; copy to `data/`). Progression constants: `data/progression.yaml` → `commanders:`.

Commanders are real historical figures. Names and dates are history; **every
skill name, description and number is original to this project**. Do not
replace them with text from any other game.

## 1. Roster (20)

| id | Name | Rarity | Talent trees | Role in one line |
|---|---|---|---|---|
| `hannibal` | Hannibal Barca | legendary | leadership, skirmish, conquest | Mixed-army field general, 3-target active |
| `subutai` | Subutai | legendary | cavalry, mobility, skirmish | Fast cavalry nuker with rage refund |
| `zhuge_liang` | Zhuge Liang | legendary | archer, support, skirmish | Archer skill damage, silence and rage drain |
| `leonidas` | Leonidas I | legendary | infantry, garrison, skirmish | Infantry tank, stronger when losing |
| `shaka` | Shaka | legendary | infantry, mobility, conquest | Fast infantry striker with a one-time heal |
| `amina` | Amina of Zazzau | legendary | leadership, conquest, cavalry | Rally leader, structure damage |
| `vauban` | Sébastien de Vauban | legendary | siege, garrison, support | Siege and garrison specialist |
| `tomoe_gozen` | Tomoe Gozen | renowned | cavalry, skirmish, support | Cavalry single-target damage |
| `khutulun` | Khutulun | renowned | cavalry, mobility, peacekeeping | Fast barbarian hunter |
| `jan_zizka` | Jan Žižka | renowned | infantry, garrison, leadership | Damage-reduction infantry/garrison |
| `artemisia` | Artemisia I of Caria | renowned | archer, skirmish, mobility | Mobile archer damage |
| `lapu_lapu` | Lapulapu | renowned | infantry, peacekeeping, skirmish | Barbarian hunter, XP bonus |
| `nzinga` | Nzinga Mbande | renowned | leadership, support, archer | Healer / secondary for mixed armies |
| `archimedes` | Archimedes | renowned | siege, garrison, support | Damage-over-time garrison defender |
| `spartacus` | Spartacus | veteran | infantry, peacekeeping, skirmish | Starter choice (infantry) |
| `tamar` | Tamar of Georgia | veteran | cavalry, garrison, leadership | Starter choice (cavalry) |
| `yue_fei` | Yue Fei | veteran | archer, peacekeeping, support | Starter choice (archer) |
| `hatshepsut` | Hatshepsut | veteran | gathering, support, leadership | Gatherer (quest reward) |
| `zheng_he` | Zheng He | veteran | gathering, mobility, leadership | Gatherer |
| `ibn_battuta` | Ibn Battuta | veteran | gathering, mobility, peacekeeping | Gatherer / fast marches |

Full skill tables (names, text, numbers for skill levels 1–5) are in
`data/commanders.yaml`; that file is the specification. Power budget used when
writing them, for anyone adding commanders:

| Rarity | Active potency Lv1 → Lv5 (single target) | Main passive stat Lv1 → Lv5 | Secondary passive |
|---|---|---|---|
| veteran | 300 → 650 | +4 % → +10 % | +3 % → +8 % |
| renowned | 500 → 1000 | +6 % → +15 % | +5 % → +12 % |
| legendary | 700 → 1400 | +10 % → +25 % | +4 % → +10 % |

Multi-target actives pay ~15 % potency per extra target; actives with a
buff/debuff pay ~15–30 %. For scale: a plain 1-v-1 army deals 2 × potency 100
per tick and fires its active every 10 ticks, so a potency-1000 active adds
about 50 % to that army's damage.

## 2. Commander state

```text
Commander { id, unlocked: bool, level: 1..50, xp: u64 (towards next level), stars: 1..5,
            skill_levels: [u8; 4]   # 0 = locked, else 1..5
            talents: { node_id: rank }, talent_reset_at: u64?,
            sculptures: u32,        # this commander's own sculptures held
            location: city | army(army_id) }
```

## 3. Skills

- 4 skills per commander. Skill 1 is always `kind: active` (costs 1000 rage); skills 2–4 are `passive`.
- Skill `n` unlocks (level 1) when the commander reaches **star `n`**. Star 5 unlocks nothing new but raises the level cap.
- Skill levels 1–5. `upgrade_skill { commander_id, skill_index }` costs that
  commander's sculptures: level 1→2: **5**, 2→3: **10**, 3→4: **15**, 4→5: **20**
  (50 per skill, 200 for all four). The player chooses which skill — no randomness.
- A passive skill with `type: mods` contributes modifiers to the Army scope
  (03 §1.2) while its `when` condition holds. A passive with `trigger:` runs
  its effects in battle (05 §6.3).

### 3.1 Schema

```yaml
commanders:
  - id: hannibal                    # unique
    name: "Hannibal Barca"
    title: "Terror of the Republic"
    origin: "Carthage, 247-183 BC"
    rarity: legendary               # veteran | renowned | legendary
    trees: [leadership, skirmish, conquest]   # exactly 3 ids from talents.yaml
    skills:                         # exactly 4; skills[0].kind == active
      - id: hannibal_1
        name: "Closing Jaws"
        kind: active                # active | passive
        trigger: { every_n_attacks: 6 }       # passive only, optional (05 §6.3)
        text: "…{1}…{2}…"           # {n} = n-th per-level array in `effects`, depth-first
        effects:                    # list of effects (05 §6.1)
          - { type: damage, potency: [600, 700, 800, 900, 1100], targets: 3 }
```

Validation: 4 skills, first active, others passive; every per-level array has
exactly 5 numbers; `mods` keys are in the registry (03 §1.5); `when` is in §3.2;
effect `type` is in 05 §6.1; `type: mods` only in passives without `trigger`;
`trees` exist and are distinct; `text` placeholders match the number of arrays.

### 3.2 Conditions (`when`)

| Value | True when |
|---|---|
| `always` | always |
| `field` | in a battle where the army is not a garrison and its target is not a city/structure garrison or structure |
| `garrison` | the army is a city or structure garrison (for the garrison pair) |
| `attacking_structure` | the army's target is a city, a structure, or their garrison |
| `rally` | the army is a rally army (for the leader's pair) |
| `vs_pve` | the army's target is a PvE army |
| `gathering` | the army is in state `gathering` (applies to gather rate, and to battle stats if attacked while gathering) |
| `only_infantry`, `only_cavalry`, `only_archer`, `only_siege` | 100 % of healthy troops are that type |
| `mixed` | at least 3 troop types each make up ≥ 10 % of healthy troops |
| `troops_above_50` / `troops_below_50` | healthy ≥ / < 50 % of `start_healthy` (battle only; outside battle `above` is true, `below` false) |

Non-battle keys (`march_speed_pct`, `march_capacity_pct`, `troop_load_pct`,
`gather_speed_*`, `commander_xp_pct`, `rally_capacity_pct`) with a battle-only
condition are simply inactive outside battle.

## 4. Levels and experience

- Level cap by stars: ★1 → 10, ★2 → 20, ★3 → 30, ★4 → 40, ★5 → 50. XP earned at the cap is discarded.
- `xp_to_next(L) = round_to_10(40 × L^2.4)` for `L` in 1…49 (table in `progression.yaml`;
  examples: L1 40, L10 10,050, L20 53,030, L30 140,330, L40 279,900, L49 455,540).
  Total 1 → 50 = 6,794,810 XP.
- XP sources: PvE victories (06 §5: both commanders in the army receive the
  full amount), XP tomes (08 §2), battles against players
  (`xp = 2 × Σ enemy severely wounded × troop power`, both commanders).
  All XP is multiplied by `(1 + commander_xp_pct/100)`.
- Each level above 1 grants **1 talent point** (49 at level 50).
- Level also raises troop capacity (§7).

## 5. Acquisition and stars — sculptures only

Everything is paid with **sculptures**, which come only from play. There are no
random draws anywhere.

- **Commander sculptures** are per commander (`Commander.sculptures`).
  **Universal sculptures** are items per rarity (`sculpture_universal_veteran|renowned|legendary`)
  and can be converted 1:1 into sculptures of any commander of that rarity
  (`convert_sculptures`), even one not yet unlocked.
- **Unlock** (`unlock_commander`): 10 sculptures of that commander. Starts at level 1, ★1, skill 1 at level 1.
- **Star up** (`star_up`): commander must be at the level cap of its current star.
  Costs ★1→2: **10**, ★2→3: **20**, ★3→4: **40**, ★4→5: **80** sculptures.
  The newly unlocked skill starts at level 1.
- Total to max one commander: 10 + 150 + 200 = **360** sculptures.

Sources (amounts in 08 §2.3):

| Source | What |
|---|---|
| Tutorial | choose one of `spartacus` / `tamar` / `yue_fei` (unlocked free); `hatshepsut` unlocked free by quest chapter 3 |
| **Hall of Heroes daily allowance** | `claim_daily_sculptures { commander_id }` once per game day: grants `daily_sculptures(level)` picks; one pick = 4 veteran, or 2 renowned (hall ≥ 8), or 1 legendary (hall ≥ 16) sculptures of the chosen commander. All picks of a day go to one commander. |
| Barbarians / Warcamps | veteran and renowned universal sculptures (06 §5–6) |
| Daily objectives, events, season rewards | universal sculptures of all rarities (08, 09) |
| Alliance shop | universal sculptures, weekly purchase limits (07 §6) |

Expected income for an active player with Hall of Heroes ≥ 16: ~45 legendary-equivalent
sculptures per week → one legendary fully maxed in about two months, renowned in one.

## 6. Talents

- 12 shared trees in `data/talents.yaml`; each commander has exactly 3 of them.
- Each tree has 9 nodes: 6 minor (3 ranks each), 2 major and 1 capstone (1 rank
  each) = 21 points. A node can be bought when
  `points already spent in this tree ≥ requires_points`. No other prerequisites.
- `mods` values are per rank; a node contributes `rank × value` under its `when` condition.
- Talent points = `level − 1`. Unspent points are allowed.
- Talents apply **only when the commander is the primary** of an army or garrison.
- `set_talents { commander_id, talents: {node_id: rank} }` replaces the whole
  allocation; validated by replaying the purchases in ascending `requires_points`
  order. Adding points to the current allocation is always allowed. An
  allocation that removes or lowers any node is a **reset**: free, but only
  once every 7 days per commander (`talent_reset_at`), and only while the commander is in the city.

| Tree id | Theme |
|---|---|
| `infantry`, `cavalry`, `archer`, `siege` | Stats of one troop type; capstones need a single-type army |
| `leadership` | Capacity and all-type stats; capstone for mixed armies |
| `garrison` | Everything `when: garrison` |
| `skirmish` | Open-field fights |
| `conquest` | Attacking cities/structures, rallies |
| `gathering` | Gather speed, load, safety while gathering |
| `peacekeeping` | PvE damage, commander XP |
| `mobility` | March speed |
| `support` | Healing, rage, damage reduction |

Schema: see the header comment of `talents.yaml`. Validation: 12 trees; node ids
unique globally; each tree's ranks sum to 21; `requires_points` < 21; keys in registry; `when` in §3.2.

## 7. Armies and pairing

`ArmySpec` (used by every march request): `{ primary: commander_id, secondary?: commander_id, troops: {troop_id: count} }`.

- An army needs a primary commander. Both must be unlocked, in the city, and not the same.
- A **secondary** is allowed only if the primary is ★3 or higher.
- Primary contributes: all unlocked skills + talents. Secondary contributes:
  all unlocked skills (its active fires the tick after the primary's, 05 §3.1), no talents.
- **Capacity** (max healthy troops when the army leaves):

```text
capacity = floor( (march_capacity(CH) + 1000 × primary.level + march_capacity_flat)
                  × (1 + march_capacity_pct / 100) )          # Army scope modifiers
```

- Troops must be healthy troops in the city; `1 ≤ Σ count ≤ capacity`.
- Number of armies outside the city ≤ `march_slots(CH)`. Reinforcing and rallying armies count.
- When an army returns to the city, troops rejoin the pool, lightly wounded
  recover, commanders become `location: city`, loot/gathered resources are added to the stockpile.
- The city garrison pair (05 §9.1) does not use a march slot.

### 7.1 Commander power

`power = rarity_mult × (50 × level + 200 × Σ skill_levels + 300 × stars)`,
`rarity_mult` = 1.0 veteran, 1.5 renowned, 2.0 legendary. Max legendary: 2 × (2500 + 4000 + 1500) = 16,000.

## 8. Protocol

| Request | Fields |
|---|---|
| `get_commanders` | — → `ok { commanders: [Commander], universal: {rarity: n}, daily_claimed: bool }` |
| `choose_starter` | `commander_id` (one of the three; once) |
| `unlock_commander` | `commander_id` |
| `convert_sculptures` | `commander_id, count` (uses universal of that rarity) |
| `claim_daily_sculptures` | `commander_id` |
| `star_up` | `commander_id` |
| `upgrade_skill` | `commander_id, skill_index (0..3)` |
| `set_talents` | `commander_id, talents: {node_id: rank}` |
| `use_xp_item` | `commander_id, item_id, count` |

Push: `commander_update { commander }` after any change (including XP from battles).

## 9. Edge cases

- XP that crosses several levels: apply repeatedly; stop at the cap and discard the rest.
- `star_up` below the level cap: `requirements_not_met`. At ★5: `limit_reached`.
- `upgrade_skill` on a locked skill or at level 5: `requirements_not_met` / `limit_reached`.
- `claim_daily_sculptures` for a rarity the hall level does not allow: `requirements_not_met`. Second claim in a day: `cooldown`.
- Changing talents or upgrading skills while the commander is out on an army:
  skill upgrades are allowed (take effect next tick); talent changes require `location: city`.
- Secondary whose primary drops below ★3: impossible (stars never decrease).
- A commander used as garrison primary and ordered out on an army: allowed; the garrison falls back per 05 §9.1.
- Level-cap XP: the client shows "MAX — star up to continue".
