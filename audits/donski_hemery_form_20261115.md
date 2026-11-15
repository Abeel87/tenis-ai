# Donski / Hemery form discrepancy — 2026-11-15

Scope: investigation of the owner's two screenshots; no runtime or model changes.
Audited main: `0387b698f8b89cbcf90ebb2d6ac9fd65deb62bb1`.
Fixture: `220525`, Alexander Donski / Calvin Hemery, Metz qualification,
2026-11-15 10:30 UTC. Published Current probability: 55.7 / 44.3.

## Verified evidence

- The supplied Superbet screenshot shows Donski LLLLL and Hemery LWWWW.
  Displayed recent results include Donski on November 8 and Hemery on November 13.
  These observations were not independently verified against the provider.
- Published `p1_stats.days_since_last=104`, `p2_stats.days_since_last=6`.
  These fields describe dates available to the core model, not actual inactivity;
  TML dates can have tournament precision. Do not infer injury or exact match dates.
- Core `model_ready=true`, `quality=HIGH`, `model_confidence=100` despite that age.
  `model_core.player_profile` uses row count, surface count and metric coverage for
  quality/confidence; its positional weights do not decay by actual calendar age.
- `player_intelligence_v85` is SHADOW and explicitly same-surface only. Its window-5
  raw wins are 0.8 / 0.4; adjusted values are 0.68174 / 0.48432.
  These are not the all-surface current last-five win/loss sequences.
- Window 20 contains 10 / 17 observations, but the UI labels both `Forma 20`.
- `frontend/match-detail-data.js::comparison` reads adjusted profile values and
  assigns the higher value to the correct participant; there is no participant
  inversion at this presentation boundary. `assessment` copies `match_win`.
- `frontend/app.js::quickAssessment` presents these diagnostic comparisons beside
  Current probability without exposing the window dates, actual sample count,
  same-surface scope or SHADOW provenance in that list. They are not proof of what
  caused the independent Current probability.

## Reproduction and limits

Ran the current match-detail JS in Node against the exact published fixture;
six assertions passed for form winner, both age fields, both window-20 counts
and Current probability. No production source, probability, quality gate or
training/settlement record was edited. No corrected prediction is claimed.

Next work: trace exact dated input rows through canonical history acquisition,
normalization and identity selection to establish why recent matches are absent;
repair that owner if a reproducible retrieval/selection defect exists. Expose
window provenance, sample counts and honest scope through existing profile/UI
owners. Any changed probability or freshness policy must follow the existing
counterfactual/validation process. Do not guess fresh outcomes, manually invert
the probability, or treat a new refresh timestamp as fresh player history.

## Follow-up diagnosis and authorized repair

Owner explicitly requested fixing the publication consequence after the initial
read-only investigation. Source verification corrected the earlier interpretation
of Hemery's six-day observation age: `tourney_date` means tournament week. His
November 13 loss to Martinez is present in `challenger_ongoing_tourneys.csv` with
November 9 date, alongside Baez and Mochizuki. Qualifying wins over Poullain and
Ghazouani Durand exist in provider PBP (217189 / 216590) but not those TML inputs.
Donski's main-draw history ends in August while current qualifying losses exist
in PBP. The TML source catalogue provides ATP qualifying, not Challenger qualifying.
Sources inspected: https://stats.tennismylife.org/tennis-match-database and the
actual 2026 Challenger, current Challenger and ATP-qualifying CSVs. No guessed
endpoint or alias was added.

Repair preserves source round/match metadata, sorts same-week matches correctly,
freezes exact source rows in the core profile and invalidates SHADOW profile cache
when content changes. `history_input` compares the five latest observed provider
outcomes against that actual sample. Existing 12-hour provider-index TTL and
five-match evidence floor are reused. Exact ID+name, completed score, fixture
cutoff and unique pair/score/surface/week overlap are required. No cross-provider
numeric IDs, incomplete scores, synthesized priors or player-swapped probability.

Publication is withheld when those results are absent or unverified. Symphony
produces no scored markets/compositions; final PLAYABLE produces no iNeed signals.
Raw probabilities remain evidence and are hidden as recommendations in the UI.
SHADOW form is explicitly same-surface sampled history with real n and date bounds.

This does not promote experimental PBP statistical conversion into production and
does not assert that the cached PBP subset is exhaustive or that any bet will win.
Focused reproduction tests include missing results, tournament-week equivalence,
identity conflicts, missing snapshots, stale source index, ambiguous overlaps,
cache correction, deterministic round order and stale-composition rejection.

## Release prerequisite: separately reviewed inactive archive snapshot

PR #592's runtime, Symphony, browser/security and full 1968-test checks passed.
Two independent 2024 archive checks rejected provider fingerprint drift. The
canonical candidate audit (43701483806, artifact 14156283318) still proved all
safety checks: 11,620 candidate rows, zero ID/score/shadow/visible-resolution or
archive-only identity conflicts, and every frozen exclusion matched evidence.
Only ATP 2024 and the derived candidate digest differ from the Nov 2 manifest.

A fresh manual audit revision is recorded in `tml_2024_review_20261115.json`.
All four official source receipts were downloaded and their exact logical hashes
independently matched CI; canonical materialization reproduced the same candidate
hash and all ten numeric consistency checks passed with zero violations. Source
URLs, row counts, exclusions and guard code are unchanged. The old expected
fingerprints are retained in the manifest basis and evidence; old raw bytes were
not recoverable, so full old/new equivalence is explicitly NOT claimed.

This review updates only the frozen audit candidate (manifest v5). Current
TML_SOURCES still exclude 2024. The separate runtime-equivalence/integration gate
remains false because old history would change shared priors. No archive is
promoted, no source validator is weakened and no automatic re-lock is introduced.

Validation: local full suite 1968 passed + 9 subtests; real CI Chromium passed
user/moderator/admin and 320/412/1280px layouts, including blocked-history UI.
