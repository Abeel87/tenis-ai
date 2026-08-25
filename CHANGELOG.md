# Changelog

## v8.5.2 — Quality Lock

- twarde progi generatora: Balanced hard floor = 72, Stable hard floor = 74, Strong hard floor = 80, Experimental hard floor = 62;
- brak forced fill: polityka `quality_lock_no_forced_fill_v852` nie obniża progów ani nie dopchuje słabszych sygnałów — przy braku wystarczająco dobrych pozycji generator zwraca mniej spotkań;
- Tracking Governor: konserwatywny mechanizm korygujący wagi na podstawie historycznie rozliczonego tracking data (`previous_tracking`) przy próbce `selected_n >= 100`;
- pozostawienie Dynamic Weights v8.4D oraz istniejących mechanizmów bez zmian;
- przemianowanie telemetrii z `Generator AI` na `Ensemble selector proxy`, informującej czytelnie w UI, że jest to proxy selektora Ensemble, a nie pojedyncze modyfikacje użytkownika w Generatorze AI UI.

## v8.0 — Clean Core / Post-Match Center

- jedna kanoniczna Historia ładowana przez `clean-core-v80.js`;
- krótka lista meczów w Historii zamiast rozwijania wszystkich sygnałów;
- kliknięcie meczu otwiera pełny Raport po meczu;
- osobne sekcje: Co weszło, Co nie weszło, Modele, Adaptive Learning;
- bezpośrednie wykorzystanie `adaptive_review_v79` z backendu;
- pokazanie learning-only dla Consensus, Early Hold, Serve/Return, Form i Surface;
- polskie statusy TRAFIONY / NIETRAFIONY / OCZEKUJE;
- kompaktowy status Adaptive i kompaktowy wybór modeli;
- usunięty hardcoded nagłówek `v7.8D` z warstwy Project UI;
- usunięty stary renderer `history-days-v732`;
- usunięte stare instalatory, wersyjne README, stare paczki ZIP i duplikaty dokumentacji z root repo;
- uproszczona stopka aplikacji;
- nowy health-check pilnujący powrotu legacy śmieci i konfliktów wersji;
- backend modeli, settlement, Shadow Lab, PBP, Calibration i Adaptive pozostają bez zmian matematycznych.

## v7.9B

Adaptive Learning End-to-End: specialist learning, status działania, korekty SHADOW i analiza pomeczowa w danych.

## v7.8D

Calibration Guard i rozdzielenie score modelu od historycznej skuteczności.

Pełna historia starszych zmian pozostaje w historii Git.
