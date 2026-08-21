from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
F=ROOT/"frontend"
B=ROOT/"backend"

# 1) BACKEND: 1:1 / 2:2 / 3:3 -> czyste holdy vs ścieżki z przełamaniami.
pbp=B/"pbp_enrich.py"
s=pbp.read_text(encoding="utf-8")

if "def _balanced_path_breakdown(" not in s:
    marker="def _tb_p1(base1: float, base2: float) -> float:\n"
    helper='''def _balanced_path_breakdown(seq1, seq2, base1, base2, games: int) -> dict:
    # total = all paths ending at 1:1 / 2:2 / 3:3.
    # clean_holds = every service game is held.
    # with_breaks = remaining balanced paths containing at least one break.
    # For 1:1 after two games, with_breaks is exactly BREAK-BREAK.
    if games not in (2, 4, 6):
        raise ValueError("games must be 2, 4 or 6")
    target = games // 2
    first = _states_for_n(seq1, seq2, base1, base2, games, True)
    second = _states_for_n(seq1, seq2, base1, base2, games, False)
    total = 0.5 * (first.get((target, target), 0.0) + second.get((target, target), 0.0))

    clean = 1.0
    for service_no in range(1, target + 1):
        clean *= _game_hold(seq1, base1, service_no)
        clean *= _game_hold(seq2, base2, service_no)

    clean = _clamp(clean, 0.0, total)
    with_breaks = max(0.0, total - clean)
    return {
        "games": games,
        "state": f"{target}:{target}",
        "total": round(100.0 * total, 1),
        "clean_holds": round(100.0 * clean, 1),
        "with_breaks": round(100.0 * with_breaks, 1),
        "break_break": round(100.0 * with_breaks, 1) if games == 2 else None,
    }


'''
    if marker not in s:
        raise SystemExit("pbp_enrich.py: brak markera _tb_p1")
    s=s.replace(marker,helper+marker,1)

if "checkpoint_breakdown = {" not in s:
    marker='''    state_probs = {str(n): _state_probs(seq1, seq2, blended1, blended2, n) for n in (1, 2, 4, 6)}
    terminal_raw = _set_sim(seq1, seq2, blended1, blended2)
'''
    repl='''    state_probs = {str(n): _state_probs(seq1, seq2, blended1, blended2, n) for n in (1, 2, 4, 6)}
    checkpoint_breakdown = {
        str(n): _balanced_path_breakdown(seq1, seq2, blended1, blended2, n)
        for n in (2, 4, 6)
    }
    terminal_raw = _set_sim(seq1, seq2, blended1, blended2)
'''
    if marker not in s:
        raise SystemExit("pbp_enrich.py: brak markera state_probs")
    s=s.replace(marker,repl,1)

if '"checkpoint_breakdown": checkpoint_breakdown' not in s:
    marker='''            "balanced_after6": state_probs["6"].get("3:3"),
        }
    )
'''
    repl='''            "balanced_after6": state_probs["6"].get("3:3"),
            "checkpoint_breakdown": checkpoint_breakdown,
            "comparison_note": "Balanced checkpoints split into clean-hold paths vs paths containing breaks.",
            "first_server_assumption": "50/50 when pre-match first server is unknown",
        }
    )
'''
    if marker not in s:
        raise SystemExit("pbp_enrich.py: brak markera eh.update")
    s=s.replace(marker,repl,1)

pbp.write_text(s,encoding="utf-8")

# 2) FRONTEND assets są już po rozpakowaniu ZIP w frontend/.
for name in ("early-hold-paths-v771.js","early-hold-paths-v771.css"):
    if not (F/name).exists():
        raise SystemExit(f"Brak {name}")

idx=F/"index.html"
x=idx.read_text(encoding="utf-8")

if "early-hold-paths-v771.css" not in x:
    marker='<link rel="stylesheet" href="early-hold-v7.css">'
    if marker not in x:
        raise SystemExit("index.html: brak early-hold-v7.css")
    x=x.replace(marker,marker+'\n  <link rel="stylesheet" href="early-hold-paths-v771.css">',1)

if "early-hold-paths-v771.js" not in x:
    marker='  <script src="performance-center-v77.js"></script>'
    if marker not in x:
        marker='  <script src="restore-v762.js"></script>'
    if marker not in x:
        raise SystemExit("index.html: brak markera końca JS")
    x=x.replace(marker,marker+'\n  <script src="early-hold-paths-v771.js"></script>',1)

x=re.sub(r'<p>Tenis AI v[^<]+</p>','<p>Tenis AI v7.7.1 · Hold Paths</p>',x,count=1)
x=re.sub(r'<span class="model-lab-badge">LAB v[^<]+</span>','<span class="model-lab-badge">LAB v7.7.1</span>',x,count=1)
if "v7.7.1: Hold Paths" not in x:
    x=x.replace(
        "<div>v7.7:",
        "<div>v7.7.1: Hold Paths — DANE ZAWODNIKA vs PORÓWNANIE MECZU oraz rozbicie 1:1/2:2/3:3 na czyste holdy i ścieżki z przełamaniami. v7.7:",
        1
    )
idx.write_text(x,encoding="utf-8")

# Stary visual shell nie może cofnąć widocznej wersji.
ui=F/"ui-v751.js"
u=ui.read_text(encoding="utf-8")
u=re.sub(
    r"document\.querySelector\('\.brand-copy p'\)\.textContent='Tenis AI v[^']+'",
    "document.querySelector('.brand-copy p').textContent='Tenis AI v7.7.1 · Hold Paths'",
    u,count=1
)
ui.write_text(u,encoding="utf-8")

# PWA cache.
sw=F/"sw.js"
w=sw.read_text(encoding="utf-8")
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v771-hold-paths';",w,count=1)
for asset,anchor in [
    ("early-hold-paths-v771.css","early-hold-v7.css"),
    ("early-hold-paths-v771.js","restore-v762.js"),
]:
    if f"'{asset}'" not in w:
        if f"'{anchor}'" not in w:
            raise SystemExit(f"sw.js: brak {anchor}")
        w=w.replace(f"'{anchor}'",f"'{anchor}','{asset}'",1)
sw.write_text(w,encoding="utf-8")

print("Tenis AI v7.7.1 Hold Paths: OK")
