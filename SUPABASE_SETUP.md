# Tenis AI v6.4 — Supabase setup

## Gotowe w paczce
- rejestracja e-mail + hasło
- logowanie / wylogowanie i zapamiętanie sesji
- publiczny nick
- heartbeat `last_seen_at`
- liczniki na stronie głównej: zarejestrowani / online / kupony dziś
- baza pod linki Superbet / Betclic / STS / Fortuna / inne
- tabele kuponów, zdarzeń kuponu, komentarzy i lajków
- RLS
- pole `verified`, żeby ranking później nie liczył samodzielnie oznaczonych wygranych

## Konfiguracja
1. Utwórz projekt Supabase.
2. SQL Editor → uruchom cały plik `supabase/schema.sql`.
3. Authentication → URL Configuration:
   - Site URL: `https://abeel87.github.io/tenis-ai/`
   - Redirect URL: `https://abeel87.github.io/tenis-ai/**`
4. W `frontend/supabase-config.js` wklej Project URL i browser-safe Publishable key.
5. Nigdy nie wklejaj `service_role` do frontendu.
6. Commit + deploy.

Wspólne kupony i automatyczne rozliczanie będą w kolejnym etapie; v6.4 przygotowuje pod nie bezpieczny fundament.
