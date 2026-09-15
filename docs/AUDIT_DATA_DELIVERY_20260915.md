# Audyt i naprawy Tenis AI — 15 września 2026

Zakres: wykonanie bez zmiany matematyki, progów, wag, treningu, settlementu ani finalnego PLAYABLE. Ten PR **nie zamyka całego pakietu zleconego audytu**. Rozdziela gotowe poprawki od przygotowania migracji infrastruktury i ustawień wymagających dostępu administracyjnego.

## Stan sprawdzony przed zmianami

- Początkowy HEAD: `7187f9fac787aab6bbf759d3a104aa95597b8022`.
- Po wznowieniu pobrano aktualny main: `2bfb10412c3e074d2f90dd38d36cc6d04bf082c3`. Doszły wyłącznie commity danych. Gałąź robocza została przesunięta do tego HEAD przed końcowymi testami.
- Początkowo jedyny otwarty PR: #304, usunięcie osieroconego CSS. Nie został zmodyfikowany ani zmergowany.
- Ostatnie sprawdzone odświeżenia danych, Superbet, Neuronu, iNeed$ i Pages miały status success. Wyniki CI starego main nie są dowodem poprawności tego PR.
- Pages odpowiadało HTTP 200. `main` miał `protected=false`.
- Zweryfikowano live projekt Supabase Tenis AI: `kplcfqmcsukiqfbgvxcm`, PostgreSQL 17.6, Edge `ineed-sync` v10, migracje, RLS, uprawnienia kolumn i definicje SECURITY DEFINER.

## Tabela ustaleń

| Problem | Priorytet | Przyczyna / pliki | Ryzyko | Naprawa i stan |
|---|---|---|---|---|
| Ciężki pierwszy render | P1 | `frontend/app.js`, pięć pełnych feedów przed renderem | Duży transfer i opóźnienia na telefonie | Gotowe: mały indeks; szczegóły osobno, content-addressed |
| Wieczny cache w pamięci | P1 | `frontend/presentation-data.js` | Stare raporty/oferty i wyścigi fetchów | Gotowe: TTL per resource, no-store, reset przy logout/refresh; oryginalne guardy na każdym odczycie PLAYABLE |
| Odświeżenie miesza stary i nowy snapshot | P1 | Asynchroniczne route load w `app.js` | Stare szczegóły pod nowym indeksem | Gotowe: generacje ładowania, sprawdzenie identyfikatora i daty Symfonii, fail-closed |
| Git rośnie od danych | P1 | Cztery workflowy commitują generowane JSON-y | Duża historia i koszt checkout | Przygotowanie: archiwum z manifestem SHA-256, restore i artifact 90 dni. **Committowanie danych nadal działa** |
| Publiczne dane B/C | P1/P2 | Publiczne repo oraz upload całego frontend na Pages | Logowanie UI nie chroni bezpośredniego URL | Sklasyfikowane, plan migracji poniżej. **Autoryzowany transport plików nie został wdrożony** |
| Brak ochrony main | P1 | Ustawienie GitHub poza kodem | Direct push omijający CI | Konkretny plan poniżej. Brak narzędzia zapisu ruleset/admin settings; **nie włączono ochrony** |
| RLS auth init-plan | P2 | Polityki public, auth.uid dla każdego wiersza | Koszt zapytań | Wdrożono live; 25 ostrzeżeń → 0 |
| Brak indeksów FK | P2 | 4 tabele iNeed$ i ui_match_moderation | Joiny, usuwanie nadrzędnych rekordów | Wdrożono live; 5 → 0 |
| Publiczne helper RPC | P2 | is_admin/is_staff/can_access_community udostępnione anon | Zbędna możliwość odpytywania uprawnień | Wdrożono live: odebrano anon; authenticated zachowane |
| Ochrona haseł z wycieków wyłączona | P2 | Ustawienie Supabase Auth | Słabe/wykradzione hasła | Dostępne narzędzia nie zapisują ustawień Auth; **nie włączono** |
| Backfill zużywa budżet na rozpoczęte mecze | P2 | Wszyscy gracze aktualnego feedu mają ten sam priorytet | Wolniejsza dostawa danych do przyszłych meczów | Gotowe: nadchodzący zawodnicy przed rozpoczętymi; wyłącznie istniejące provider ID, nie zmieniono budżetów ani minimum 5 |
| Brak prawdziwego browser E2E | P2 | Smoke w VM/symulowanym DOM | Niewykrywane błędy przeglądarki | Gotowe: Chromium, 412×915, role, login, filtry, szczegóły, powrót, awarie i empty states |
| Drobna typografia / touch targets | P2 | style.css | Czytelność na Androidzie | Teksty poniżej .8rem podniesione; kontrolki co najmniej 44px |
| Brak lock i kontroli zależności | P2 | requirements.txt z zakresami | Zmienny build | Lock CPython 3.12/Linux, npm lock, Dependabot, pip-audit, npm audit, CodeQL |
| Małe próbki Symfonii | Diagnostyka | symphony2_stats.training | Błędna interpretacja pewności | Panel admin: train/validation, dostępne Brier, kalibracja; brakujące test/log-loss to N/D; etykiety tylko UI |
| Niejednoznaczna świeżość Neuronu | Diagnostyka | neuron-data-bridge i panel admin | Mylenie scoringu z treningiem | Osobno scoring, trening, dataset date_max, quality gate, świeżość źródeł |

## Dostarczanie danych i integralność

`scripts/build_delivery.mjs` używa istniejących funkcji prezentacji i guardów, bez własnej implementacji matematyki. Tworzy:

- `data/delivery/index.json`: metadane meczów, małe podsumowanie, odnośnik do szczegółów oraz minimalny dowód konieczny do ponownej kontroli PLAYABLE.
- `data/delivery/matches/<sha256>.json`: pełny oryginalny rekord meczu, jego Symfonia, DNA i kontekst cen. Hash wiąże konkretną zawartość z indeksem.
- `data/delivery/symphony.json`: dane potrzebne ekranowi Symfonii, pobierane dopiero na tej trasie.
- `data/delivery/diagnostics.json`: tylko diagnostyka administratora, bez wpływu na ranking.
- `manifest.json`: hashe źródeł i rzeczywisty checkout HEAD, nie SHA zdarzenia wyzwalającego workflow.

Wygenerowany katalog jest ignorowany przez Git i odtwarzany w każdym z trzech publisherów Pages. Indeks nie jest alternatywnym źródłem prawdy PLAYABLE: cache boolean nie daje dostępu do zakładu; pozostaje dotychczasowy kod exact-offer, wygasania i zgodności finalnej kompozycji. Nie zmieniono `playable-ui.js`, `superbet_playable.py`, `symphony2_engine.py` ani żadnego źródła model math.

Historia nie była globalnie ładowana na starcie już przed poprawką. Nadal jest odczytywana na żądanie. Ekran Symfonii oraz pełna historia pozostają większymi zasobami; to nie jest deklaracja, że wszystkie widoki mają budżet poniżej 1 MB. Techniczne dane administratora pozostają dostępne na jego trasach.

## Supabase — wykonana migracja

`supabase/migrations/20260915094023_audit_rls_and_fk_indexes.sql` odpowiada wersji zarejestrowanej live. Zmieniono sposób ewaluacji auth helpers w istniejących predykatach, zachowując komendy, role, USING i WITH CHECK. Dodano indeksy:

- ineed_bankroll_ledger(bet_id)
- ineed_email_events(experiment_id)
- ineed_experiments(created_by)
- ineed_signal_events(experiment_id)
- ui_match_moderation(updated_by)

Po migracji sprawdzono: brak prawa authenticated do zmiany role/banned_at/community_access, brak anonymous execute helperów, zachowanie authenticated helperów, brak authenticated execute systemowego iNeed RPC i zachowanie service_role execute. Wszystkie kontrole zwróciły true.

Pozostałe ostrzeżenia SECURITY DEFINER nie zostały mechanicznie usunięte: staff/admin RPC muszą być osiągalne dla JWT authenticated i sprawdzają rolę wewnątrz. `username_available` i `community_public_stats` pozostają publiczne zgodnie z obecnym flow. Tabele app_migrations/community_admin_audit mają RLS bez polityki klienckiej — nie otwarto ich, żeby usunąć ostrzeżenie. Nowe indeksy naturalnie zaczynają jako unused.

Edge iNeed v10 sprawdza podpis, issuer, audience, repository, ref, workflow_ref i event_name GitHub OIDC; endpoint odrzuca włączenie real betting. Nie zmieniono tej funkcji ani jej wdrożenia.

Dokumentacja: [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [ochrona haseł](https://supabase.com/docs/guides/auth/password-security). Ochronę wyciekłych haseł należy włączyć w Authentication → Settings → Security / Password Security, jeżeli pozwala plan projektu; potem ponownie odczytać security advisors. Nie zmieniać CAPTCHA ani istniejącej konfiguracji logowania.

## Klasyfikacja i konieczne dalsze wdrożenie

| Klasa | Dane | Docelowy dostęp |
|---|---|---|
| A | HTML/CSS/JS, logo, publiczna konfiguracja publishable key | Publiczne Pages |
| B | Indeks z predykcjami, analiza meczu, wybrane profile, Symfonia, historia i kontekst Superbet | Zalogowany, niezablokowany użytkownik aplikacji |
| C | Pełne zbiorcze payloady z technicznymi śladami, wagi/model Neuronu, admin diagnostics | Admin; dane iNeed$ dodatkowo moderator według istniejącego RLS |

**Aktualna implementacja plików B/C pozostaje publiczna.** Rola ukrywa trasę UI, nie URL. Sam prywatny bucket nie usuwa wcześniejszych kopii z publicznej historii Git. Nie wykonano rewrite historii, usuwania danych treningowych ani zmiany widoczności repo.

Docelowa migracja wymaga prywatnego Storage i autoryzowanej Edge Function:

1. Prywatny bucket; obiekty immutable z generation/hash; manifest wskazujący jedną kompletną publikację. Service key wyłącznie po stronie serwera.
2. Czytnik weryfikuje JWT przez Auth, odczytuje aktualny profil i banned_at, rozróżnia B/C po ścisłej allowliście ścieżek. Żadne role z user_metadata. Brak anonimowego fallbacku do Pages.
3. Publisher przez GitHub OIDC: allowlista repo/main/konkretnych workflowów, podpis/issuer/audience/event. Nie używać istniejącego endpointu iNeed do nowego zadania.
4. Rozdzielone snapshoty core (Update/Superbet), DNA i Neuron; spójny core i CAS wskaźnika generacji zapobiegają nadpisaniu nowszych danych przez starszy job.
5. Przed zmianą writerów zarchiwizować i zweryfikować pełne `data/cache` oraz opublikowane JSON-y w trwałym prywatnym magazynie. Artifact 90 dni **nie zastępuje trwałego archiwum treningowego**.
6. Zmienić wszystkie czytniki: Update, Superbet, DNA, Neuron, iNeed, audyty PBP/point tape, wszystkie deploye i testy CI. Niezaufany PR nie może dostać dostępu do prywatnych danych produkcyjnych; potrzebne odrębne bezpieczne fixtures CI.
7. Sprawdzić staging: cold-start bez runtime w Git, kolejny refresh każdej warstwy, odtworzenie archiwum, wygasła/brakująca generacja, rollback, user/admin/moderator/anon/banned. Dopiero wtedy usunąć hourly git add/commit/push. Brak danych ma zatrzymać publikację, nigdy rozluźniać gate.
8. Dopiero po działającym przełączeniu publikować na Pages allowlistę A i usunąć bieżące kopie B/C. Ochrona historycznie ujawnionych kopii wymaga osobnej decyzji o repo/archiwum; nie da się jej uczciwie obiecać samą zmianą frontendu.

## Wpływ na workflowy i ochrona main

| Producent | Aktualny zapis | Warunek wyłączenia direct push |
|---|---|---|
| Update tennis data | całe frontend/data; raw cache w Actions cache | trwały snapshot core+raw, hydrate i zachowanie pełnych gate |
| Superbet hourly refresh | frontend/data, modyfikuje też results/Symfonię | spójna generacja core, bez odtwarzania starszej oferty |
| Player DNA SHADOW | 12 wybranych raportów | osobna wersjonowana warstwa DNA i wszystkie czytniki |
| Neuron SHADOW | 3 pliki neuron_* | osobna warstwa Neuronu; izolacja wpływu zachowana |
| iNeed$ | Supabase przez OIDC | czyta nowy core; brak zmiany RPC/risk/settlement |
| Pages: FULL/FAST/Neuron | całe frontend | wspólny builder; potem prywatne B/C i publiczna allowlista A |

Przygotowano wspólną composite action `prepare-pages`: archiwizuje opublikowane źródła, weryfikuje sumy i generuje indeks. Zachowano kolejność istniejących guardów. Nie przenoszono tysięcy linii audytów PBP bez osobnej weryfikacji semantyki.

Po migracji writerów skonfigurować ruleset dla `refs/heads/main`:

- Pull request wymagany, bez bypass dla ludzi; blokada force push i delete.
- Required checks minimum `health`, `browser`, `dependencies` oraz rzeczywiste nazwy CodeQL z zielonego PR. Wszystkie te workflowy uruchamiają się dla każdego PR.
- Wymagać aktualności względem main; nie wpisywać jako obowiązkowych checków z filtrami ścieżek, które nie startują na każdym PR.
- Nie dodawać szerokiego bypass `github-actions` jako trwałego rozwiązania. Dopóki boty zapisują main, włączenie zakazu direct push zatrzyma aktualizacje.
- Sprawdzić PR → zielone CI, wszystkie refresh joby, Pages i iNeed. API wymaga repo Administration write; aktualny connector nie udostępnia operacji zapisu ruleset.

## Reprodukowalność i ograniczenia testów

Lock dotyczy zweryfikowanego bazowego środowiska CPython 3.12/Linux i zależności z requirements.txt. Dodatkowe opcjonalne instalacje Selenium/TabPFN w dotychczasowych workflowach nie zostały wszystkie objęte kompletnym transitive lock; nie deklarujemy odtworzenia całego ekosystemu treningu bit-for-bit. Nie zmieniono wersji TabPFN ani jego fallbacku. Pytest podniesiono z 8.4.2 do 9.0.3 po wykryciu PYSEC-2026-1845; zmiana dotyczy narzędzia testowego.

E2E używa rzeczywistego Chromium, DOM, account.js i auth-enhancements.js, ale **izolowanego transportu Supabase i testowej odpowiedzi CAPTCHA**. Nie jest to potwierdzenie logowania produkcyjnym kontem ani test prawdziwej CAPTCHA. Nie wysłano e-maili, nie utworzono kont i nie złożono realnych zakładów.

Wyniki i miary końcowe znajdują się w `AUDIT_RESULTS_20260915.json`. Cała lista zmian jest dostępna w Files changed PR. Status CI oraz SHA gałęzi należy sprawdzić przy review; raport nie utożsamia lokalnych testów z zielonym GitHub Actions.

## Końcowa weryfikacja lokalna

- Pytest: **1015 passed**, 11,31 s.
- UI static i runtime smoke: PASS.
- Playwright/Chromium: trzy role, mobile 412×915, PASS; transport Auth/CAPTCHA izolowany jak opisano wyżej.
- Projekcja: 675 porównań oryginalnego guardu PLAYABLE, zgodność szczegółów JSON i hashy, powtarzalny indeks, PASS.
- pip-audit: brak znanych podatności; npm audit: 0.
- Project health: 0 FAIL, 1 istniejące ostrzeżenie o liczbie modułów JS.
- Archiwum runtime: spakowano i zweryfikowano 48 rzeczywistych plików JSON.

Dla tej samej bazy `2bfb104…` pierwszy render zmniejsza statyczne pobrania runtime JSON z 5 / 40 882 012 B do 1 / 290 719 B (99,29% mniej). Miara nie obejmuje Auth/profilu, moderacji, JS/CSS ani późniejszych pobrań konta. Źródłowe feedy pozostają niezmienione; szczegóły są pobierane po otwarciu meczu. Pierwotny snapshot audytu miał 62 699 141 B — zmiana feedu na main sama zmniejszyła tę bazę, więc nie przypisujemy całości różnicy poprawce.

Pełna lista zmienionych plików znajduje się też w polu `changed_files` raportu JSON. HEAD po zmianach i status CI są identyfikowane przez commit i PR, żeby uniknąć wpisywania do pliku jego własnego, niemożliwego do ustabilizowania SHA.
