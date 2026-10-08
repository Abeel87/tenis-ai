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
