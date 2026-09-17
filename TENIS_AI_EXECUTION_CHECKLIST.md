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

**ACTIVE LOGIC/TASK:** `LOGIC-02 — Feature Provenance / Ranking Audit`

**SUBSTEP:** wykonać audit-only mapowanie rankingu fixture z Live Tennis API, historycznego `latest_rank`/`opponent_rank` z TML oraz wszystkich realnych konsumentów tych pól; zero zmian model math.

**BRANCH:** `brak` dla LOGIC-02 — świeży branch ma zostać utworzony dopiero po wejściu tego checkpointu na aktualny `main`.

**PR:** `brak` dla LOGIC-02. PR #386 jest zakończony i zmergowany; PR #383 został zamknięty bez merge jako superseded evidence.

**LAST VERIFIED MAIN:** `0c4c65f67e4bb3789f5693917911c4a4962ace9a` — botowy `data: refresh Superbet market context`, frontend/data-only drift po w pełni zielonym produkcyjnym refreshu LOGIC-01; parent `1b74e03ae5e1187d5ee90a547add622c5923d7c0`.

**LAST COMPLETED WORK:** `LOGIC-01 — Freshness Counterfactual` zakończony. PR #386 został zmergowany jako `c9292b630c918f7fde0c9c48231629a10819c09f` po pełnym green CI. Audit wykorzystał istniejący TASK 019 jako frozen evidence, odtworzył baseline Current bez cutoffu, policzył 30/60/90/120/180/365 dni przy zamrożonych baseline surface priors i osobno zbadał PBP/Early Hold. Nie wybrano cutoffu i nie autoryzowano żadnej zmiany PROD.

**CHANGED FILES w zakończonym PR #386:**

- `backend/history_freshness_counterfactual.py`
- `tests/test_history_freshness_counterfactual.py`
- `.github/workflows/history-freshness-counterfactual.yml`

**LOGIC-01 EVIDENCE:**

- workflow audit: `35265863260`, artifact `10516701643`, digest `sha256:f28fb5362ee8e24475b803beed9111da673e07635069037edb283e758491e77b`;
- baseline: 155 fixture'ów przeliczonych, 51 `model_ready`, 137 profili z >=5 meczami, zero błędów;
- `model_ready` retained / 51: 30d=9, 60d=32, 90d=36, 120d=38, 180d=41, 365d=46;
- profile z >=5 retained / baseline 137: 30d=40, 60d=86, 90d=97, 120d=105, 180d=114, 365d=126;
- Early Hold: 77 obecnie gotowych profili; >=5 wybranych próbek retained: 30d=33, 60d=75, 90d=77, 120d=77, 180d=77, 365d=77; najstarsza użyta próbka 157 dni;
- 594 daty próbek Early Hold rozwiązane, 0 brakujących;
- Brier/calibration/accuracy celowo nie zostały sfabrykowane: ten audit nie posiadał dedykowanego, bezstronnego settled prediction ledger; ten kontrakt należy do LOGIC-09.

**TEST STATUS:** PR #386 miał zielone testy jednostkowe LOGIC-01, realny restore cache, walidację kontraktu, pełny Project Health/pytest oraz brak błędów fixture w counterfactualu. Post-merge `main` przeszedł pełny final regression v9.3.3 w produkcyjnym refreshu.

**CI STATUS:**

- PR #386 final head `ea416c5cc136834e7f11c623276ae6fbd14bd9c5`: Delivery/Security run `35265862952` = GREEN; LOGIC-01 run `35265863260` = GREEN; CodeQL run `35265863139` = GREEN; UI & Project Health run `35265862833` = GREEN.
- post-merge `c9292b630c918f7fde0c9c48231629a10819c09f`: Project Health/full pytest, browser/dependencies i CodeQL = GREEN.
- production refresh run `35266260343`: wszystkie warstwy, guardy, final full regression, commit refreshed JSON, Pages artifact i Deploy Pages = GREEN; bot przesunął `main` do `1b74e03ae5e1187d5ee90a547add622c5923d7c0`.
- późniejszy botowy refresh Superbet market context przesunął `main` do `0c4c65f67e4bb3789f5693917911c4a4962ace9a`; drift względem `1b74e03...` dotyczył wyłącznie `frontend/data/*`, bez zmian kodu i dokumentacji.

**BLOCKERS:** brak blockerów.

**DO NOT REDO:** nie powtarzać TASK 019 ani LOGIC-01 bez nowego dowodu, że evidence jest błędne. PR #383 jest zamknięty bez merge. Nie wybierać cutoffu 30/60/90/120/180/365 „na oko” na podstawie samego LOGIC-01. Nie wdrażać freshness policy do PROD w LOGIC-02. Nie fabricować Brier/calibration bez bezstronnego common settled ledger.

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

### Stan zamkniętego TASK 019

- [x] PR #383 dostarczył historyczny freshness evidence użyty jako materiał wejściowy LOGIC-01.
- [x] Evidence zostało zweryfikowane i skonsumowane przez LOGIC-01 bez blind merge starego brancha.
- [x] PR #383 został zamknięty bez merge jako superseded evidence.

### NEXT EXACT ACTION

1. Sprawdź ponownie świeży `main`, otwarte PR-y i ostatnie CI; nie zakładaj, że `0c4c65f67e4bb3789f5693917911c4a4962ace9a` nadal jest HEAD, jeżeli bot zdążył zrobić kolejny refresh.
2. Utwórz świeży branch `logic-02-ranking-provenance` z aktualnego `main`.
3. Zmapuj bez nowych requestów: fixture `p1_rank/p2_rank` z Live Tennis API snapshotu, `latest_rank` i `opponent_rank` z TML/history oraz realne miejsca konsumpcji w Current Engine i SHADOW Player DNA.
4. Dla każdego rankingu zapisz source, observation/effective date jeśli istnieje, wiek, resolved player identity i miejsce użycia. Nie wymyślaj `ranking_effective_date`, jeśli provider go nie daje.
5. Audit-only: zmierz current-vs-historical rank, wiek historycznego rankingu, opponent-rank coverage i counterfactual, czy rank faktycznie wpływa na Current probability/output.
6. Zero zmian model math, probability, progów, wag, treningu, Player DNA, Surface Elo, Symfonii, Neuronu, PLAYABLE, settlementu, SHADOW→PROD ani iNeed$ calculations.
7. PR → pełne zielone CI + artifact → fresh-main check → merge → post-merge weryfikacja → checkpoint do LOGIC-03.

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

Status: `[x] COMPLETED — PR #386 / merge c9292b630c918f7fde0c9c48231629a10819c09f`

Cel: ustalić na danych, jak świeżość wpływa na jakość modeli; bez zmiany PROD.

- [x] Przenieść wynik TASK 019 jako baseline evidence.
- [x] Zmierzyć baseline produkcyjny bez cutoffu.
- [x] Przeliczyć scenariusze 30/60/90/120/180/365 dni dla Current player history.
- [x] Osobno zmierzyć PBP/Early Hold freshness.
- [x] Nie zmieniać global surface priors w pierwszym eksperymencie — izolować player-history effect.
- [x] Raport: profile retained, >=5 fresh matches, model-ready matches retained/lost.
- [x] Raport: probability/output deltas na tych samych fixture'ach.
- [x] Raport: Brier/calibration/accuracy tam, gdzie istnieje bezstronny settled common set — `N/A` dla wejścia LOGIC-01; brak dedykowanego unbiased settled prediction ledger, metryk nie sfabrykowano; własność tego kontraktu = LOGIC-09.
- [x] Lista konkretnych meczów/profili zależnych od starej historii w artefakcie.
- [x] Zero zmian PROD.
- [x] CI + artifact.

**Definition of Done:** spełnione. Mamy twarde dane do późniejszej decyzji o polityce świeżości; LOGIC-01 nie wybiera cutoffu „na oko”.

---

## LOGIC-02 — Feature Provenance / Ranking Audit

Status: `[~] ACTIVE — NEXT: RANKING PROVENANCE AUDIT`

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
