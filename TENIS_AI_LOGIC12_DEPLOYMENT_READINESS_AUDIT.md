# LOGIC-12 — Shared Exposure Production Deployment Closeout

**Status:** DEPLOYED / VERIFIED READ-SIDE — BUILDER WRITES STILL DISABLED

**Repository baseline:** PR #450 merged as `8f6795e4670b32f601f04e8822a4dc40875e4d6f`.

## 1. Scope and hard boundary

This artifact closes the controlled 2026-09-21 production rollout of the already-reviewed LOGIC-12 shared-exposure read/accounting/presentation path.

The rollout deployed database read-side ownership/readers and `ineed-sync` v11. It did **not** add a builder reservation writer, builder settlement, model/probability changes or real-money execution.

Builder settlement remains `NOT_IMPLEMENTED`. `automatic_real_betting=false` remains mandatory.

## 2. Preflight evidence

Immediately before the first database mutation:

- fresh GitHub `main` was `8f6795e4670b32f601f04e8822a4dc40875e4d6f`;
- ACTIVE experiment remained SHADOW with starting bankroll 200 PLN;
- open V1 bets = 0 and open V1 exposure = 0;
- 35/35 historical `STAKE_RESERVED` rows had a V1 `bet_id` owner;
- `ineed_email_events` had 36 total historical events and 0 pending;
- live `ineed-sync` was ACTIVE v10 hash `0752efcece199bcc69c5f8e0387dff756cac90b0afd369b5364c8657e8e696e4`.
## 3. Database rollout evidence

The five reviewed migrations were applied in dependency order and verified after every step:

1. `20260921084010_ineed_builder_shared_exposure_dormant.sql` → live `20260921115222`.
2. `20260921091005_ineed_shared_exposure_readers.sql` → live `20260921115316`.
3. `20260921093354_ineed_admin_start_shared_exposure.sql` → live `20260921115347`.
4. `20260921095220_ineed_settlement_shared_exposure.sql` → live `20260921115431`.
5. `20260921101354_ineed_staff_exposure_summary.sql` → live `20260921115506`.

Post-DB advisor review found one new performance INFO: the `ineed_bankroll_ledger.builder_ticket_id` foreign key had no covering leading index.

That delta was fixed immediately by:

6. `20260921115606_ineed_builder_ticket_fk_index.sql` → live `20260921115606`.

After Step 6 the unindexed-FK finding disappeared. The index is currently reported as unused, which is expected while builder rows remain zero.

## 4. Database verification

Production now contains `ineed_builder_tickets`, `ineed_open_risk_exposures`, ledger `builder_ticket_id`, and `ineed_staff_exposure_summary(uuid)`.

At rollout closeout:

- builder ticket rows = 0;
- shared open rows = 0;
- shared open exposure = 0;
- V1 open rows = 0 and V1 open exposure = 0;
- placement uses the shared view and retains experiment locking/service-role ACL;
- admin-start uses the shared view and retains admin authorization;
- settlement uses the shared view for `other_exposure`, retains exactly two `FOR UPDATE` locks and remains service-role only.
## 5. Staff presentation and ACL proof

The normalized row-level exposure view remains service-only. Browser clients do not receive V1/builder risk rows.

`ineed_staff_exposure_summary(uuid)` is `SECURITY DEFINER`, uses `search_path=''`, and applies internal `is_staff(auth.uid())` authorization. `anon` has no execute privilege.

A live authenticated real-staff context returned:

- `source=SHARED_DB`;
- `open_units=0`;
- `v1_open_units=0`;
- `builder_open_units=0`;
- `total_exposure=0`.

The Supabase advisor warning that authenticated users can invoke this SECURITY DEFINER RPC is therefore reviewed/intentional, not ignored: invocation is necessary for the staff UI and authorization remains inside the function.

## 6. Edge v11 deployment

After all database/advisor gates were green, the exact reviewed repository `supabase/functions/ineed-sync/index.ts` was deployed.

Live function state:

- status: ACTIVE;
- version: 11;
- `verify_jwt=false`, preserving the existing internal GitHub OIDC authorization contract;
- source hash: `5e6cd2eea5937fd66de98754dbd40afe2906f6d70fbe5588116f218ef45c673f`.

The live source reads `ineed_open_risk_exposures` into normalized `risk_exposures` while keeping `open_bets` V1-only for settlement.

No builder table insert, builder reserve RPC, or builder settlement call exists in the Edge source.
## 7. Real production SHADOW verification

Normal workflow `iNeed$ SHADOW bankroll` run `35596941111` was dispatched against `main` after v11 deployment.

It completed GREEN end to end:

- guard GREEN;
- settlement runner GREEN: 0 settlements, 0 result-check errors;
- scoped runner GREEN;
- 41 real scoped evaluations processed;
- all 41 were `REJECTED`;
- 0 bets were placed.

Returned live state was:

- available capital = 191.2532 PLN;
- bankroll equity = 191.2532 PLN;
- active exposure = 0;
- `open_bets=[]`;
- `risk_exposures=[]`;
- `automatic_real_betting=false`.

## 8. Email non-regression

Live v11 still contains `ineed_email_events`, `QUALIFIED` alert generation, Gmail SMTP aliases/config handling and `flushEmails()`.

The rollout run had no `QUALIFIED` signal, so it correctly sent 0 new emails and left 0 pending. No synthetic betting alert was created.

Historical production evidence after rollout: 36 email events are `SENT`, all 36 have provider message IDs, and zero events are currently pending/config-blocked/failed.
## 9. Security/performance closeout

New rollout-related findings were reviewed explicitly:

- `ineed_builder_tickets` RLS/no-policy INFO is intentional because the table is service-only and browser roles have no table grant;
- staff summary authenticated SECURITY DEFINER WARN is intentional with `search_path=''` + internal staff authorization;
- the unindexed builder-ticket FK INFO was fixed by the sixth migration;
- the resulting unused-index INFO is expected at zero builder rows.

Unrelated pre-existing project advisor warnings remain outside LOGIC-12 and were not mixed into this rollout.

## 10. Hard stop before builder writes

The successful shared read-side deployment does **not** authorize builder reservations.

There is still no `ineed_system_reserve_builder_ticket` RPC, runtime caller, or durable builder writer. Builder ticket rows remain zero.

Any future reservation implementation requires a separate SHADOW-only PR using the same experiment-row serialization mutex, immutable builder owner/digest and exactly one `STAKE_RESERVED` ledger debit. It must not recompute model probability, Symphony joint probability, operator combined price, EV or Kelly.

Builder settlement remains `NOT_IMPLEMENTED` and cannot be inferred from V1 settlement semantics. Real-money execution remains out of scope.

## 11. Closeout verdict

Shared-exposure production read/accounting/presentation: **DEPLOYED AND VERIFIED**.

iNeed$ V1 SHADOW runtime: **GREEN on Edge v11**.

Email delivery contract: **PRESERVED**.

Builder reservation writer: **NOT IMPLEMENTED / DISABLED**.

Builder one-ticket settlement: **NOT_IMPLEMENTED**.

Next engineering step, only under a separate task/PR, may design the SHADOW builder reservation writer. It must not enable real-money execution or invent settlement semantics.
