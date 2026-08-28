# Audyt Tenis AI — v9.1.9

Data: 28.08.2026. Punkt wyjścia: PR #26 (`160d9325d6092c81df760a348a761237b3d9e91b`).

**Status: poprawki w kodzie do przeglądu. Nie jest to potwierdzenie wdrożenia ani pełny test penetracyjny.**
PR #26 pozostawał otwarty podczas audytu; obserwacje przeglądarkowe dotyczą wcześniejszej wersji produkcyjnej.

## Zachowane dane i kontrakty

Nie zmieniono żadnego zapisanego JSON-a, historii, prognozy, wyniku rozliczenia ani wagi modelu. Nie wykonano zapisu w produkcyjnej bazie Supabase. SHADOW pozostaje bez wpływu na PROD. Brak danych nie jest zastępowany wyliczoną na potrzeby UI liczbą. Dodane pole `source_max_age_hours` opisuje dotychczasową politykę ważności oferty; nie zmienia oceny modelowej. Harmonogram płatnego API i limit 4000 zapytań miesięcznie pozostają bez zmian.

## Zakres kontroli

| Obszar | Sprawdzone | Ograniczenia |
| --- | --- | --- |
| Mecze i sygnały | Kod filtrów, statusy, zegar, TOP, Centrum Decyzji, oferta operatora; produkcyjny ekran meczów | Brak porównania każdego meczu z niezależnym źródłem wyników na żywo |
| Scenariusze i Symfonia | Produkcyjna nawigacja, lista i pełna kompozycja; testy filtra, linii, wygaśnięcia w otwartym panelu | Nie tworzono scenariuszy na koncie użytkownika |
| SHADOW i Odrzucone | Produkcyjne ekrany, oddzielenie od PROD, statusy i zaokrąglenia; regresja SHADOW | Nie zmieniano historycznych prognoz testowych |
| Historia i statystyki | Widok historii, rozliczenia, zakres baza/FINAL, kalibracja, próbki i Brier; istniejące audyty spójności | Zachowano historyczny czas zamrożenia prognozy, nawet gdy później zmienił się plan meczu |
| Profil i społeczność | Niezalogowane wejście, formularz, CAPTCHA; katalog polityk, przywilejów i funkcji Supabase | Bez logowania jako użytkownik/admin, bez wysyłania wiadomości i kasowania kont |
| Wygląd | Produkcyjny desktop, kod responsywności, etykiety, hierarchia i duplikaty | Nowej gałęzi nie uruchomiono w przeglądarce: pliki lokalnego podglądu nie były widoczne w środowisku przeglądarki. Telefon wymaga odbioru po wdrożeniu |

## Naprawione w tej gałęzi

1. **Ważność Superbet:** znacznik `VERIFIED` nie wystarcza. UI sprawdza czas źródła i maksymalny wiek; domyślnie 108 minut zgodnie z aktywną polityką v9.1.3. Przyszły/nieprawidłowy znacznik, zawieszenie i nieaktualny mecz blokują PLAYABLE. Backend także odrzuca czas źródła z przyszłości.
2. **Wygasanie podczas otwarcia aplikacji:** istniejący zegar 15 s sprawdza karty, otwarte Centrum Decyzji, miniatury, pełną Symfonię i SHADOW. Powrót do karty przeglądarki również wywołuje kontrolę. Nie powstaje nowy interwał ani dodatkowe zapytanie do płatnego API.
3. **Pełna lista Symfonii:** usunięto powrót do wszystkich historycznych wierszy, gdy brak meczów z bieżącego dnia. Każda kompozycja musi odpowiadać aktualnemu meczowi i dokładnym selekcjom operatora. Brak wyniku wyświetla N/D. Godzina zawiera datę, aby nie mylić jutra z dzisiaj.
4. **SHADOW:** wspólna kontrola czasu/oferty i wspólne etykiety statusu; brak domyślnego „PRZED MECZEM” dla starych danych. Dane raportu pozostają nienaruszone.
5. **Filtr 80+:** ocenia aktualny sygnał PLAYABLE, nie niezweryfikowane maksimum RAW.
6. **Statystyki:** trend, kalibracja i rynki bazowe są wyraźnie opisane jako baza. FINAL ma własny zakres i wykres. Raport Superbet pokazuje datę wygenerowania i informację, że nie jest stanem oferty na żywo. Nie zmieniono liczb ani metod obliczeń.
7. **Etykiety i porządki:** jedna wersja wydania z `app-meta.js`; usunięto nadpisywanie starą wersją oraz powtórzoną wersję w nagłówku statystyk. „Widok sygnałów” na stronie statystyk zmieniono na „Widok statystyk”. Usunięto powtórzony skrót „Odrzucone”; zakładka i jej dane pozostają.
8. **Menu telefonu:** osiem pozycji w dwóch rzędach do szerokości 600 px, etykiety 10 px i cele dotykowe minimum 44 px zamiast etykiet 5,5–6 px. Uwzględniono dolny odstęp i bezpieczny obszar urządzenia. Wymaga sprawdzenia wizualnego na telefonie.
9. **Odrzucone sygnały:** zachowano jedną cyfrę po przecinku, żeby 71,9 nie wyglądało jak zielone 72/100; lista nie rozpoczyna się od przeterminowanych meczów.
10. **CAPTCHA:** równoległe inicjalizacje po załadowaniu skryptu nie montują kilku widgetów w tym samym kontenerze. Test odtwarza wyścig bez wysyłania formularza.

## Supabase — ustalenia i migracja do osobnego odbioru

Wszystkie 10 tabel publicznych mają RLS. Dla `profiles` konto `authenticated` może aktualizować wyłącznie `avatar_url`, `bio`, `last_seen_at`; nie ma szerokiego UPDATE. Sprawdzone funkcje administracyjne kontrolują `auth.uid()` i rolę zapisaną w bazie. Nie stwierdzono na tej podstawie możliwości samodzielnego nadania roli admina.

**Luka w politykach interakcji:** `comments own insert` i `likes own insert` sprawdzały członkostwo i autora, lecz nie widoczność wskazanego kuponu. `likes community read` pozwalała członkowi czytać polubienia także prywatnych kuponów. Przy znajomości identyfikatora pozwalało to na interakcję z niedostępnym kuponem. To ustalenie z polityk, nie wynik wykonanego ataku na dane użytkownika.

Przygotowano migrację `supabase/migrations/20260828125221_restrict_private_coupon_interactions.sql`, z nazwą wygenerowaną przez CLI. Zmienia tylko trzy polityki; nie usuwa ani nie aktualizuje wierszy. **Nie zastosowano jej w produkcji i nie wykonano testu RLS na dwóch kontach.** Migracja nie jest uruchamiana przez wdrożenie GitHub Pages.

Przed zastosowaniem należy sprawdzić na środowisku testowym:

| Rola / zasób | Odczyt polubień | Dodanie komentarza/polubienia |
| --- | --- | --- |
| Niezalogowany | zabroniony | zabronione |
| Członek, publiczny kupon | dozwolony | dozwolone wyłącznie z własnym user_id |
| Członek A, własny prywatny kupon | dozwolony | dozwolone |
| Członek B, prywatny kupon A | zabroniony | zabronione, także przy znajomości ID |
| Konto bez dostępu / zablokowane | zabroniony | zabronione |

Doradca bezpieczeństwa zgłosił ponadto:

- 15 ostrzeżeń dla funkcji SECURITY DEFINER dostępnych roli `anon` i 15 dla `authenticated`. To nie dowód obejścia kontroli wewnętrznych. Warto ograniczyć niepotrzebne EXECUTE, zachowując publiczne funkcje sprawdzania nicka/statystyk i funkcje wymagane przez polityki. [Opis i zalecenia](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable).
- Wyłączoną ochronę przed ujawnionymi hasłami. [Konfiguracja](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). Nie zmieniano ustawień Auth.
- Dwie informacje o RLS bez polityk (`app_migrations`, `community_admin_audit`). Tabele nie są przeznaczone do bezpośredniego odczytu przez zwykłego klienta; nie dodawano publicznych polityk tylko po to, aby usunąć komunikat.

## Weryfikacja

`python -m pytest -q --tb=short`: **451 passed**, 148,80 s. Testy obejmują kod aplikacji; nie stanowią testu wdrożenia SQL ani przeglądarkowego odbioru nowej gałęzi.

Dodatkowo wykonano:

- kontrolę składni zmienionych JS oraz `git diff --check`;
- Project Health: PASS, 0 błędów i 2 istniejące ostrzeżenia o liczbie plików (68 JS, 47 CSS);
- Runtime/UI Guard, Decision Center Guard, Full App Coherence Guard, SHADOW Signal Center Guard: PASS;
- Audit consistency: PASS — 285 kandydatów RAW/FINAL, zamknięte warstwy, kalibracja tej samej próbki;
- audyt historycznych odstępstw 11.5: PASS — dwie pozostałe pozycje dotyczą retired/nonstandard, zachowane zgodnie z dotychczasową polityką;
- potwierdzenie, że diff nie obejmuje żadnego pliku danych JSON.

Testy regresji obejmują granicę 108 minut, przyszły/brakujący czas źródła, dokładną linię rynku, brak wyniku, zakończony mecz, brak meczu w bieżącym feedzie, zachowanie danych wejściowych, wygaśnięcie w otwartej Symfonii i SHADOW oraz równoległą inicjalizację CAPTCHA.

## Odbiór po wdrożeniu i dalsze ryzyka

- Scalić PR #26 przed tą gałęzią albo uwzględnić jego zmiany wraz z nią. Potwierdzić zielone GitHub Actions i wersję v9.1.9 po wdrożeniu.
- Telefon: 320/360/390/430 px, portret/poziom, zoom 200%, menu, długie nazwiska, otwarte panele i klawiatura. Ten etap nie jest zaliczony na podstawie samych testów kodu.
- Pozostawić otwartą aplikację do wygaśnięcia oferty; sprawdzić N/D zamiast starego PLAYABLE oraz powrót po świeżym pobraniu danych.
- Przeprowadzić scenariusze RLS powyżej i dopiero potem zastosować migrację. Włączenie ochrony haseł i ograniczenie EXECUTE wymagają osobnego sprawdzenia zgodności.
- 68 skryptów i 47 arkuszy stylów nadal tworzy trudny do utrzymania układ nadpisań. Nie usuwano masowo plików nadal ładowanych przez aplikację. Dalsze scalanie rendererów wymaga testów wizualnych każdej zakładki.
- Nie potwierdzono wszystkich funkcji po zalogowaniu, dostarczania e-maili, panelu administratora, rzeczywistych płatnych zapytań, zgodności każdego wyniku z niezależnym dostawcą ani pełnej dostępności WCAG.
