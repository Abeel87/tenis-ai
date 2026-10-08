# TENIS AI — Self Evolution (etap 1: SHADOW research)

Status: **EXPERIMENT ONLY — no PROD authority**, implementation in backend/self_evolution_shadow.py.

## Cel
An autonomous research job periodically searches a **bounded deterministic family of 66 convex mixtures**
of three existing, prospectively frozen probability producers: Current, CatBoost and TabPFN.
This is **ensemble-weight selection**, not an AlphaZero agent, new foundation model or betting engine.
It does **not** tune any existing production model or claim guaranteed profit.

## Authoritative evidence
- Only frontend/data/prediction_ledger_shadow.json from existing pre-selection immutable owner.
- Only frontend/data/prediction_ledger_settlement_shadow.json from existing exact terminal scorer owner.
- Both source schemas must be SHADOW_ONLY and digest-linked; mismatches fail closed.
- Exact id:<number> live match identity, same frozen prediction ID, match key, candidate and schedule.
- Frozen capture must predate match start; terminal settlement must be known by evaluation time.
- Missing/void/unverifiable results and unavailable/invalid probabilities do not become negative training labels.

## Offline experiment
1. Collect complete UTC match days and split **entire fixture days**, not individual rows, into
   chronological train (60%), validation (20%), and untouched holdout (20%).
2. Training labels must have settled strictly before the validation window;
   validation labels must have settled before holdout begins.
3. Require at least **120 distinct matches in train**, **40 in validation**, and **40 in holdout**.
   Otherwise return explicit COLLECTING_VERIFIED_HISTORY with no candidate.
4. Evaluate 66 convex mixtures on train by Brier score, then consider the 12 best.
   Pick among those using validation only. Evaluate that already-selected combination on holdout
   and compare with the frozen Current baseline on the same samples.
5. Report descriptive status SHADOW_EVIDENCE_POSITIVE or SHADOW_NOT_BETTER;
   these statuses **do not authorize production promotion**.

The research job runs daily via .github/workflows/self-evolution-shadow.yml once merged to
main, or manually via GitHub Actions. PR runs do **only offline unit tests**.
Daily research restores exact chunked ledger bytes, makes **no network fetch**,
and uploads a 7-day job artifact self_evolution_shadow.json.
No bot commits, frontend publications, hidden PROD switches, operator actions or monetary bets.

## Local reproducibility
- python -m pytest -q tests/test_self_evolution_shadow.py
- python scripts/history_publication_chunks.py restore
- python backend/self_evolution_shadow.py

The runner reads repository data, produces frontend/data/self_evolution_shadow.json,
and **never** modifies immutable ledgers, model artifacts or downstream outputs.

## What is NOT implemented in phase 1
- Per-market strategy architectures, contextual bandits, agent memory, self-play, or neural architecture search.
- True live odds / price provenance and ROI, staking, Kelly and Bet Builder optimisation.
- Stable multi-run champion register, live decision execution, a production UI, or automatic model promotion.
- Automated production deployment. Positive SHADOW backtests alone are not a trading guarantee.

Next phase requires independently verified immutable historical operator quotes and
their pre-match timestamps, market-specific settled labels, prospective out-of-sample
evaluation, and a separately approved promotion contract. Until then the trainer
remains entirely isolated from PLAYABLE/Symphony/iNeed$.

### Nightly source materialization
The production settlement sidecar is not committed to Git. After restoring
the frozen ledger and history chunks, the nightly job must generate the
canonical exact-settlement sidecar locally before the research step. It never
commits that large derived file or treats missing exact outcomes as losses.
Brier comparisons weight each distinct fixture equally, not each correlated
candidate market. Regression tests enforce both contracts.


## Phase 2a — Market specialists (research-only, no bookmaker prices)

The same canonical research module now additionally groups exact market identifiers
already frozen in the preselection ledger. It never guesses tour, surface, match
identity or market from free text or a digest. Unknown market is N/D.

Specialists share the **global frozen** train, validation and untouched holdout
time cuts and independent match counting. Each market must have >=60/20/20
independent fixtures in these windows or yields INSUFFICIENT_EVIDENCE. A bounded
list of at most 12 lexicographically ordered market IDs is studied; excess IDs
are explicitly reported as unexamined. For each eligible market, the train
window ranks the same 66 mixtures, validation picks among 12 finalists,
and the holdout is **observed only**. No weights are delivered to live models.

As nightly runs repeatedly examine the same historical holdout, the report
labels these observations **descriptive exploratory research only**. True
prospective quality validation and permanent champion registration require a
separate later implementation; no automatic production promotion.

### Quote provenance audit blocker
Current Superbet and Bet Builder quote sidecars describe *current* operator
conditions, not an immutable one-quote-per-prediction historical as-of ledger.
No ROI/EV or economic reward is computed. The report exposes
quote_provenance.status = NO_FROZEN_EXACT_HISTORICAL_OPERATOR_QUOTES_JOINED,
with priced observation counts set to N/D (not 0), until exact historical
bookmaker quotes can be frozen and joined under audited chronology and
unique identity. Neither current odds nor post-match offers may fill this gap.


## Phase 2b — AI Memory + prospective Champion vs Challenger

The canonical backend/self_evolution_shadow.py research owner now writes two
independent artifacts per successful **main** GitHub Actions run:

* Original retrospective SHADOW report (unchanged).
* self-evolution-memory.json: a 60-day research-only, versioned register of
  Champion/Challenger model-mixture versions, per-version SHA-256 identities,
  historical fixed-horizon evaluations, run numbers and previous-state lineage.

Actions workflow uses read-only permissions (contents:read, actions:read).
It downloads the most recent available successful **main-branch** memory
artifact with GitHub CLI before training. Missing prior memory is an explicit
bootstrap. Corrupt artifact, invalid weights and non-monotonic timestamps
fail closed; there are no bot pushes and no production runtime consumers.

A challenger is frozen with a registration timestamp. Its retrospective
train/validation/holdout metrics NEVER qualify it for automatic promotion.
The only allowed evaluation observes real binary outcomes from canonical
settlement linked to model predictions **first captured after challenger
registration**, inside a fixed 14-day prospective window. Repeated frozen
snapshots for one exact candidate are deduplicated; correlated candidate
markets aggregate to one balanced contribution per fixture. Results from
matches before Challenger registration are *not* admissible.

After the full 14-day window, an independent SHADOW benchmark may change
only if >=100 distinct fixtures on >=7 UTC days and a conservative
approximate paired Brier improvement lower confidence bound exceeds 0.003.
Missing evidence remains INSUFFICIENT_PROSPECTIVE_EVIDENCE / N-D, not a win. A positive result
updates only this internal research registry and its auditable trial history:
no betting actions, model weights, Symphony, PLAYABLE, iNeed, real money,
automated PROD promotion, or guaranteed return. Repeated market comparisons
still require independent confirmation in future research.

Historical operator prices are not frozen per prospective action, so
bookmaker ROI / EV are NOT assessed. Version registry memory is time-limited
by GitHub Actions artifact retention; this is not permanent archival storage.


## Phase 2c — prospective exact Superbet price-evidence capture

Canonical archival evidence owner: backend/superbet_quote_evidence.py.
The existing hourly market-refresh workflow freezes a separate GitHub
Actions artifact after the existing Direct, prepriced Bet Builder and dynamic
SGA quote producers run. New operator HTTP requests: ZERO; no model training,
PROD/PLAYABLE/iNeed changes, real bets or repo artifact publication.

Each run records hashes of source documents, source timestamps/statuses,
exact Superbet fixture/event IDs, operator selection IDs, actual positive
odds and observation times, but only when identity and pre-start timestamp
proof are valid. Ambiguous duplicates, stale, unsupported, post-start and
unverified prices are excluded with explicit reason codes. Absence yields
NO_VERIFIED_PREMATCH_QUOTES (not zero odds / historical negative examples).
Price snapshots must never be backfilled by current postmatch odds.

The snapshot is an immutable Actions run artifact keyed by GitHub run/attempt
and retained 60 days. It is a per-run prospective sample, NOT a complete
permanent archive. It is not yet matched to immutable Prediction Ledger
decision identities; therefore EV, ROI, bankroll returns and profit claims
remain disabled. Separate forward-only decision/action/reward join requires
audit of exact market, line, selection and as-of quote proof.
