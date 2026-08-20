/* Tenis AI v7.0 — point-by-point Early Hold panel */
(() => {
  if (typeof renderMatchDetail !== 'function') return;
  const baseRender = renderMatchDetail;
  const p = x => x == null ? 'N/D' : `${Number(x).toFixed(1).replace('.0','')}%`;
  const esc7 = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function playerCol(x){
    if(!x) return '';
    return `<div class="eh7-player">
      <div class="eh7-name"><b>${esc7(x.player||'—')}</b><span class="${x.ready?'ready':'nd'}">${x.ready?'PBP OK':'N/D'}</span></div>
      <div class="eh7-kpis">
        <span>EHS <b>${x.ehs==null?'N/D':Number(x.ehs).toFixed(1)+'/100'}</b></span>
        <span>1. serwisowy <b>${p(x.hold1)}</b></span>
        <span>2. serwisowy <b>${p(x.hold2)}</b></span>
        <span>3. serwisowy <b>${p(x.hold3)}</b></span>
        <span>1:1 po 2 <b>${p(x.after2_11)}</b></span>
        <span>2:2 po 4 <b>${p(x.after4_22)}</b></span>
        <span>3:3 po 6 <b>${p(x.after6_33)}</b></span>
      </div>
      <small>${x.matches||0} wiarygodnych meczów · nawierzchnia ${x.surface_matches||0}</small>
    </div>`;
  }

  function box(m){
    const e=m.early_hold_v7;
    if(!e) return '';
    const main=e.ready ? `
      <div class="eh7-top">
        <span>🎯 Pick 1. seta <b>${esc7(m.pick_first_set_early||'—')} · ${p(m.score_first_set_early)}</b></span>
        <span>Prowadzi po 6 <b>${p(m.score_lead_after6)}</b></span>
        <span>Joint Builder* <b>${p(m.score_joint_builder)}</b></span>
      </div>` : `<div class="eh7-nd">Brak min. 5 wiarygodnych point-by-point dla obu zawodników — EHS pozostaje N/D i model nie zgaduje.</div>`;
    return `<section class="eh7-box">
      <div class="eh7-head"><div><b>🧬 Early Hold v7 · BASIC PBP</b><small>prawdziwe 1./2./3. gemy serwisowe · ostatnie 5 mocniej + poprzednie · nawierzchnia</small></div><span>${e.ready?'LIVE DATA':'N/D'}</span></div>
      ${main}
      <div class="eh7-grid">${playerCol(e.p1)}${playerCol(e.p2)}</div>
      <div class="eh7-foot">* Joint Builder jest liczony wspólnie w jednej symulacji: wybrany zawodnik prowadzi po 6 gemach + over 8.5 gema + wygrywa 1. set. Nie mnożymy trzech niezależnych procentów.</div>
    </section>`;
  }

  renderMatchDetail = function(m){
    return baseRender(m) + box(m);
  };
})();
