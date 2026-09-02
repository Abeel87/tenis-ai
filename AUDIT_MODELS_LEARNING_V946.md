# Tenis AI — audit modeli, uczenia i pokrycia v9.4.6

## Zakres

Audyt obejmuje Current Engine, Adaptive, AutoLearn, modele specjalistyczne, Player SHADOW, Accuracy/Market Lab, Symfonię 2.0 i NEURO SHADOW. Zasada architektury pozostaje bez zmian:

`DANE/MODELE -> SYMFONIA -> FILTR AKTUALNEJ OFERTY SUPERBET -> PLAYABLE`

MODEL/RAW nie zależy od dostępności operatora. Brak rynku lub linii Superbet nie może kasować ani zastępować obliczeń modelowych.

## Co naprawdę się uczy

- **AutoLearn** — rzeczywisty trening z chronologicznym train/calibration/validation i ochroną przed leakage.
- **Adaptive PROD / Adaptive base** — rzeczywista pętla feedbacku na zamkniętych historycznych predykcjach; korekty są ograniczone guardami.
- **CatBoost / TabPFN / Ensemble** — rzeczywiste modele/warstwa ensemble zgodnie z aktualnym artefaktem AutoLearn; ich jakość musi być oceniana na zamrożonych splitach, nie na bieżącym UI.
- **Player SHADOW** — rzeczywiście trenowany model, ale pozostaje SHADOW, ponieważ aktualny holdout nie daje przewagi wystarczającej do PROD.
- **Ensemble + Player learning SHADOW** — rzeczywiste uczenie blendu segmentowego, bez automatycznej promocji.
- **Accuracy / Market Lab** — rzeczywiste eksperymenty SHADOW z walidacją; rekomendacja progu nie jest automatycznie PROD.
- **Symfonia 2.0** — rzeczywisty supervised operator-line model z time split i kalibracją per rynek.

## Co jest modelem statystycznym, a nie samodzielnym ML

- **Current Engine** — deterministyczny/statystyczny silnik profilu zawodnika i dystrybucji meczu. Nie udaje samouczenia.
- **Early / Serve / Form / Surface** — specjalistyczne scorery regułowo-statystyczne. Ich skuteczność jest mierzona i może być korygowana downstream przez Adaptive, ale nie należy przedstawiać ich jako osobnych retrenowanych sieci/ML.
- **Consensus** — agregacja sygnałów, nie osobny uczący się model.

## Naprawa 1 — NEURO SHADOW settlement -> training

Przyczyna `unverifiable`: NEURO rozliczało prognozy tylko przeciwko bieżącemu `results.json`. Po zakończeniu spotkania fixture może wypaść z tego feedu, podczas gdy zweryfikowany finalny wynik jest już zapisany w głównym `history.json`.

Dodano `backend/neuro_shadow_archive_settlement_v946.py`, który:

- bierze tylko jawny, terminalny `result` z głównej historii (`completed`, `retired`, `void`),
- nie rekonstruuje wyniku z prognoz ani przyszłych danych,
- przekazuje finalny wynik do istniejącego retryowalnego settlementu NEURO,
- zachowuje zamrożoną pre-match probability i tożsamość selekcji,
- nie ma wpływu na PROD, PLAYABLE ani Symfonię.

Heavy workflow wykonuje teraz archive recovery przed zwykłym settle/capture/train/current.

## Naprawa 2 — Current Engine BO3 / BO5

Poprzedni pełny match distribution był zawsze BO3. To mogło dawać błędne match winner, exact score, total sets i match totals dla fixture BO5.

v9.4.6:

- zachowuje istniejący profil gracza i set model bez zmiany jego matematyki,
- czyta jawne `best_of` / `bestOf`,
- liczy osobno BO3 i BO5,
- BO5 ma pełną przestrzeń wyników `3:0, 3:1, 3:2, 2:3, 1:3, 0:3`,
- mecz kończy się w dystrybucji po osiągnięciu wymaganej liczby setów,
- nie zgaduje BO5 z nazwy turnieju; przy braku poprawnego metadata pozostaje konserwatywne BO3.

## Naprawa 3 — większe pokrycie Symfonii 2.0 istniejącą dystrybucją

Nie tworzono nowego AI dla rynków, które można policzyć dokładnie z już istniejącego shared state. Symfonia zachowuje jeden wspólny rozkład dla marginal i joint probability.

Dodano state support dla:

- `set2_winner`
- `set2_total`
- `set2_exact_score`
- `match_game_handicap`
- `set1_game_handicap`
- `set2_game_handicap`
- `player_total_games`
- `exact_sets`
- `set_handicap`
- `match_games_parity`
- `set1_games_parity`
- `set2_games_parity`
- `any_set_to_nil`
- `p1_exactly_1_set`, `p1_exactly_2_sets`
- `p2_exactly_1_set`, `p2_exactly_2_sets`
- `p1_wins_a_set`, `p2_wins_a_set`

Stan meczu przechowuje teraz również dokładny wynik każdego rozegranego seta oraz sumę gemów każdego zawodnika, dlatego handicap i player total nie są sztucznym blendem procentów.

## Celowo nadal bez sztucznego wsparcia

- `game_state` / `set2_game_state` wymagające prawdziwych checkpointów PBP — nie wolno rozliczać ich z finalnego wyniku seta.
- `match_total_aces` / `most_aces` — wymagają wiarygodnego serve-prop/ace state i settlement evidence; NEURO może być challengerem dopiero po zbudowaniu etykiet.
- rynki seta 3 zależne od wystąpienia seta wymagają poprawnej semantyki VOID/conditional probability; nie są wciskane do state support na siłę.

## NEURO — zasada promocji

NEURO pozostaje `SHADOW`. Sama liczba wygenerowanych prognoz nie jest dowodem uczenia. Warunek dalszego kroku to zamknięta pętla:

`frozen prediction -> verified settlement -> labeled history -> chronological train/holdout -> Brier/log-loss/accuracy -> market gate`

Dopóki rynek nie ma wystarczającej liczby zweryfikowanych etykiet i nie poprawia baseline na holdout, jego neural probability nie może wpływać na PROD/PLAYABLE/Symfonię.

## Testy dodane

- odzyskiwanie `unverifiable` NEURO ze zweryfikowanej historii,
- pełna masa i przestrzeń wyników BO3/BO5,
- state support Symfonii dla set2, handicapów, player totals, exact sets, parity i set props,
- jawny guard, że rynek asów pozostaje unsupported bez odpowiedniego stanu.
