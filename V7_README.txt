Tenis AI v7.0 — BASIC Point-by-Point Early Hold

Co zmienia:
- osobna warstwa Early Hold oparta na Live Tennis API BASIC point-by-point,
- prawdziwe 1., 2. i 3. własne gemy serwisowe w 1. secie,
- minimum 5 wiarygodnych meczów albo EHS = N/D,
- ostatnie 5 meczów ma większą wagę; kolejne do 8 mniejszą,
- ta sama nawierzchnia ma większą wagę,
- 1:1 po 2, 2:2 po 4, 3:3 po 6 i sekwencja 1:1→2:2→3:3,
- PBP-aware wynik po 1/2/4/6 gemach,
- score_lead_after6,
- score_joint_builder liczony wspólnie w symulacji (nie jako iloczyn),
- cache PBP w data/cache/pbp_v7,
- limit API pilnuje dziennej rezerwy,
- UI pokazuje EHS i źródło danych,
- testy uruchamiają się w GitHub Actions przed wdrożeniem.

Pełne rynki meczu nadal pozostają bazowym Adaptive v0.5/BO3.
v7.0 ulepsza przede wszystkim specjalistę Early Hold i rynki początku 1. seta.
