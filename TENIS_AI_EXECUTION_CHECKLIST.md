# Tenis AI — execution checklist i checkpoint pracy

Status: **KANONICZNA LISTA WYKONAWCZA / PUNKT WZNOWIENIA**

Ten plik odpowiada za dwie rzeczy:

1. kolejność programu napraw i możliwość odhaczania wykonanych etapów,
2. jednoznaczny punkt wznowienia po przerwaniu pracy, limicie czatu, zmianie agenta albo przesunięciu `main` przez boty.

Nie wolno zaczynać kolejnego etapu tylko dlatego, że „wydaje się następny”. Najpierw sprawdź ten plik, bieżący GitHub i ostatni checkpoint.

---

## 0. Legenda statusów

- `[ ]` — nie rozpoczęto,
- `[~]` — rozpoczęte / w toku,
- `[x]` — zakończone i potwierdzone dowodem,
- `[!]` — blocker / konflikt wymagający rozwiązania,
- `[S]` — SHADOW/audyt gotowy, ale bez promocji do PROD.

Element wolno oznaczyć `[x]` tylko wtedy, gdy istnieje odpowiedni dowód: commit/PR, test, artefakt audytu, zielone CI albo produkcyjna weryfikacja — zależnie od rodzaju zadania.

---

# 1. LIVE CHECKPOINT — od tego miejsca ma zaczynać kolejny czat

**Ostatnia aktualizacja checkpointu:** 2026-09-17

**Aktywny program:** reorganizacja logiki/danych/modeli Tenis AI

**ACTIVE LOGIC/TASK:** `LOGIC-01 — Freshness Counterfactual`

**SUBSTEP:** przejąć istniejący dowód z `TASK 019` jako baseline evidence i ustalić, co można bezpiecznie wykorzystać bez powtarzania audytu.

**BRANCH:** `brak` — następny branch LOGIC-01 ma zostać utworzony dopiero ze świeżego `main` po wejściu tego checkpointu.

**PR:** `brak` dla LOGIC-01. `#384` jest zakończony i zmergowany.

**LAST VERIFIED MAIN:** `5269f6c467c3602fd6d557ed3385bc951008f07d` — merge PR #384; zweryfikowany po merge 2026-09-17 ok. 21:17 CEST.

**LAST COMPLETED WORK:** `LOGIC-00 — Project Constitution / Operating Contract` zakończony. PR #384 został zmergowany po pełnym green; kanoniczne dokumenty i test kontraktowy są na `main`; post-merge `Tenis AI UI & Project Health` przeszedł w całości zielono.

**CHANGED FILES w zakończonym PR #384:**

- `AGENTS.md`
- `ARCHITECTURE.md`
- `README.md`
- `TENIS_AI_EXECUTION_CHECKLIST.md`
- `TENIS_AI_LOGIC_CONSTITUTION.md`
- `TENIS_AI_MODEL_DATA_REGISTRY.md`
- `tests/test_project_contract_docs.py`

**TEST STATUS:** finalny PR #384 miał pełne wymagane CI zielone. Po merge na `main` pełny pytest oraz wszystkie kroki `Tenis AI UI & Project Health` również zakończyły się `success`.

**CI STATUS:**

- PR #384 final head `f41abaa760f7360c6fd6847412711963dd0c87b5`: `health`, `browser`, `dependencies`, CodeQL oraz analizy Python/JS = GREEN.
- post-merge `main @ 5269f6c467c3602fd6d557ed3385bc951008f07d`: `Tenis AI UI & Project Health` run `35263641686` = GREEN; `browser`/`dependencies` run `35263641554` = GREEN.

**BLOCKERS:** brak blockerów dla zamknięcia LOGIC-00.

**DO NOT REDO:** nie odtwarzać LOGIC-00 ani TASK 019 od zera bez nowego dowodu, że istniejący materiał jest błędny. PR #383 pozostaje materiałem wejściowym do LOGIC-01 i nie wolno go merge'ować w ciemno na starym base.

### Co zakończono w LOGIC-00

- [x] Utworzono `AGENTS.md` — obowiązkowy protokół pracy.
- [x] Utworzono `TENIS_AI_LOGIC_CONSTITUTION.md` — kanoniczne znaczenie danych i granice modułów.
- [x] Utworzono `TENIS_AI_MODEL_DATA_REGISTRY.md` — mapa modeli/danych i program napraw.
- [x] `ARCHITECTURE.md` wskazuje dokumenty nadrzędne i oznacza starą mapę UI jako debt.
- [x] `README.md` jest wejściem do kanonicznych dokumentów zamiast starej mapy vXXX/UI.
- [x] Dodano test kontraktowy dokumentacji.
- [x] Wszystkie wymagane checki PR #384 były zielone na finalnym headzie.
- [x] Fresh-main check wykonano bezpośrednio przed merge; `main` nadal wskazywał `d24bee7cd11f54f6a42ee3b890d6067f0c90a7f7`.
- [x] PR #384 zmergowano.
- [x] Merge commit: `5269f6c467c3602fd6d557ed3385bc951008f07d`.
- [x] Produkcyjna weryfikacja po merge: dokumenty są na `main`, pełny pytest i Project Health są zielone.
- [x] `LOGIC-00` zakończony.

### Znany równoległy stan

- `[S]` PR #383 — TASK 019 freshness audit: dowód audytowy istnieje, ale PR był oparty na starszym `main` i **nie wolno go merge'ować w ciemno**.
- LOGIC-01 ma najpierw odczytać żywy stan #383 (head/base/files/CI/artifacts), ocenić drift względem świeżego `main` i wykorzystać istniejący wynik jako baseline evidence tam, gdzie nadal jest ważny.
- Nie powtarzać samego audytu bez potrzeby; uzupełnić tylko brakujące elementy wymagane przez LOGIC-01.

### NEXT EXACT ACTION

1. Sprawdź ponownie świeży `main`, otwarte PR-y i CI; bot może przesunąć `main` po tym checkpointcie.
2. Odczytaj aktualny PR #383: head/base, changed files, CI, raporty/artefakty TASK 019 i dokładnie ustal, które wyniki są nadal ważne.
3. Porównaj #383 ze świeżym `main`; **nie merge'uj #383 w ciemno**. Zdecyduj na podstawie diffu, czy wynik przenieść jako evidence do nowego LOGIC-01, czy bezpiecznie przebudować/rebase'ować jego zakres.
4. Utwórz świeży branch LOGIC-01 z aktualnego `main` i rozpocznij wyłącznie audit/SHADOW freshness counterfactual.
5. Najpierw zamroź baseline produkcyjny bez cutoffu i istniejący TASK 019 evidence; potem uruchamiaj scenariusze 30/60/90/120/180/365 dni dla tych samych danych/fixture'ów.
6. Zero zmian PROD, probability, progów, wag, treningu, Player DNA, Surface Elo, Symfonii, Neuronu, PLAYABLE, settlementu, SHADOW/PROD promotion ani iNeed$ calculations w LOGIC-01.

---

# 2. Obowiązkowa checklista KAŻDEGO zadania / PR

Każdy przyszły TASK/LOGIC ma przejść przez tę listę. Nie pomijamy punktów po cichu.

## A. Start

- [ ] Sprawdź aktualny `main`/HEAD.
- [ ] Sprawdź wszystkie otwarte PR-y związane z tym obszarem.
- [ ] Sprawdź ostatnie workflow/CI i ostatni gate.
- [ ] Przeczytaj `AGENTS.md`.
- [ ] Przeczytaj `TENIS_AI_LOGIC_CONSTITUTION.md`.
- [ ] Przeczytaj odpowiedni wpis w `TENIS_AI_MODEL_DATA_REGISTRY.md`.
- [ ] Przeczytaj `TENIS_AI_EXECUTION_CHECKLIST.md` i sekcję `LIVE CHECKPOINT`.
- [ ] Ustal dokładnie jeden kanoniczny owner błędu/logiki.
- [ ] Potwierdź, że nie istnieje już aktywna równoległa implementacja rozwiązująca to samo.

## B. Audyt przed zmianą

- [ ] Odtwórz faktyczne zachowanie z kodu/runtime, nie z pamięci.
- [ ] Zapisz źródła wejściowych danych.
- [ ] Zapisz, które moduły konsumują wynik.
- [ ] Zapisz guardy/walidatory stojące przed i za modułem.
- [ ] Odtwórz bug testem, raportem lub audytem.
- [ ] Rozdziel: bug implementacyjny / problem danych / problem modelowy / debt dokumentacyjny.
- [ ] Jeżeli zmiana dotyczy probability/wag/progów/modelu — najpierw SHADOW/counterfactual i osobna autoryzacja.

## C. Implementacja

- [ ] Popraw kanonicznego ownera **w miejscu**.
- [ ] Nie twórz nowego `vXXX`, wrappera ani równoległej ścieżki jako obejścia.
- [ ] Usuń/zdezaktywuj zastępowaną aktywną logikę, gdy migracja jest bezpieczna.
- [ ] Nie zmieniaj downstream UI tylko po to, by ukryć zły upstream.
- [ ] Nie zmieniaj guardu, jeśli bug należy do producenta danych/modelu — i odwrotnie.
- [ ] Zachowaj provenance danych i reason codes.
- [ ] Dodaj test regresyjny.
- [ ] Zaktualizuj registry/architekturę/checklistę, jeżeli zmieniła się odpowiedzialność lub pipeline.

## D. Walidacja

- [ ] Test jednostkowy reprodukujący bug jest zielony.
- [ ] Testy sąsiednich modułów są zielone.
- [ ] Pełny wymagany pytest jest zielony.
- [ ] UI smoke jest zielony, jeśli zakres dotyczy UI/runtime danych.
- [ ] Project Health jest zielony.
- [ ] Security/CodeQL wymagane dla PR są zielone.
- [ ] Brak niezamierzonej zmiany probability/model math/settlement/PROD-SHADOW poza zakresem.
- [ ] Porównano output przed/po tam, gdzie zmiana może wpłynąć na wyniki.

## E. Merge

- [ ] PR zawiera wyłącznie zakres zadania.
- [ ] Wszystkie wymagane CI = GREEN.
- [ ] Świeży `main` sprawdzony bezpośrednio przed merge.
- [ ] Jeśli `main` się przesunął — branch przebudowany/rebase i CI uruchomione ponownie.
- [ ] Merge wykonany.
- [ ] Merge commit zapisany w checkpointcie.

## F. Po merge

- [ ] Sprawdź produkcyjny workflow/snapshot.
- [ ] Potwierdź, że funkcja faktycznie działa na `main`, nie tylko w teście.
- [ ] Potwierdź brak regresji w module downstream.
- [ ] Odhacz zadanie w programie.
- [ ] Ustaw `NEXT EXACT ACTION` następnego etapu.
- [ ] Zapisz nowy checkpoint przed zakończeniem czatu.

---

# 3. PROGRAM GŁÓWNY — lista do odhaczania

## LOGIC-00 — Project Constitution / Operating Contract

Status: `[x] COMPLETED — PR #384 / merge 5269f6c467c3602fd6d557ed3385bc951008f07d`

Cel: jedna prawda o projekcie, jeden sposób pracy, jedna kolejność napraw.

- [x] AGENTS protocol.
- [x] Logic Constitution.
- [x] Model/Data Registry.
- [x] README canonical entrypoint.
- [x] ARCHITECTURE authority order.
- [x] Contract-doc tests.
- [x] Execution checklist + resume protocol.
- [x] Final CI green.
- [x] Fresh-main check.
- [x] Merge #384.
- [x] Post-merge verification.

**Definition of Done:** wszystkie kanoniczne dokumenty są na `main`, testy ich obecności są zielone, checkpoint wskazuje LOGIC-01.

---

## LOGIC-01 — Freshness Counterfactual

Status: `[~] ACTIVE — NEXT: TASK 019 EVIDENCE REVIEW`

Cel: ustalić na danych, jak świeżość wpływa na jakość modeli; bez zmiany PROD.

- [ ] Przenieść wynik TASK 019 jako baseline evidence.
- [ ] Zmierzyć baseline produkcyjny bez cutoffu.
- [ ] Przeliczyć scenariusze 30/60/90/120/180/365 dni dla Current player history.
- [ ] Osobno zmierzyć PBP/Early Hold freshness.
- [ ] Nie zmieniać global surface priors w pierwszym eksperymencie — izolować player-history effect.
- [ ] Raport: profile retained, >=5 fresh matches, model-ready matches retained/lost.
- [ ] Raport: probability/output deltas na tych samych fixture'ach.
- [ ] Raport: Brier/calibration/accuracy tam, gdzie istnieje bezstronny settled common set.
- [ ] Lista konkretnych meczów/profili zależnych od starej historii.
- [ ] Zero zmian PROD.
- [ ] CI + artifact.

**Definition of Done:** mamy twarde dane pozwalające później zdecydować o polityce świeżości; nie wybieramy cutoffu „na oko”.

---

## LOGIC-02 — Feature Provenance / Ranking Audit

Status: `[ ] NOT STARTED`

Cel: wiedzieć skąd pochodzi każda ważna cecha i czy jest aktualna.

- [ ] Zmapować ranking fixture z Live Tennis API.
- [ ] Zmapować `latest_rank` z TML/history.
- [ ] Porównać current vs historical ranking dla wszystkich model-ready fixture'ów.
- [ ] Zmierzyć wiek używanego rankingu.
- [ ] Zidentyfikować miejsca, gdzie obecny ranking jest ignorowany.
- [ ] Zmapować opponent rank dla historycznych meczów, jeśli źródło pozwala.
- [ ] Zbudować provenance report per match/player.
- [ ] Zero zmian model math w fazie audytu.

**Definition of Done:** dla każdej cechy rankingowej znamy źródło, datę i miejsce użycia.

---

## LOGIC-03 — Population / Priors Audit

Status: `[ ] NOT STARTED`

Cel: sprawdzić mieszanie ATP/WTA/Challenger i wpływ globalnych priors.

- [ ] Zmierzyć current `_surface_priors` per surface.
- [ ] Rozbić priory na ATP / CH / WTA.
- [ ] Zmierzyć różnice hold/break/serve/return.
- [ ] Zmierzyć, ile profili zmienia się przez mixed-population prior.
- [ ] Sprawdzić fallback, gdy segment ma mało danych.
- [ ] Zaprojektować hierarchy/fallback bez wdrażania do PROD.
- [ ] SHADOW comparison.

**Definition of Done:** wiemy, czy i jak populacje muszą być rozdzielone oraz jaki fallback jest statystycznie uzasadniony.

---

## LOGIC-04 — Context Engine SHADOW

Status: `[ ] NOT STARTED`

Cel: jeden kanoniczny producent kontekstu meczu/historycznego rekordu.

- [ ] Zdefiniować schema contextu.
- [ ] current season / previous season / career prior.
- [ ] days_old / freshness bucket.
- [ ] surface.
- [ ] tour/event level.
- [ ] player rank / opponent rank / rank gap.
- [ ] opponent tier.
- [ ] inactivity gap / matches-since-return.
- [ ] provenance dla każdego pola.
- [ ] brak zgadywania kontuzji.
- [ ] SHADOW only.
- [ ] testy identity/time leakage.

**Definition of Done:** każdy model może konsumować jeden spójny kontekst zamiast własnych lokalnych interpretacji czasu/rankingu/surface.

---

## LOGIC-05 — Opponent Strength Engine

Status: `[ ] NOT STARTED`

Cel: wynik/statystyka ma znaczenie względem klasy przeciwnika.

- [ ] Ustalić dostępne historyczne informacje o jakości rywala.
- [ ] Zbudować opponent strength feature bez prostego ręcznego przelicznika rankingu.
- [ ] ranking tier / continuous transform do walidacji.
- [ ] surface-aware opponent strength.
- [ ] event/tour context.
- [ ] performance-vs-expectation residual.
- [ ] walk-forward validation.
- [ ] SHADOW only do czasu przewagi nad baseline.

**Definition of Done:** przegrana z Top 20 i przegrana z #500 nie są identycznymi obserwacjami treningowymi.

---

## LOGIC-06 — Opponent-Adjusted Serve / Return / Hold / Break

Status: `[ ] NOT STARTED`

Cel: Player DNA opisuje realną siłę, nie tylko surowe procenty z różnej klasy rywali.

- [ ] Expected serve vs opponent return strength.
- [ ] Serve residual.
- [ ] Expected return vs opponent serve strength.
- [ ] Return residual.
- [ ] Hold residual.
- [ ] Break residual.
- [ ] surface split.
- [ ] sample/confidence handling.
- [ ] porównanie raw vs adjusted na common test set.
- [ ] nie nadpisywać Player DNA przed promotion PR.

**Definition of Done:** 72% serve przeciw słabym returnerom nie jest automatycznie równoważne 72% przeciw elicie.

---

## LOGIC-07 — Player State

Status: `[ ] NOT STARTED`

Cel: oddzielić „kim gracz zwykle jest” od „jak gra teraz”.

- [ ] Current-season level.
- [ ] Recent form windows wybrane na podstawie LOGIC-01.
- [ ] Season delta vs 2025 baseline.
- [ ] ranking momentum.
- [ ] serve trend.
- [ ] return trend.
- [ ] opponent-adjusted performance trend.
- [ ] surface state.
- [ ] inactivity/comeback uncertainty.
- [ ] matches-since-return state.
- [ ] confidence/provenance.
- [ ] SHADOW comparison z obecnym Current Engine.

**Definition of Done:** system potrafi rozróżnić dobrego zawodnika w słabej formie od przeciętnego zawodnika w mocnym progresie.

---

## LOGIC-08 — Readiness Engine

Status: `[ ] NOT STARTED`

Cel: koniec z jednym prostym `model_ready` dla wszystkiego.

- [ ] Identity readiness.
- [ ] Freshness readiness.
- [ ] Current-season readiness.
- [ ] Surface readiness.
- [ ] Serve/return readiness.
- [ ] PBP readiness.
- [ ] Opponent-context readiness.
- [ ] Market-specific readiness.
- [ ] reason codes dla każdej blokady.
- [ ] UI prezentuje reason codes bez wymyślania danych.
- [ ] migration plan z obecnego boolean `model_ready`.

**Definition of Done:** system wie dokładnie, dla jakiego rynku ma wystarczające dane i dlaczego.

---

## LOGIC-09 — Learning Integrity / Prediction Ledger

Status: `[ ] NOT STARTED`

Cel: modele uczą się i są porównywane na uczciwej próbce.

- [ ] Zapisywać wszystkie wspierane pre-match predictions przed selection gate.
- [ ] Oddzielić `ALL`, `PLAYABLE`, `SELECTED`.
- [ ] Wspólny settled common test set Current/CatBoost/TabPFN.
- [ ] Walk-forward split bez leakage.
- [ ] Brier/calibration/accuracy na identycznej próbce.
- [ ] Market-specific metrics.
- [ ] Usunąć selection bias z interpretacji telemetryki.
- [ ] Nie zmieniać wag ensemble przed wynikami audytu.

**Definition of Done:** wagi i oceny modeli wynikają z porównywalnych danych, nie z różnych podzbiorów.

---

## LOGIC-10 — Guard Ownership / Dead Logic Audit

Status: `[ ] NOT STARTED`

Cel: guardy chronią kontrakty, ale nie walczą z legalnym outputem innych modułów.

- [ ] Lista wszystkich aktywnych guardów.
- [ ] Owner każdego guardu.
- [ ] Input/output/reason code.
- [ ] Kolejność wykonania.
- [ ] Wykrycie sprzecznych guardów.
- [ ] Audyt BO5 dead logic.
- [ ] Usunięcie/naprawa tylko po testach regresyjnych.
- [ ] Zero guardów naprawiających inne guardy.

**Definition of Done:** każdy guard ma jeden cel i nie blokuje legalnego kanonicznego outputu przez historyczny warunek.

---

## LOGIC-11 — Frontend Ownership / Data Provenance

Status: `[ ] NOT STARTED`

Cel: UI pokazuje dokładnie to, co backend faktycznie wyprodukował.

- [ ] Zmapować faktyczne importy/runtime obecnego UI.
- [ ] Ustalić jednego ownera listy meczów.
- [ ] Ustalić jednego ownera detail view.
- [ ] Ustalić jeden PLAYABLE gate w UI.
- [ ] Usunąć/oznaczyć martwe stare pliki po audycie.
- [ ] N/D zamiast sztucznego zero.
- [ ] SHADOW wyraźnie oznaczone.
- [ ] timestamp = generated_at backendu.
- [ ] żadnych frontendowych probability/H2H/odds fallbacków.
- [ ] zaktualizować `ARCHITECTURE.md` po potwierdzeniu ownerów.

**Definition of Done:** liczba widoczna w UI ma jednoznaczne backendowe źródło i ownera.

---

## LOGIC-12 — iNeed$ Bet Builder Redesign

Status: `[ ] NOT STARTED`

Cel: iNeed$ ocenia rzeczywisty finalny Bet Builder, nie niezależne single.

- [ ] Potwierdzić final Symphony composition jako jednostkę wejścia.
- [ ] Joint probability całej kompozycji.
- [ ] Exact Superbet combined odds / jawne zasady, jeśli operator nie dostarcza combined price.
- [ ] EV całego buildera.
- [ ] Kelly/risk/stake całego buildera.
- [ ] Jedna rezerwacja bankroll per BB.
- [ ] Jeden settlement całego BB.
- [ ] Min. 2 nogi.
- [ ] SHADOW/DRY_RUN.
- [ ] Brak real-money execution.
- [ ] Backtest na zamrożonych ofertach/operator context, jeśli dane pozwalają.

**Definition of Done:** ekonomika iNeed$ odpowiada temu samemu produktowi, który użytkownik faktycznie może zbudować w Superbet.

---

# 4. CHECKPOINT PRZERWANIA — obowiązkowy przed zakończeniem/przerwą

Przed zakończeniem dłuższej sesji albo gdy istnieje ryzyko limitu/przerwania należy zaktualizować `LIVE CHECKPOINT` i zapisać co najmniej:

- **ACTIVE LOGIC/TASK:** np. `LOGIC-05`.
- **SUBSTEP:** konkretny punkt checklisty.
- **BRANCH:** aktualny branch.
- **PR:** numer albo `brak`.
- **LAST VERIFIED MAIN:** SHA i czas sprawdzenia.
- **LAST COMPLETED WORK:** co faktycznie zakończono.
- **CHANGED FILES:** dokładna lista.
- **TEST STATUS:** które testy przeszły / które nie były uruchomione.
- **CI STATUS:** run IDs + green/red/in progress.
- **BLOCKERS:** realne blokery, nie przypuszczenia.
- **DO NOT REDO:** rzeczy już potwierdzone, których nie trzeba powtarzać bez powodu.
- **NEXT EXACT ACTION:** jedna konkretna następna czynność.
- **RISKS / HARD BANS:** czego nie wolno zmienić podczas wznowienia.

Jeżeli nie można zaktualizować pliku przed nagłym przerwaniem, następny agent ma odtworzyć checkpoint z GitHub PR/commits/workflowów i dopiero wtedy kontynuować.

---

# 5. PROTOKÓŁ WZNOWIENIA NOWEGO CZATU

Każdy nowy czat/agent ma wykonać kolejno:

1. Odczytaj `AGENTS.md`.
2. Odczytaj `TENIS_AI_LOGIC_CONSTITUTION.md`.
3. Odczytaj `TENIS_AI_MODEL_DATA_REGISTRY.md`.
4. Odczytaj ten plik i `LIVE CHECKPOINT`.
5. Sprawdź żywy GitHub: `main`, branch, PR, CI, najnowsze commity.
6. Porównaj stan GitHub z checkpointem.
7. Jeżeli bot przesunął `main`, nie resetuj całej pracy — oceń tylko drift względem aktywnego brancha.
8. Potwierdź, które checkboxy mają dowody i są nadal ważne.
9. Kontynuuj od `NEXT EXACT ACTION`.
10. Nie rozpoczynaj wcześniejszego etapu od zera, chyba że odkryto dowód, że checkpoint był błędny.
11. Nie przeskakuj do kolejnego LOGIC, dopóki Definition of Done aktywnego etapu nie jest spełnione albo jawnie oznaczone jako deferred/blocked przez właściciela projektu.

---

# 6. Zasada anty-chaos

Jeżeli podczas zadania pojawi się nowy problem, nie zmieniamy natychmiast całego zakresu.

- Jeżeli blokuje bieżący etap — wpisz jako blocker i napraw w jego ownerze.
- Jeżeli nie blokuje — dopisz do właściwego LOGIC/P0/P1/P2 w registry/checkliście.
- Nie twórz nowej architektury na boku.
- Nie zmieniaj kolejności programu bez zapisania powodu.
- Nie uznawaj problemu za rozwiązany tylko dlatego, że UI przestało go pokazywać.

Celem checklisty jest to, żeby **stan projektu był w repo, a nie w pamięci pojedynczego czatu**.
