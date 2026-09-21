-- LOGIC-12: cover the builder-ticket ledger foreign key discovered by post-rollout advisor delta.
-- This index preserves the shared-exposure schema while avoiding unindexed FK cleanup cost.

create index if not exists ineed_bankroll_ledger_builder_ticket_id_idx
  on public.ineed_bankroll_ledger(builder_ticket_id)
  where builder_ticket_id is not null;
