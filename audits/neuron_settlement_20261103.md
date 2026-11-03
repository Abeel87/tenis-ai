# Neuron / AutoLearn: audyt rozliczeń i publikacji porównań

Status: **poprawka przygotowana; bez wdrożenia; wymagana zgoda właściciela**.
Audytowany main: `0d2f6bb7553e2407e1eac05d40ddcec3cc418bd5`.
Daty i godziny poniżej podano w UTC. Dowody maszynowe i hashe wejść:
[`neuron_settlement_20261103.json`](neuron_settlement_20261103.json).

## Ustalenie

Brak par miał więcej niż jedną przyczynę. Raport z 03:20Z rzeczywiście nie miał
jeszcze rozliczonego meczu z dostępnym zamrożonym ensemble. Nowsza historia
pozwala już rozliczyć dwie takie pary. Niezależnie wykryto błąd publikacji:
publisher ponownie obliczał raport bez ledgeru AutoLearn, przez co usunąłby
również poprawnie obliczone porównania. Sama liczba ukończonych testów ani
pobranych PBP nie dowodzi dostępności tych porównań.

| Populacja bieżącego modelu | Opublikowane 03:20Z | Odczyt nowszej historii z audytowanego main |
| --- | ---: | ---: |
| Unikalne mecze | 207 | 207 |
| Rozliczone binarnie | 26 | 28 |
| Void, poza metrykami binarnymi | 4 | 7 |
| Nierozliczone | 177 | 172 |
| Rozliczone pary Neuron–AutoLearn | 0 | 2 |
| Rozliczone bez zamrożonego ensemble | 26 | 26 |

To read-only replay istniejących prognoz i istniejących wyników, nie publikacja
nowego raportu ani rekonstrukcja dawnych prawdopodobieństw. Model pozostaje
`neuron-27a48846f9da06eac56a20bd9239b2821648f1e645ad17d62bb7193361f962d7`.

Log [Neuron 41571432561](https://github.com/Abeel87/tenis-ai/actions/runs/41571432561),
job `125704975877`, potwierdza 26 rozliczeń i zero par już na etapie `evaluate`,
przed publikacją `37d1efa`. Nie przypisujemy tego historycznego zera wyłącznie
błędowi publishera. Wcześniejsze zero bieżącego modelu w PR #573 dotyczyło
jeszcze młodszej próby z 2 listopada.

## Dwie dostępne pary

| Dokładny fixture | Prognoza AutoLearn | Prognoza Neuronu | Start | Zapis wyniku |
| --- | --- | --- | --- | --- |
| `id:214269`, Jake Delaney – Keegan Smith | 02.11 17:45:30Z | 02.11 18:33:27Z | 03.11 02:00Z | 03.11 07:04:56Z |
| `id:214271`, Yuta Shimizu – Stefanos Sakellaridis | 02.11 17:45:30Z | 02.11 18:33:27Z | 03.11 03:30Z | 03.11 07:04:56Z |

Baseline zapisano przed meczami, a wyniki pojawiły się po poprzednim przebiegu
Neuronu. Z 114797 wierszy ledgeru 3306 zawiera rzeczywisty nowy ensemble, w tym
154 rekordy rynku zwycięzcy meczu. To nie 3306 ani 154 niezależne rozliczone pary.
W obecnej kohorcie 32 mecze mają dokładnie pasujący zamrożony baseline: dwa są
rozliczone, 27 czeka na terminalną historię, trzy blokuje konflikt terminu.

Oba modele mają na tych samych dwóch parach accuracy 0%; Brier Neuronu wynosi
0.433658, a AutoLearn 0.291196. **N=2 nie pozwala wnioskować o przewadze ani
gotowości produkcyjnej.** Accuracy 64,15% z treningowego TEST i wynik Elo nie są
wynikiem tego prospektywnego porównania. Oceny na 28 i na dwóch meczach nie mogą
być bezpośrednio porównywane jako ranking modeli.

## Co pozostaje nierozliczone

Podział po ponownym odczycie historii, względem 03.11 08:13:28Z:

| Powód | Liczba | Start jeszcze w przyszłości | Start już minął |
| --- | ---: | ---: | ---: |
| Brak dokładnego rekordu w kanonicznej historii | 65 | 39 | 26 |
| Niezgodny termin przy tym samym ID | 78 | 35 | 43 |
| Historia jeszcze bez terminalnego wyniku | 29 | 28 | 1 |

Dziewięć konfliktów terminu ma terminalny rekord historii (osiem completed,
jeden retired). Nie wolno uznać ich za poprawne rozliczenia bez dokładnego
dowodu zgodności terminu. Pozostałe konflikty nie mają terminalnego wyniku.
Brak rekordu nie jest dowodem porażki ani potwierdzeniem, że wystarczy poczekać.
Kanoniczna historia obejmuje 2500 rekordów i powstaje z własnej populacji
model-ready; Neuron może punktować inną populację. Obecna poprawka nie rozszerza
tej historii ani nie zmienia jej właściciela.

## Rzetelność i chronologia

- Neuron zamraża pierwszy snapshot przed startem wraz z modelem, cechami,
  czasem i hashem. Zmiana zamrożonej prognozy narusza walidację.
- `settle_predictions` deleguje do kanonicznych `_history_index` /
  `_settlement_fact` i `signal_settlement.settle_signal_live`. Wymagane są
  dokładne ID, termin, uczestnicy, terminalny status, źródło, wersja i czas.
  Przyszły lub niepełny wynik pozostaje N/D.
- `_production_index` przyjmuje tylko rzeczywisty, poprawnie opisany,
  zamrożony przed startem ensemble AutoLearn dla dokładnej selekcji zwycięzcy.
  Brak dawnego ensemble pozostaje brakiem; nie liczymy go dzisiejszymi wagami.
- Oba modele dostają ten sam wynik tej samej selekcji. Druga strona meczu ma
  odpowiednio odwrócony target i probability. Powtórne snapshoty/model versions
  nie powiększają liczby niezależnych fixture; bieżąca wersja ma osobną kohortę.
- Jest to porównanie pierwszych niezależnie zapisanych prognoz przedmeczowych,
  **nie identycznego momentu decyzji**. Różnica czasu zapisu jest jawna. VOID i
  nierozliczone rekordy są wykluczone z obu metryk; próba i brakujące baseline
  pozostają widoczne. Brak zmiany metod treningu, progów lub promocji.

## Dokładny zakres poprawki

1. `scripts/publish_neuron_shadow.py`: jednorazowo czyta i waliduje odtworzony
   ledger AutoLearn z tego samego przebiegu. Podaje go istniejącemu
   `summarize_predictions` również po scaleniu równoległych wierszy Neuronu.
   Retry zachowuje ten sam baseline; brak/uszkodzenie pliku blokuje publikację.
   Zmiana `backend/prediction_ledger_shadow.py` na main blokuje publikację
   raportu ze starego kontraktu. Publisher nie zapisuje ledgeru AutoLearn.
2. `tests/test_neuron_publication.py`: regresje integracyjne na lokalnych
   repozytoriach Git, w tym utrzymanie metryk, równoległe dopisanie prognoz,
   ponowienie push, brak/uszkodzenie baseline, legacy bez ensemble, zapis po
   starcie, obcy fixture/termin/selekcja i zmiana kontraktu.
3. Rejestr modeli, architektura i LIVE CHECKPOINT oraz niniejszy audyt JSON/MD.

Łącznie siedem plików. Jedyny zmieniony plik wykonywalny to istniejący
publisher; bez alternatywnej ścieżki. Bez zmian probability, treningu, modeli,
settlementu, workflowów, UI, historycznych snapshotów i realnych zakładów.

## Walidacja i zatwierdzenie

Przed poprawką: sześć regresji zawiodło, pięć testów przeszło. Po poprawce:
początkowy pakiet Neuronu 58/58, rozszerzony pakiet porównań 85/85; dwa istniejące
ostrzeżenia NumPy z pustej próbki testowej. Pełna regresja na zależnościach z
`requirements.lock`: **1905/1905 passed w 99,76 s**, te same dwa ostrzeżenia.
Dodatkowy replay na rzeczywistych wejściach, opublikowany wyłącznie do lokalnego
bare Git, zachował pełny raport evaluatora: 28 rozliczeń i dwie pary. Wszystkie
1370 zamrożonych snapshotów zachowało treść; ledger AutoLearn nie został
opublikowany. Lokalne kontrole UI static/runtime/readiness/time/decision przeszły.
Dla kodu `82885fc` przeszły na GitHubie Neuron, browser/security, dependencies,
CodeQL i audyty źródeł. Health był w toku w chwili zapisania tego potwierdzenia;
aktualny stan wszystkich kontroli: [PR #574](https://github.com/Abeel87/tenis-ai/pull/574/checks).

Nie wykonano merge ani wdrożenia. Draft [PR #574](https://github.com/Abeel87/tenis-ai/pull/574)
oczekuje na decyzję właściciela. Po zgodzie wymagane są aktualny main,
zielone CI i zwykła weryfikacja SHADOW. Nie zmieniać produkcyjnych probability
ani nie promować Neuronu na podstawie tej małej próby.
