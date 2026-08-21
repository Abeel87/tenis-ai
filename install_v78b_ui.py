from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI = ROOT / "frontend" / "ui-v751.js"
INDEX = ROOT / "frontend" / "index.html"
SW = ROOT / "frontend" / "sw.js"


def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"OK already: {label}")
        return
    if old not in text:
        raise SystemExit(f"STOP: anchor not found for {label}: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"PATCHED: {label}")


joint_fn = r'''  function jointBuilder78b(m){
    const j=m.joint_builder_v78b;
    if(!j){
      return `<details class="p751-acc"><summary><div><span>🧩</span><b>Joint Builder v7.8B</b><small>wspólna kombinacja 1. seta</small></div><em>N/D</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">Brak jeszcze wyniku Joint Buildera w tym rekordzie. Po kolejnym przebiegu danych zostanie policzony automatycznie.</p></div></details>`;
    }
    if(j.status!=='READY'){
      const why=j.reason||((j.validation_errors||[]).join(' · '))||j.status||'N/D';
      return `<details class="p751-acc"><summary><div><span>🧩</span><b>Joint Builder v7.8B</b><small>wspólna kombinacja 1. seta</small></div><em>${esc(j.status||'N/D')}</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">N/D: ${esc(why)}. Nie zgadujemy wyniku bez modelu serwisowego i pełnego rozkładu.</p></div></details>`;
    }
    const b=j.best||{},p=b.player||'—';
    const r=(j.p1?.player===p?j.p1:j.p2?.player===p?j.p2:null)||{};
    const dep=num(b.dependency_ratio),joint=num(b.joint_all_3),naive=num(b.naive_independent);
    return `<details class="p751-acc ready" open>
      <summary><div><span>🧩</span><b>Joint Builder v7.8B</b><small>3 zdarzenia liczone z tej samej ścieżki seta</small></div><em>${joint==null?'N/D':pc(joint)}</em><i>⌄</i></summary>
      <div class="p751-acc-body">
        <p class="p751-note"><b>${esc(p)}</b>: prowadzi po 6 gemach + OVER 8.5 w 1. secie + wygrywa 1. set. To jest wspólne prawdopodobieństwo, a nie iloczyn trzech niezależnych procentów.</p>
        ${marketRow('Kombinacja 3/3',joint==null?'N/D':pc(joint),naive==null?'':`naiwne mnożenie ${pc(naive)}`,false)}
        ${marketRow('1 · Prowadzi po 6 gemach',`${esc(p)} ${pc(r.lead_after_6)}`,'',num(r.lead_after_6)>=72)}
        ${marketRow('2 · OVER 8.5 · 1. set',pc(r.over_8_5_set1),'',num(r.over_8_5_set1)>=72)}
        ${marketRow('3 · Wygrywa 1. set',`${esc(p)} ${pc(r.win_set1)}`,'',num(r.win_set1)>=72)}
        ${dep!=null?marketRow('Wpływ zależności',`×${dep.toFixed(2)}`,dep>1?'zdarzenia wzajemnie się wzmacniają':'zależność nie podbija kombinacji',dep>=1.25):''}
        <p class="p751-note">Joint zawsze musi być ≤ każdej składowej. Integralność v7.8A sprawdza ten warunek automatycznie.</p>
      </div>
    </details>`;
  }

'''

replace_once(
    UI,
    "  function stats(m){\n",
    joint_fn + "  function stats(m){\n",
    "Joint Builder section",
)
replace_once(
    UI,
    '${coreMarkets(m)}${stats(m)}${analyticsPro76(m)}',
    '${coreMarkets(m)}${jointBuilder78b(m)}${stats(m)}${analyticsPro76(m)}',
    "Joint Builder in match detail",
)
replace_once(
    UI,
    "<span>${m.early_hold_v7?.ready?'🧬 PBP OK':'🧬 PBP N/D'}</span>\n        <span>DANE",
    "<span>${m.early_hold_v7?.ready?'🧬 PBP OK':'🧬 PBP N/D'}</span>\n        <span>${m.joint_builder_v78b?.status==='READY'?`🧩 Joint ${pc(m.joint_builder_v78b.best?.joint_all_3)}`:'🧩 Joint N/D'}</span>\n        <span>DANE",
    "Joint Builder card badge",
)
replace_once(
    UI,
    "document.querySelector('.brand-copy p').textContent='Tenis AI v7.8A · Integrity Guard'",
    "document.querySelector('.brand-copy p').textContent='Tenis AI v7.8B · Joint Builder'",
    "UI brand version",
)

replace_once(INDEX, "Tenis AI v7.8A · Integrity Guard", "Tenis AI v7.8B · Joint Builder", "index brand version")
replace_once(INDEX, '<span class="model-lab-badge">LAB v7.8A</span>', '<span class="model-lab-badge">LAB v7.8B</span>', "model badge version")
replace_once(
    INDEX,
    '<div>v7.8A: Integrity Guard',
    '<div>v7.8B: Joint Builder — prowadzenie po 6 gemach + OVER 8.5 1S + zwycięzca 1S liczone wspólnie z jednej dystrybucji ścieżek seta; pokazuje też różnicę względem naiwnego mnożenia. v7.8A: Integrity Guard',
    "footer v7.8B note",
)
replace_once(SW, "const C='tenis-ai-v78a-integrity-guard';", "const C='tenis-ai-v78b-joint-builder';", "PWA cache bump")

print("v7.8B UI installer complete")
