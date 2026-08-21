-- Tenis AI v7.4.1 — bezpieczne sprawdzanie dostępności nicku
-- Uruchom RAZ w Supabase SQL Editor.

begin;

create or replace function public.username_available(wanted_username text)
returns boolean
language plpgsql
stable
security definer
set search_path = public
as $$
declare u text := trim(coalesce(wanted_username,''));
begin
  if char_length(u) < 3 or char_length(u) > 24 then
    return false;
  end if;

  return not exists (
    select 1
    from public.profiles p
    where lower(trim(p.username)) = lower(u)
  );
end;
$$;

revoke all on function public.username_available(text) from public;
grant execute on function public.username_available(text) to anon, authenticated, service_role;

commit;
