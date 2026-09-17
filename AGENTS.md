# Tenis AI — obowiązkowy protokół pracy dla agentów i kolejnych czatów

Ten plik jest **pierwszym dokumentem, który należy przeczytać przed jakąkolwiek zmianą w repozytorium**. Jest kontraktem pracy dla każdego kolejnego agenta/czatu. Nie wolno go obchodzić przez tworzenie alternatywnej ścieżki, wrappera, `vXXX`, hotfixu obok istniejącej logiki ani przez uznanie, że „tak już ma być”, jeżeli zachowanie jest sprzeczne z poniższymi zasadami.

## 1. Start każdej pracy

Przed analizą lub zmianą kodu:

1. Sprawdź **aktualny** `main`, HEAD, najnowsze commity, otwarte PR-y i status CI. Boty mogą przesuwać `main`; nie opieraj się na pamięci ani wcześniejszym czacie.
2. Przeczytaj w tej kolejności:
   - `AGENTS.md` — zasady pracy,
   - `TENIS_AI_LOGIC_CONSTITUTION.md` — niezmienne kontrakty danych i komunikacji modułów,
   - `TENIS_AI_MODEL_DATA_REGISTRY.md` — właściciele logiki, role modeli, znane problemy i kolejność napraw,
   - `TENIS_AI_EXECUTION_CHECKLIST.md` — aktywny etap, odhaczone kroki, `LIVE CHECKPOINT` i `NEXT EXACT ACTION`,
   - `ARCHITECTURE.md` — bieżąca architektura techniczna; jeżeli jest sprzeczna z konstytucją/rejestrem, **nie zgaduj** — zgłoś rozjazd i popraw dokumentację w osobnym, kontrolowanym kroku.
3. Porównaj `LIVE CHECKPOINT` z żywym GitHubem. Checkpoint jest punktem wznowienia, ale GitHub jest źródłem prawdy dla aktualnego SHA/PR/CI.
4. Ustal **kanonicznego właściciela** błędu. Nie naprawiaj objawu w warstwie downstream, jeśli źródło błędu jest upstream.
5. Najpierw audyt i test reprodukujący błąd; dopiero później zmiana zachowania.
6. Kontynuuj od `NEXT EXACT ACTION`; nie zaczynaj zakończonych etapów od zera bez dowodu, że wcześniejszy checkpoint był błędny.

## 2. Zasada: naprawa w miejscu, nie dokładanie warstw

Jeżeli istniejąca linia/funkcja/moduł jest błędny, poprawia się **kanoniczny kod**, usuwa błędną logikę i dodaje test regresyjny.

Nie wolno:

- tworzyć `*_v2`, `*_v3`, `*_vXXX` tylko po to, aby ominąć zły kod,
- zostawiać starej aktywnej ścieżki i uruchamiać równolegle nowej,
- dokładać guardu naprawiającego wynik innego guardu,
- maskować złego upstreamu w UI,
- tworzyć fikcyjnych danych/fallbacków, żeby ekran wyglądał „pełniej”,
- przepisywać probability, threshold, weight lub settlement w module, który nie jest ich właścicielem.

Po migracji ma istnieć **jedna aktywna ścieżka** dla jednej odpowiedzialności.

## 3. Twarde zasady projektu

- Dane muszą mieć źródło, czas, tożsamość i znaczenie. Brak danych = brak danych, nigdy `0` ani wartość zmyślona.
- `2026` jest bieżącym sezonem i opisuje obecny stan; `2025` jest poprzednim sezonem/bazą odniesienia. Starsze sezony mogą być długoterminowym prior/historycznym kontekstem, ale **nie mogą automatycznie udawać aktualnej formy**.
- „Ostatnie 5/10/20” nie oznacza automatycznie „świeże”. Wiek danych musi być jawny i audytowalny.
- Wynik/statystyka bez jakości przeciwnika jest niepełną informacją. Ranking, poziom rywala, tour i nawierzchnia są kontekstem, nie dekoracją.
- Przegrana z Top 20 nie jest równoważna przegranej z #500; wygrana z #500 nie jest równoważna wygranej z Top 50.
- Surowy serve/return/hold/break nie jest automatycznie „siłą” zawodnika. Docelowo siła ma być opponent-adjusted.
- Długa przerwa oznacza **inactivity/comeback uncertainty**. Bez twardego źródła nie wolno nazywać jej kontuzją.
- Ranking ma być używany jako cecha kontekstowa/trendowa, ale nie jako samodzielny wyrok.
- Tożsamość zawodnika ma być stabilna i provider-aware. Nie wolno porównywać ID z różnych namespace'ów ani zgadywać aliasów fuzzy bez osobnej autoryzacji.

## 4. Granice odpowiedzialności

Każda warstwa ma jedną rolę:

- **Data/Identity** — kto jest kim i jakie rekordy należą do gracza.
- **Context** — sezon, wiek danych, ranking, poziom rywala, tour, surface, inactivity.
- **Player DNA** — długoterminowe cechy gracza; nie „aktualna forma”.
- **Player State** — bieżący sezon, recent form, trend, comeback state; obecnie planowane/SHADOW do czasu walidacji.
- **Current Engine / ML** — generowanie probability z poprawnych wejść.
- **AutoLearn/Adaptive** — uczenie/kalibracja; nie może poprawiać identity ani wymyślać brakujących danych.
- **Symfonia** — składanie wspieranych probabilistycznie rynków i joint probability; nie zmienia surowych cech zawodnika.
- **Superbet** — autorytet dostępności dokładnego rynku/linii/kursu; nie definiuje model probability.
- **PLAYABLE** — końcowa bramka operatorowa/jakościowa, fail-closed.
- **iNeed$** — risk/EV/stake po PLAYABLE; nie tworzy probability i docelowo ocenia cały Bet Builder, nie pojedyncze nogi jako niezależne zakłady.
- **Frontend** — prezentuje wynik backendu i jego provenance; nie liczy nowych probability ani nie inventuje H2H/odds/stats.

## 5. Guardy i walidatory

Guard ma chronić konkretny kontrakt, a nie być drugim modelem biznesowym.

Każdy guard musi mieć:

- nazwany cel,
- wejście/wyjście,
- właściciela,
- test pozytywny i negatywny,
- powód blokady widoczny w diagnostyce.

Jeżeli stary guard blokuje legalny output nowego kanonicznego silnika, nie dodawaj kolejnego obejścia. Audytuj guard, popraw lub usuń jego nieaktualny warunek i zabezpiecz testem. Nie wolno mieć łańcucha guardów, które wzajemnie sobie przeczą.

## 6. Zmiany modeli i danych

Do czasu zakończenia programu reorganizacji **nie zmieniaj bez osobnej autoryzacji**:

- matematyki Current Engine,
- probability,
- progów,
- wag,
- treningu,
- Player DNA,
- Surface Elo,
- Symfonii,
- Neuronu,
- PLAYABLE,
- settlementu,
- SHADOW/PROD,
- iNeed$ calculations.

Audyt, telemetryka, registry, testy i SHADOW counterfactual są dozwolone, o ile nie wpływają na PROD.

## 7. Proces zmian

Standard:

`fresh main -> branch -> audyt/test -> minimalna poprawka kanonicznego właściciela -> pełne CI -> PR -> ponowny fresh-main check -> merge tylko green -> produkcyjna weryfikacja`

Nie merge'uj czerwonego PR. Jeżeli `main` przesunął się przed merge, sprawdź/rebase/rebuild i ponownie uruchom wymagane CI.

Każdy etap tego procesu ma odpowiadający checkbox w `TENIS_AI_EXECUTION_CHECKLIST.md`. Checkbox nie jest dekoracją — odhacz go dopiero po uzyskaniu dowodu.

## 8. Zasada prawdy w UI

Frontend pokazuje tylko dane, które potrafi wskazać do backendowego źródła/kontraktu.

- brak = `N/D` / brak danych,
- zero = tylko prawdziwe zero,
- SHADOW musi być oznaczone jako SHADOW,
- PROD nie może prezentować eksperymentu jako produkcyjnej rekomendacji,
- timestamp widocznych danych ma odpowiadać faktycznej generacji snapshotu, nie częstotliwości odświeżania przeglądarki,
- model output, operator offer i settlement to osobne źródła i nie wolno ich mieszać.

## 9. Zakaz „bajek”

Nie wolno uzasadniać istniejącego zachowania stwierdzeniem „tak ma być” bez wskazania kanonicznego kontraktu i kodu. Jeśli kod przeczy zasadom projektu, traktujemy to jako bug/legacy debt do zbadania, nie jako automatycznie prawidłowe zachowanie.

Każda istotna decyzja musi być oparta na:

- kodzie,
- danych,
- teście,
- artefakcie audytu,
- lub jawnej decyzji właściciela projektu.

## 10. Dokumentacja jest częścią kodu

Każda zmiana odpowiedzialności modułu, źródła danych, pipeline'u, guardu, statusu PROD/SHADOW lub właściciela UI wymaga aktualizacji `TENIS_AI_MODEL_DATA_REGISTRY.md` i — jeśli zmienia architekturę — `ARCHITECTURE.md`.

Każda zmiana statusu programu, wykonanie/merge zadania, realny blocker albo przerwanie pracy wymaga aktualizacji `TENIS_AI_EXECUTION_CHECKLIST.md`.

Jeżeli dokumentacja i runtime się rozjechały, to jest bug projektu.

## 11. Obowiązkowy checkpoint przed przerwaniem

Stan projektu ma być zapisany w repo, nie w pamięci czatu.

Przed zakończeniem dłuższej sesji, zmianą czatu albo gdy istnieje ryzyko przerwania należy zaktualizować `LIVE CHECKPOINT` w `TENIS_AI_EXECUTION_CHECKLIST.md` i zapisać:

- aktywny LOGIC/TASK i substep,
- branch i PR,
- ostatni zweryfikowany `main`,
- co faktycznie ukończono,
- zmienione pliki,
- status testów i CI,
- realne blockery,
- elementy `DO NOT REDO`,
- `NEXT EXACT ACTION`,
- aktualne twarde zakazy/ryzyka.

Nowy agent/czat ma najpierw zweryfikować ten checkpoint z żywym GitHubem, a następnie kontynuować od `NEXT EXACT ACTION`. Nie wolno resetować pracy do początku tylko dlatego, że zmieniła się rozmowa.
