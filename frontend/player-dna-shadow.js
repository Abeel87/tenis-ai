/* Player DNA · transparent SHADOW/prospective stats.
   UI-only: reads published evidence and never changes model/runtime decisions.
*/
(() => {
  'use strict';

  const PROSPECTIVE_URL='data/player_dna_prospective_validation.json';
  const WALK_FORWARD_URL='data/player_dna_hold_walk_forward.json';
  const SIMULATION_URL='data/player_dna_current_simulation.json';
  const MIN_SETTLED=150;
  const PANEL_ID='player-dna-shadow-stats';
  const MARKET_LABELS={
    first_set_tiebreak:'Tie-break · 1. set',
    'first_set_over_8.5':'Over 8.5 · 1. set',
    'first_set_over_9.5':'Over 9.5 · 1. set',
    'first_set_over_10.5':'Over 10.5 · 1. set'
  };

  let lastLoad=null;
  let simulationLoad=null;

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

  async function loadSimulation(force=false){
    if(force) simulationLoad=null;
    if(!simulationLoad){
      simulationLoad=json(SIMULATION_URL).catch(()=>null);
    }
    return simulationLoad;
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

  function norm(value){
    return String(value??'')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g,'')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g,' ')
      .trim();
  }

  function pct(value){
    const x=n(value);
    return x==null?'—':`${(x*100).toFixed(1).replace('.0','')}%`;
  }

  function activeDetailMatch(){
    const overlay=document.querySelector('#p751-match-overlay:not([hidden])');
    if(!overlay)return null;
    const key=String(overlay.dataset.matchKey||'');
    try{
      return window.TENIS_AI_PROJECT_UI?.findMatch?.(key)||null;
    }catch{
      return null;
    }
  }

  function simulationRow(report,match){
    const rows=Array.isArray(report?.matches)?report.matches:[];
    if(!match||!rows.length)return null;
    const id=match.id??match.match_id;
    if(id!=null){
      const direct=rows.find(row=>String(row?.match_id??'')===String(id));
      if(direct)return direct;
    }
    const p1=norm(match.p1),p2=norm(match.p2);
    const when=Date.parse(match.scheduled_time||'');
    return rows.find(row=>{
      if(norm(row?.p1)!==p1||norm(row?.p2)!==p2)return false;
      const other=Date.parse(row?.scheduled_time||'');
      return Number.isFinite(when)&&Number.isFinite(other)
        ?Math.abs(when-other)<=10*60*1000
        :true;
    })||null;
  }

  function topCheckpoint(trajectory,key){
    const rows=trajectory?.checkpoints_neutral_start_server?.[key];
    if(!Array.isArray(rows)||!rows.length)return null;
    return rows[0]||null;
  }

  function scenarioPathText(path){
    const sets=Array.isArray(path?.sets)?path.sets:[];
    if(sets.length){
      return sets.map((setRow,index)=>{
        const progression=Array.isArray(setRow?.progression)?setRow.progression:[];
        return `Set ${index+1}: ${progression.join(' → ')}`;
      }).join(' · ');
    }
    const setScores=Array.isArray(path?.set_scores)?path.set_scores:[];
    return setScores.length?`Sety: ${setScores.join(' · ')}`:'Brak pełnej ścieżki';
  }

  function conditionedScenario(branch,label,p1,p2){
    const full=Array.isArray(branch?.full_match_top_game_paths)?branch.full_match_top_game_paths:[];
    const setPaths=Array.isArray(branch?.match_top_set_paths)?branch.match_top_set_paths:[];
    const firstSet=Array.isArray(branch?.first_set_top_game_paths)?branch.first_set_top_game_paths:[];
    const primary=full.length?full:setPaths;
    const top=primary.slice(0,3);
    const firstName=label==='p1'?p1:p2;

    return `
      <div class="pds-trajectory-branch">
        <header>
          <div><span>Pierwszy serwis</span><b>${esc(firstName||'N/D')}</b></div>
          <small>warunek scenariusza</small>
        </header>
        ${top.length?top.map((path,index)=>`
          <details class="pds-scenario" ${index===0?'open':''}>
            <summary>
              <span>#${index+1}</span>
              <b>${esc(path.match_score||path.final_score||'scenariusz')}</b>
              <em>${pct(path.probability)}</em>
              <i>⌄</i>
            </summary>
            <div>
              <p>${esc(scenarioPathText(path))}</p>
              ${path.total_games!=null?`<small>Łącznie gemów: ${esc(path.total_games)} · setów: ${esc(path.sets_played)}</small>`:''}
            </div>
          </details>
        `).join(''):`
          <div class="pds-empty">Pełne ścieżki meczu pojawią się po publikacji nowego raportu trajektorii.</div>
        `}
        ${!full.length&&firstSet[0]?`
          <p class="pds-trajectory-fallback">
            Najmocniejsza ścieżka 1. seta: <b>${esc(firstSet[0].final_score||'—')}</b>
            · ${pct(firstSet[0].probability)}
          </p>
        `:''}
      </div>`;
  }

  function trajectoryHTML(row){
    const sim=row?.simulation||{};
    const trajectory=sim.trajectory||{};
    if(trajectory.status!=='SHADOW_TRAJECTORY_FOUNDATION'){
      return `
        <header class="pds-trajectory-head">
          <div><b>🧬 Player DNA · przebieg meczu</b><small>SHADOW trajectory</small></div>
          <span class="pds-status collecting">CZEKA NA RAPORT</span>
        </header>
        <div class="pds-empty">Dla tego meczu nie ma jeszcze opublikowanej trajektorii Player DNA.</div>`;
    }

    const cp2=topCheckpoint(trajectory,'after_2_games');
    const cp4=topCheckpoint(trajectory,'after_4_games');
    const cp6=topCheckpoint(trajectory,'after_6_games');
    const conditioned=trajectory.serve_order_conditioned||{};
    return `
      <header class="pds-trajectory-head">
        <div>
          <b>🧬 Player DNA · mapa przebiegu meczu</b>
          <small>ranking scenariuszy, nie jeden pewny skrypt</small>
        </div>
        <span class="pds-status collecting">SHADOW</span>
      </header>

      <div class="pds-checkpoints">
        <span><small>Po 2 gemach</small><b>${esc(cp2?.score||'—')}</b><em>${pct(cp2?.probability)}</em></span>
        <span><small>Po 4 gemach</small><b>${esc(cp4?.score||'—')}</b><em>${pct(cp4?.probability)}</em></span>
        <span><small>Po 6 gemach</small><b>${esc(cp6?.score||'—')}</b><em>${pct(cp6?.probability)}</em></span>
      </div>

      <div class="pds-trajectory-grid">
        ${conditionedScenario(conditioned.p1_serves_first,'p1',row.p1,row.p2)}
        ${conditionedScenario(conditioned.p2_serves_first,'p2',row.p1,row.p2)}
      </div>

      <p class="pds-foot">
        Pierwszy serwujący jest przed meczem nieznany, dlatego pokazujemy oba warunki osobno.
        Prawdopodobieństwo ścieżki jest warunkowe na wskazany pierwszy serwis.
        ${row.hold_calibrated_candidate?'Hold-calibrated DNA pozostaje kandydatem i nie zastępuje tej referencyjnej trajektorii. ':''}
        UNVALIDATED_MATCH_LEVEL · zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE.
      </p>`;
  }

  async function injectTrajectory(force=false){
    const overlay=document.querySelector('#p751-match-overlay:not([hidden])');
    if(!overlay)return false;
    const match=activeDetailMatch();
    if(!match)return false;

    const report=await loadSimulation(force);
    if(!document.querySelector('#p751-match-overlay:not([hidden])'))return false;
    const row=simulationRow(report,match);

    let panel=overlay.querySelector('#player-dna-match-trajectory');
    if(!panel){
      panel=document.createElement('section');
      panel.id='player-dna-match-trajectory';
      panel.className='pds-trajectory-panel';
      panel.dataset.playerDnaTrajectory='1';
    }
    panel.innerHTML=trajectoryHTML(row);

    const playerContext=overlay.querySelector('[data-pi851-detail],#pi85-detail');
    const verdict=overlay.querySelector('.p751-verdict');
    const matchup=overlay.querySelector('.p751-matchup');
    if(playerContext?.parentNode){
      playerContext.insertAdjacentElement('afterend',panel);
    }else if(verdict?.parentNode){
      verdict.parentNode.insertBefore(panel,verdict);
    }else if(matchup?.parentNode){
      matchup.insertAdjacentElement('afterend',panel);
    }
    return true;
  }

  function wrapProjectOpen(){
    const project=window.TENIS_AI_PROJECT_UI;
    if(!project||project.__playerDnaTrajectoryWrapped||typeof project.openMatch!=='function')return false;
    const base=project.openMatch;
    project.openMatch=function(...args){
      const result=base.apply(this,args);
      queueMicrotask(()=>injectTrajectory(false).catch(()=>{}));
      return result;
    };
    Object.defineProperty(project,'__playerDnaTrajectoryWrapped',{value:true});
    return true;
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
    if(event.target?.closest?.('#refresh')){
      schedule(true);
      simulationLoad=null;
    }
    if(event.target?.closest?.('[data-p751-open]')){
      setTimeout(()=>injectTrajectory(false).catch(()=>{}),60);
    }
  },true);

  function boot(){
    wrapProjectOpen();
    schedule(false);
    if(document.querySelector('#p751-match-overlay:not([hidden])')){
      injectTrajectory(false).catch(()=>{});
    }
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }

  window.TENIS_AI_PLAYER_DNA_SHADOW=Object.freeze({
    mode:'SHADOW_UI_ONLY',
    prospectiveUrl:PROSPECTIVE_URL,
    walkForwardUrl:WALK_FORWARD_URL,
    simulationUrl:SIMULATION_URL,
    render:()=>render(true),
    renderTrajectory:()=>injectTrajectory(true)
  });
})();
