-- Tenis AI v8.2A — Scenariusze AI
create table if not exists public.ai_scenarios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  scenario_date date not null default current_date,
  title text,
  mode text not null default 'manual' check (mode in ('manual','generator')),
  profile text not null default 'balanced' check (profile in ('stable','balanced','strong','experimental','manual')),
  status text not null default 'active' check (status in ('draft','active','partial','settled','archived')),
  match_count integer not null default 0 check (match_count between 0 and 8),
  signal_count integer not null default 0 check (signal_count between 0 and 32),
  composer_score numeric(5,2) check (composer_score is null or composer_score between 0 and 100),
  calibrated_probability numeric(5,2) check (calibrated_probability is null or calibrated_probability between 0 and 100),
  items jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  composer_version text not null default 'v8.2A-core',
  settled_at timestamptz,
  points integer not null default 0
);
alter table public.ai_scenarios enable row level security;
create policy "ai scenarios own read" on public.ai_scenarios for select to authenticated using (user_id = auth.uid());
create policy "ai scenarios own insert" on public.ai_scenarios for insert to authenticated with check (user_id = auth.uid());
create policy "ai scenarios own update" on public.ai_scenarios for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "ai scenarios own delete" on public.ai_scenarios for delete to authenticated using (user_id = auth.uid());
create index if not exists ai_scenarios_user_created_idx on public.ai_scenarios (user_id, created_at desc);
create index if not exists ai_scenarios_user_status_idx on public.ai_scenarios (user_id, status, created_at desc);
