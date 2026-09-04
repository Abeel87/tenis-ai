/* Player DNA · transparent SHADOW/prospective stats.
   UI-only: reads published evidence and never changes model/runtime decisions.
*/
(() => {
  'use strict';

  const PROSPECTIVE_URL='data/player_dna_prospective_validation.json';
  const WALK_FORWARD_URL='data/player_dna_hold_walk_forward.json';
  const MIN_SETTLED=150;
  const PANEL_ID='player-dna-shadow-stats';
  const MARKET_LABELS={
    first_set_tiebreak:'Tie-break · 1. set',
    'first_set_over_8.5':'Over 8.5 · 1. set',
    'first_set_over_9.5':'Over 9.5 · 1. set',
    'first_set_over_10.5':'Over 10.5 · 1. set'
  };

  let lastLoad=null;

  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[char]));

  function n(value){
    const x=Number(value);
    return Number.isFinite(x)?x:null;
  }

  function brier(value){
    const x=n(value);
    return x==null?'—':x.toFixed(4);
  }

  function delta(value){
    const x=n(value);
    if(x==null)return '—';
    return `${x>=0?'+':''}${x.toFixed(4)}`;
  }

  function signalMeta(signal){
    if(signal==='PROSPECTIVE_DURATION_ROBUST_SHADOW'){
      return {label:'PROSPECTIVE ROBUST',tone:'good'};
    }
    if(signal==='PROSPECTIVE_DURATION_NOT_YET_PROVEN'){
      return {label:'NIEPOTWIERDZONE',tone:'warn'};
    }
    return {label:'ZBIERAMY DANE',tone:'collecting'};
  }

  async function json(url){
    try{
      const response=await fetch(url,{cache:'default'});
      if(!response.ok)return null;
      const data=await response.json();
      return data&&typeof data==='object'?data:null;
    }catch{
      return null;
    }
  }

  async function load(force=false){
    if(force) lastLoad=null;
    if(!lastLoad){
      lastLoad=Promise.all([json(PROSPECTIVE_URL),json(WALK_FORWARD_URL)])
        .then(([prospective,walkForward])=>({prospective,walkForward}))
        .catch(()=>({prospective:null,walkForward:null}));
    }
    return lastLoad;
  }

  function statsViewActive(){
    const btn=document.querySelector('[data-view="stats"]');
    return !!btn?.classList.contains('active');
  }

  function supportedChips(policy={}){
    const tours=Array.isArray(policy.supported_tours)?policy.supported_tours:[];
    const surfaces=Array.isArray(policy.supported_surfaces)?policy.supported_surfaces:[];
    const labels=[
      ...tours.map(x=>String(x).toUpperCase()),
      ...surfaces.map(x=>String(x).toUpperCase())
    ];
    if(!labels.length)return '<span class="pds-chip muted">brak zatwierdzonych segmentów</span>';
    return labels.map(x=>`<span class="pds-chip">${esc(x)}</span>`).join('');
  }

  function marketRows(prospective){
    const markets=prospective?.evaluation?.markets||{};
    return Object.entries(MARKET_LABELS).map(([key,label])=>{
      const row=markets[key]||{};
      const count=n(row.n)||0;
      const gain=n(row.brier_gain_calibrated_vs_raw);
      const improved=row.improved===true;
      const verdict=count===0?'czekamy':improved?'lepiej':'gorzej / bez poprawy';
      const cls=count===0?'pending':improved?'good':'warn';
      return `
        <div class="pds-market-row ${cls}">
          <div><b>${esc(label)}</b><small>n=${count}</small></div>
          <span>RAW <strong>${brier(row.raw_brier)}</strong></span>
          <span>DNA <strong>${brier(row.calibrated_brier)}</strong></span>
          <span>Δ <strong>${delta(gain)}</strong></span>
          <em>${esc(verdict)}</em>
        </div>`;
    }).join('');
  }

  function settlementHealth(prospective){
    const integrity=prospective?.ledger_integrity||{};
    const observability=prospective?.settlement_observability||{};
    const unsettled=observability.unsettled||{};
    const buckets=unsettled.buckets||{};
    const latency=observability.settlement_latency||{};
    const drift=observability.schedule_drift||{};
    const overdue6=n(buckets.overdue_6_24h)||0;
    const overdue24=n(buckets.overdue_24_72h)||0;
    const overdue72=n(buckets.overdue_gt_72h)||0;
    const overdue=overdue6+overdue24+overdue72;
    const ledgerOk=integrity.status==='LEDGER_INTEGRITY_OK';
    const latencyN=n(latency.n)||0;
    const median=n(latency.median_hours);
    const driftCount=n(drift.count)||0;

    return {
      ledgerLabel:ledgerOk?'OK':'BRAK / BŁĄD',
      ledgerTone:ledgerOk?'good':'warn',
      rewrites:n(integrity.rewritten_predictions)||0,
      overdue,
      overdue72,
      upcoming:n(buckets.upcoming)||0,
      due:n(buckets.due_within_6h)||0,
      latencyN,
      latencyMedian:median==null?'—':`${median.toFixed(1)} h`,
      driftCount,
      ready:Object.keys(observability).length>0
    };
  }

  function renderHTML(prospective,walkForward){
    if(!prospective){
      return `
        <header class="pds-head">
          <div><b>🧬 Player DNA</b><small>Prospective validation · SHADOW</small></div>
          <span class="pds-status collecting">CZEKA NA RAPORT</span>
        </header>
        <div class="pds-empty">
          Pierwszy raport prospective nie jest jeszcze opublikowany na main. Panel sam się uzupełni po refreshu Player DNA.
        </div>
        <p class="pds-foot">SHADOW · zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE.</p>`;
    }

    const counts=prospective.counts||{};
    const evaluation=prospective.evaluation||{};
    const policy=prospective.eligibility_policy||{};
    const aggregate=walkForward?.aggregate||{};
    const sig=signalMeta(prospective.signal);
    const settled=n(counts.settled_snapshots)||0;
    const snapshots=n(counts.snapshots)||0;
    const eligible=n(counts.current_eligible_by_segment)||0;
    const complete=n(aggregate.completed_folds)||0;
    const required=n(aggregate.required_folds)||0;
    const promising=n(aggregate.promising_folds)||0;
    const target=Math.max(MIN_SETTLED,settled);
    const progress=Math.min(100,Math.round((settled/target)*100));
    const scope=prospective.market_scope==='DURATION_MARKETS_ONLY'
      ?'Tylko duration markets'
      :'Zakres diagnostyczny';
    const health=settlementHealth(prospective);

    return `
      <header class="pds-head">
        <div>
          <b>🧬 Player DNA</b>
          <small>Forward test bez poprawiania predykcji po meczu · SHADOW</small>
        </div>
        <span class="pds-status ${sig.tone}">${esc(sig.label)}</span>
      </header>

      <div class="pds-grid">
        <div class="pds-metric">
          <span>Walk-forward</span>
          <b>${complete}/${required||'—'}</b>
          <small>${promising}/${required||'—'} foldów PROMISING</small>
        </div>
        <div class="pds-metric">
          <span>Zamrożone typy</span>
          <b>${snapshots}</b>
          <small>predykcje zapisane przed meczem</small>
        </div>
        <div class="pds-metric">
          <span>Rozliczone</span>
          <b>${settled} / ${MIN_SETTLED}</b>
          <small>próg pierwszej oceny prospective</small>
        </div>
        <div class="pds-metric">
          <span>Bieżące eligible</span>
          <b>${eligible}</b>
          <small>${esc(scope)}</small>
        </div>
      </div>

      <div class="pds-progress" aria-label="Postęp próby prospective">
        <span style="width:${progress}%"></span>
      </div>

      <div class="pds-segments">
        <div><b>Segmenty dopuszczone przez walk-forward</b><small>tour AND surface muszą być powtarzalne</small></div>
        <div class="pds-chips">${supportedChips(policy)}</div>
      </div>

      <section class="pds-health">
        <div class="pds-subhead">
          <b>Integralność i rozliczanie</b>
          <small>Kontrola, czy forward-test nie przepisuje historii i czy wyniki dochodzą do canonical tape.</small>
        </div>
        ${health.ready?`
          <div class="pds-health-grid">
            <div class="pds-health-item ${health.ledgerTone}">
              <span>Ledger</span>
              <b>${esc(health.ledgerLabel)}</b>
              <small>rewrite: ${health.rewrites}</small>
            </div>
            <div class="pds-health-item ${health.overdue72?'warn':'good'}">
              <span>Czekają &gt;6 h</span>
              <b>${health.overdue}</b>
              <small>&gt;72 h: ${health.overdue72}</small>
            </div>
            <div class="pds-health-item">
              <span>Latency median</span>
              <b>${esc(health.latencyMedian)}</b>
              <small>n=${health.latencyN} rozliczonych</small>
            </div>
            <div class="pds-health-item ${health.driftCount?'warn':'good'}">
              <span>Zmiany godziny</span>
              <b>${health.driftCount}</b>
              <small>snapshot pozostaje zamrożony</small>
            </div>
          </div>
          <p class="pds-health-note">
            Nierozliczony / overdue oznacza tylko, że workflow nie ma jeszcze kompletnych canonical labeli.
            To nie jest automatycznie anulowany mecz. Przed startem: ${health.upcoming}, do 6 h po planowanym starcie: ${health.due}.
          </p>
        `:`
          <div class="pds-empty">Diagnostyka rozliczania pojawi się po pierwszym refreshu raportu z nowym kontraktem.</div>
        `}
      </section>

      <section class="pds-markets">
        <div class="pds-subhead">
          <b>Brier: RAW vs hold-calibrated DNA</b>
          <small>Niżej = lepiej. Δ dodatnia oznacza przewagę DNA.</small>
        </div>
        ${marketRows(prospective)}
      </section>

      <p class="pds-foot">
        ${settled<MIN_SETTLED
          ?`Na razie zbieramy czystą próbkę: ${settled}/${MIN_SETTLED} rozliczonych.`
          :`Próg ${MIN_SETTLED} rozliczonych osiągnięty — patrzymy na stabilność każdego rynku i segmentu.`}
        Winner markets: wyłączone. SHADOW · zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE.
      </p>`;
  }

  async function render(force=false){
    if(!statsViewActive())return false;
    const app=document.querySelector('#app');
    if(!app)return false;

    const data=await load(force);
    if(!statsViewActive())return false;

    let panel=document.getElementById(PANEL_ID);
    if(!panel){
      panel=document.createElement('section');
      panel.id=PANEL_ID;
      panel.className='pds-panel v853-primary-block';
      panel.dataset.playerDnaShadow='1';
    }
    panel.innerHTML=renderHTML(data.prospective,data.walkForward);

    const toolbar=document.querySelector('#v853-stats-toolbar');
    const playerIntel=document.querySelector('#pi85-stats');
    if(playerIntel?.parentNode){
      playerIntel.parentNode.insertBefore(panel,playerIntel);
    }else if(toolbar?.parentNode){
      toolbar.insertAdjacentElement('afterend',panel);
    }else if(app.firstElementChild){
      app.insertBefore(panel,app.firstElementChild);
    }else{
      app.append(panel);
    }
    return true;
  }

  function schedule(force=false){
    queueMicrotask(()=>render(force).catch(()=>{}));
  }

  document.addEventListener('tenis-ai:stats-ready',()=>schedule(false));
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>schedule(false));
  document.addEventListener('click',event=>{
    if(event.target?.closest?.('[data-view="stats"]'))schedule(false);
    if(event.target?.closest?.('#refresh'))schedule(true);
  },true);

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',()=>schedule(false),{once:true});
  }else{
    schedule(false);
  }

  window.TENIS_AI_PLAYER_DNA_SHADOW=Object.freeze({
    mode:'SHADOW_UI_ONLY',
    prospectiveUrl:PROSPECTIVE_URL,
    walkForwardUrl:WALK_FORWARD_URL,
    render:()=>render(true)
  });
})();
