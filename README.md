# Tenis AI

Tenis AI jest systemem analizy meczów tenisowych, budowania probability rynków, walidacji bieżącej oferty Superbet, kompozycji Symfonii 2.0, PLAYABLE oraz eksperymentalnego risk layer iNeed$.

## Zanim zmienisz kod

Każdy agent/czat/programista ma zacząć od tych dokumentów, w tej kolejności:

1. **`AGENTS.md`** — obowiązkowy proces pracy, zakazy i zasada naprawy w miejscu.
2. **`TENIS_AI_LOGIC_CONSTITUTION.md`** — kanoniczne znaczenie danych i granice odpowiedzialności modeli/modułów.
3. **`TENIS_AI_MODEL_DATA_REGISTRY.md`** — bieżący rejestr modeli, źródeł, known logic debt i kolejność programu napraw.
4. **`TENIS_AI_EXECUTION_CHECKLIST.md`** — aktywny etap, checkboxy, `LIVE CHECKPOINT`, status PR/CI i `NEXT EXACT ACTION`; to jest punkt wznowienia po zmianie czatu lub przerwaniu pracy.
5. **`ARCHITECTURE.md`** — techniczna mapa aktywnego pipeline'u; rozjazd z runtime jest bugiem dokumentacji/architektury, nie powodem do zgadywania.

Historyczne audyty i plany są materiałem dowodowym. Nie mają pierwszeństwa nad powyższymi kontraktami i nie dowodzą, że opisywana kiedyś ścieżka nadal jest aktywna.

## Kanoniczna zasada pipeline'u

`RAW DATA -> IDENTITY/HYGIENE -> CONTEXT -> PLAYER/MODEL FEATURES -> CURRENT/ML -> CALIBRATION/ENSEMBLE -> SYMFONIA 2.0 -> EXACT CURRENT SUPERBET OFFER -> PLAYABLE -> iNeed$ -> UI/HISTORY/SETTLEMENT`

Brak rynku Superbet nie usuwa MODEL/RAW. SHADOW nie steruje PROD bez jawnej promocji. Frontend nie tworzy probability ani brakujących danych.

## Zasada konsolidacji

Nie dokładamy kolejnych aktywnych `vXXX`, wrapperów ani hotfixów obok błędnego kodu. Ustalamy jednego kanonicznego właściciela odpowiedzialności, odtwarzamy bug testem, poprawiamy właściciela, usuwamy zastępowaną aktywną ścieżkę po migracji i zabezpieczamy kontrakt testami.

## Zasada ciągłości pracy

Stan projektu ma być zapisany w repo, nie w pamięci pojedynczej rozmowy. Każdy zakończony krok, realny blocker, merge i zmiana aktywnego etapu mają być zapisane w `TENIS_AI_EXECUTION_CHECKLIST.md`.

Po przerwaniu pracy nowy agent nie zaczyna od zera. Najpierw sprawdza żywy GitHub, porównuje go z `LIVE CHECKPOINT`, a potem kontynuuje od `NEXT EXACT ACTION`.

## Testy bazowe

```bash
python -m pytest -q
node tests/ui_static_smoke.mjs
python scripts/project_health.py
```

Pełny zestaw wymaganych workflow/CI zależy od zakresu PR i musi być zielony przed merge.

## Status eksperymentów

Warstwy oznaczone w registry jako **SHADOW/PLAN** nie są źródłem produkcyjnej rekomendacji, dopóki nie przejdą audytu, counterfactual/backtestu, common test set, jawnego review i osobnego promotion PR.

Modele nie gwarantują wygranej ani zysku.
