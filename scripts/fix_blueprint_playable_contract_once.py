from pathlib import Path
import re

p = Path('frontend/playable-ui.js')
s = p.read_text(encoding='utf-8')
pattern = r"function patchTopStrip\(\)\{.*?\n\}\nfunction patchSignalPage\(\)"
replacement = r'''function patchTopStrip(){
  // Keep the RAW/PLAYABLE separation contract available for technical mode,
  // but the agreed simple product must never render a second Top strip.
  if(document.documentElement.dataset.tenisProduct==='blueprint'&&document.documentElement.dataset.tenisUiMode!=='technical'){
    document.querySelector('#app [data-playable-top-v917="1"]')?.remove();
    return;
  }
  // Top SUPERBET must be derived from the exact set that Match Browser leaves
  // visible after its mode / data / surface filters, never from hidden cards.
  const cards=[...document.querySelectorAll('#app .match-group:not([hidden]) .p751-match-card[data-p751-open]:not([hidden])')];
  const picks=cards.map(card=>{
    const raw=card.getAttribute('data-p751-open')||'';
    const match=findMatch(raw);
    const signal=match?playableSignals(match,1)[0]:null;
    return match&&signal&&valueOf(signal)>=72?{match,signal,raw}:null;
  }).filter(Boolean).sort((a,b)=>valueOf(b.signal)-valueOf(a.signal)).slice(0,3);
  const old=document.querySelector('#app [data-playable-top-v917="1"]');
  if(!picks.length){old?.remove();return}
  const hash=picks.map(x=>`${x.raw}:${signature(x.signal)}:${valueOf(x.signal)}`).join('|');
  if(old?.dataset?.v917Hash===hash)return;
  const wrap=document.createElement('div');
  wrap.innerHTML=topBarHtml(picks);
  const fresh=wrap.firstElementChild;
  fresh.dataset.v917Hash=hash;
  if(old)old.replaceWith(fresh);
  else{
    const rawTop=document.querySelector('#app .signal-spotlight:not([data-playable-top-v917])');
    const focus=document.querySelector('#app .match-browser-head');
    if(rawTop)rawTop.insertAdjacentElement('afterend',fresh);
    else if(focus)focus.insertAdjacentElement('afterend',fresh);
    else document.querySelector('#app')?.prepend(fresh);
  }
}
function patchSignalPage()'''
out, count = re.subn(pattern, replacement, s, count=1, flags=re.S)
if count != 1:
    raise SystemExit(f'patchTopStrip replacement count={count}')
p.write_text(out, encoding='utf-8')
