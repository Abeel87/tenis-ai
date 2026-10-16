-- Presentation preferences are per-user/per-key; parallel device edits do not
-- overwrite unrelated settings. Research uses the existing private tier-C reader.
begin;
create table public.ui_preferences (
 user_id uuid not null references auth.users(id) on delete cascade,
 setting_key text not null check (
   setting_key ~ '^(matches|symphony)[.](focus|tour|surface|sort)$'
   or setting_key in ('symphony.market','alerts.enabled')
   or setting_key ~ '^saved:[A-Za-z0-9:_-]{1,120}$'
 ),
 value jsonb not null check (jsonb_typeof(value) in ('string','boolean') and octet_length(value::text)<=256),
 primary key(user_id,setting_key)
);
alter table public.ui_preferences enable row level security;
revoke all on public.ui_preferences from public,anon,authenticated;
grant select,insert,update,delete on public.ui_preferences to authenticated;
create policy ui_preferences_read on public.ui_preferences for select to authenticated
 using (user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null));
create policy ui_preferences_insert on public.ui_preferences for insert to authenticated
 with check (user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null));
create policy ui_preferences_update on public.ui_preferences for update to authenticated
 using (user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null))
 with check (user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null));
create policy ui_preferences_delete on public.ui_preferences for delete to authenticated
 using (user_id=(select auth.uid()) and exists(select 1 from public.profiles where id=(select auth.uid()) and banned_at is null));
alter table public.runtime_data_generations drop constraint runtime_data_generations_layer_check;
alter table public.runtime_data_generations add constraint runtime_data_generations_layer_check
 check (layer in ('core','market','dna','neuron','research'));
alter table public.runtime_data_heads drop constraint runtime_data_heads_layer_check;
alter table public.runtime_data_heads add constraint runtime_data_heads_layer_check
 check (layer in ('core','market','dna','neuron','research'));
commit;
