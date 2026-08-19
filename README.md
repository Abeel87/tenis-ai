# 🎾 Tenis AI — Early Hold v0.1

Darmowa PWA do analizy meczów na telefonie i Windowsie. Backend w Pythonie pobiera darmową historię ATP/WTA/Challenger, liczy ostatnie 5+5 meczów i publikuje gotowy JSON do lekkiej strony PWA.

## Co działa

- ATP / WTA / Challenger
- ostatnie 5 meczów = wyższa waga, wcześniejsze 5 = niższa
- bonus za tę samą nawierzchnię
- hold%, break%, serve points won, forma, 1st-set win, 1st-set over 8.5
- ocena 0–100 dla `Over 8.5 w 1. secie` i `wygrana 1. seta`
- **`prowadzi po 6 gemach = N/D`**, dopóki nie ma wiarygodnej historii game-by-game
- jakość danych HIGH / MEDIUM / LOW
- PWA: na Androidzie można wybrać „Dodaj do ekranu głównego”

## Darmowe źródła

Historia/statystyki: TennisMyLife CSV (roczniki + bieżące turnieje) (`stats.tennismylife.org`), bez klucza. Nadchodzące mecze: Live Tennis API FREE — wymaga darmowego klucza, bez karty.

## Uruchomienie Windows

Najprościej: kliknij `start_windows.bat`. Pierwsze uruchomienie samo utworzy środowisko i doinstaluje wymagane biblioteki.

Ręcznie:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python backend\update.py
python -m http.server 8080 -d frontend
```

Otwórz `http://localhost:8080`.

Bez klucza wpisz mecze do `data/manual_matches.csv` i ponownie uruchom `python backend/update.py`.

## Automatycznie na telefon + GitHub Pages

1. Utwórz nowe publiczne repozytorium na GitHubie i wrzuć zawartość tego katalogu.
2. Załóż darmowy klucz Live Tennis API.
3. GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**.
4. Nazwa: `LIVE_TENNIS_API_KEY`, wartość: Twój darmowy klucz.
5. Settings → Pages → Source: **GitHub Actions**.
6. Actions → workflow `Update tennis data and deploy Pages` → **Run workflow**.
7. Po wdrożeniu otwórz adres Pages na Androidzie i wybierz **Dodaj do ekranu głównego**.

Workflow aktualizuje dane 4 razy dziennie. Limit darmowego Live Tennis API wynosi obecnie 100 żądań/dzień, więc ten harmonogram jest oszczędny.

## Ważne

Wyniki 0–100 są **rankingiem modelu**, a nie gwarantowanym prawdopodobieństwem. Exact Early Hold (1./2./3. własny gem, prowadzenie po 6) nie jest liczony z samych statystyk całomeczowych. To celowo: aplikacja ma pokazać N/D zamiast wymyślać dane.
