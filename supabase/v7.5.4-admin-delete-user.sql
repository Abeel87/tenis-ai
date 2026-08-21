-- Tenis AI v7.5.4 — trwałe usuwanie kont przez ADMINA
-- Uruchom RAZ w Supabase SQL Editor.
--
-- Zasady:
-- - tylko rola admin może usuwać konta,
-- - admin nie może usunąć własnego konta,
-- - nie można usunąć innego admina,
-- - moderator nie może usuwać nikogo,
-- - moderatora trzeba najpierw zdegradować do USER,
-- - usunięcie auth.users kasuje profil i dane zależne przez ON DELETE CASCADE,
-- - wpis audytowy pozostaje, ale po usunięciu target_id staje się NULL.

begin;

-- Zachowujemy audyt również wtedy, gdy kiedyś usuwany USER był wcześniej moderatorem.
-- actor_id może wtedy zostać NULL zamiast blokować kasowanie profilu.
alter table public.community_admin_audit
  drop constraint if exists community_admin_audit_actor_id_fkey;

alter table public.community_admin_audit
  alter column actor_id drop not null;

alter table public.community_admin_audit
  add constraint community_admin_audit_actor_id_fkey
  foreign key (actor_id) references public.profiles(id) on delete set null;

create or replace function public.admin_delete_user(target_uid uuid)
returns boolean
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  uid uuid := auth.uid();
  target_role text;
  target_name text;
begin
  if uid is null or not public.is_admin(uid) then
    raise exception 'Tylko administrator może trwale usuwać konta.';
  end if;

  if target_uid is null then
    raise exception 'Brak ID użytkownika.';
  end if;

  if target_uid = uid then
    raise exception 'Nie możesz usunąć własnego konta administratora.';
  end if;

  select role, username
    into target_role, target_name
  from public.profiles
  where id = target_uid
  for update;

  if target_role is null then
    raise exception 'Nie znaleziono użytkownika.';
  end if;

  if target_role = 'admin' then
    raise exception 'Nie można usunąć konta administratora z panelu.';
  end if;

  if target_role = 'moderator' then
    raise exception 'Najpierw odbierz rolę moderatora, a dopiero potem usuń konto.';
  end if;

  insert into public.community_admin_audit(actor_id,target_id,action,detail)
  values(
    uid,
    target_uid,
    'delete_user',
    jsonb_build_object(
      'username', target_name,
      'role', target_role,
      'permanent', true
    )
  );

  -- profiles.id ma FK do auth.users(id) ON DELETE CASCADE.
  -- Kupony, komentarze, wiadomości, follow itd. zależne od profilu
  -- również znikają zgodnie z istniejącymi FK/cascade.
  delete from auth.users
  where id = target_uid;

  if not found then
    raise exception 'Nie znaleziono konta Auth do usunięcia.';
  end if;

  return true;
end;
$$;

revoke all on function public.admin_delete_user(uuid) from public;
grant execute on function public.admin_delete_user(uuid) to authenticated, service_role;

commit;
