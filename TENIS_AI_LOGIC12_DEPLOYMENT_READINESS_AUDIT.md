# LOGIC-12 — Shared Exposure Deployment Readiness Audit

**Status:** AUDIT / READINESS CONTRACT ONLY — NO DEPLOYMENT AUTHORIZED

**Audit base:** `5e2f008bafc516ccc47ac79a9844b46c98a71281` (PR #449 merge)

## 1. Scope

This audit defines the only safe rollout order for the already-merged LOGIC-12 shared-exposure schema/read-side changes. It does **not** apply a migration, deploy an Edge Function, create a builder reservation writer, or implement builder settlement.

The repository has closed the known V1-only read/presentation consumers. Production has not yet received those database objects or the newer `ineed-sync` read-side.

Builder settlement remains `NOT_IMPLEMENTED`. Real-money execution remains disabled.

## 2. Verified live pre-deploy state

Read-only Supabase evidence on 2026-09-21 shows:

- live `ineed-sync` is ACTIVE v10 with source hash `0752efcece199bcc69c5f8e0387dff756cac90b0afd369b5364c8657e8e696e4`;
- live migration history ends before every LOGIC-12 shared-exposure migration;
- no Supabase development branch exists;
- `public.ineed_builder_tickets` does not exist;
- `public.ineed_open_risk_exposures` does not exist;
- `public.ineed_staff_exposure_summary(uuid)` does not exist;
- `ineed_bankroll_ledger.builder_ticket_id` does not exist;
- live placement/admin-start/settlement still read V1-only exposure sources;
- live settlement still contains two `FOR UPDATE` locks: target V1 bet + owning experiment.

Current ACTIVE SHADOW bankroll evidence is suitable for a future low-blast-radius rollout window but is not a permanent invariant:

- starting bankroll: 200.0000 PLN;
- latest available capital: 191.2532 PLN;
- open V1 exposure: 0;
- open V1 bets: 0.

Historical compatibility evidence:

- 35 `STAKE_RESERVED` ledger rows exist;
- all 35 are owned by a V1 `bet_id`;
- zero `STAKE_RESERVED` rows are ownerless;
- 35 V1 bets exist and zero are currently open.

Therefore the dormant reservation-owner constraint is compatible with the current database history.

## 3. Repository deployment bundle

The DB bundle is ordered by migration timestamp and dependency:

1. `20260921084010_ineed_builder_shared_exposure_dormant.sql` — 14 statements.
2. `20260921091005_ineed_shared_exposure_readers.sql` — 3 statements.
3. `20260921093354_ineed_admin_start_shared_exposure.sql` — 2 statements.
4. `20260921095220_ineed_settlement_shared_exposure.sql` — 3 statements.
5. `20260921101354_ineed_staff_exposure_summary.sql` — 3 statements.

All five parse as PostgreSQL and their filenames are in the required chronological order.

The repository `supabase/functions/ineed-sync/index.ts` already reads `ineed_open_risk_exposures`, while deployed v10 still reads V1 `ineed_shadow_bets` only. The candidate Edge source passes Deno type-check.

This creates a hard dependency: **database objects/readers must be deployed and verified before the Edge candidate can be deployed**.

## 4. Preflight gate for any future rollout

Before the first write to a Supabase environment:

1. fetch fresh repository `main` and verify the exact merged migration set;
2. confirm there is no newer conflicting iNeed migration or open iNeed PR;
3. capture live migration history, Edge version/hash, iNeed function definitions, active experiment/bankroll state and advisor baseline;
4. require `open V1 bets = 0` for the first controlled rollout window unless a separate concurrency proof explicitly authorizes otherwise;
5. confirm builder reservation writer and builder settlement are still absent;
6. confirm a rollback/recovery route before mutation.

A Supabase development branch is preferred for first application. None exists today. Creating one requires cost confirmation and explicit authorization; this audit does not create it.

## 5. Required database rollout order

### Step A — dormant owner + normalized view

Apply only `20260921084010_ineed_builder_shared_exposure_dormant.sql`.

Immediately verify table/view existence, ledger column/constraints, RLS, grants, generated identities, zero builder rows and V1 projection equivalence. Do not insert a builder ticket.

### Step B — V1 placement reader

Apply `20260921091005_ineed_shared_exposure_readers.sql` only after Step A verification is green.

Verify the live function definition reads `ineed_open_risk_exposures`, still locks signal + experiment, remains service-role only, and is V1-equivalent with zero builder rows. Do **not** place a test bet merely to prove the migration.

### Step C — admin-start reader

Apply `20260921093354_ineed_admin_start_shared_exposure.sql` only after Step B verification is green.

Verify the function definition reads the shared view and preserves admin authorization/experiment locking. Do **not** start a new experiment as a rollout probe.

### Step D — settlement bookkeeping reader

Apply `20260921095220_ineed_settlement_shared_exposure.sql` only after Step C verification is green.

Verify the live function still contains both `FOR UPDATE` locks, reads the shared view for `other_exposure`, excludes the target V1 bet, and preserves the existing outcome/payout/ledger/status contract. Do **not** settle a bet as a rollout probe.

### Step E — staff presentation aggregate

Apply `20260921101354_ineed_staff_exposure_summary.sql` only after Step D verification is green.

Verify the underlying view remains service-only, the RPC exposes aggregates only, PUBLIC/anon cannot execute it, authenticated non-staff fail, and authorized staff receives V1-equivalent totals with zero builder rows.

## 6. Advisor delta gate

After DB Steps A-E, rerun Supabase security and performance advisors and compare against the captured pre-rollout baseline.

Existing baseline warnings are not part of this rollout and must not be mixed into LOGIC-12 cleanup. Only new deltas caused by the shared-exposure bundle are rollout blockers.

The staff summary is intentionally `SECURITY DEFINER` + authenticated-callable with an internal `is_staff(auth.uid())` authorization check, so any new advisor warning for that function must be explicitly reviewed against this contract rather than ignored automatically.

## 7. Edge rollout comes last

Only after all DB verification gates are green may the repository `ineed-sync` candidate be considered for deployment.

That deployment requires separate explicit authorization. Preserve the current custom GitHub OIDC contract and current `verify_jwt=false` deployment setting because authentication is enforced inside the function.

Post-Edge verification must prove:

- deployed source/version changed only to the reviewed repository candidate;
- `action=state` reconstructs V1 equity/exposure equivalently from `risk_exposures` when there are zero builder rows;
- `open_bets` remains V1-only for settlement;
- no real-money execution path exists;
- no builder ticket is written;
- the existing `ineed_email_events` queue, `QUALIFIED` alert generation, Gmail SMTP aliases/config handling and mail flush behavior remain intact.

The shared-exposure rollout must not silently disable or bypass iNeed$ email delivery. Mail verification is a regression gate, not a reason to send a synthetic betting alert.

Do not use a mutating SHADOW sync merely as a smoke test outside the existing controlled workflow.

## 8. Hard stop before any builder writer

Successful deployment of the read-side bundle still does **not** authorize builder reservation writes.

A future writer requires a separate design/implementation PR and must reuse the same experiment-row serialization mutex, one durable `ineed_builder_tickets` owner and exactly one `STAKE_RESERVED` debit. It must not recompute model probability, joint probability, operator combined price, EV or Kelly.

Before that writer can be considered, the deployed read-side must have demonstrated stable V1-only equivalence and no unexpected security/performance advisor delta.

Builder settlement remains `NOT_IMPLEMENTED` and cannot be inferred from V1 settlement semantics.

## 9. Readiness verdict

Repository readiness: **READY FOR CONTROLLED DEPLOYMENT VALIDATION, NOT READY FOR BUILDER WRITES**.

Production readiness today: **BLOCKED** because the shared-exposure DB bundle and candidate Edge source are not deployed, no Supabase dev branch exists, and no explicit deployment/cost authorization has been given.

Next safe action after this audit is merged: obtain explicit authorization for a controlled deployment environment (preferably a cost-confirmed Supabase development branch) or, if production rollout is explicitly chosen, execute the preflight and DB-first sequence above with verification after every step.
