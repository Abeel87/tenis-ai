/* Player DNA · transparent SHADOW/prospective stats.
   UI-only: reads published evidence and never changes model/runtime decisions.
*/
(() => {
  'use strict';

  const PROSPECTIVE_URL='data/player_dna_prospective_validation.json';
  const WALK_FORWARD_URL='data/player_dna_hold_walk_forward.json';
  const SIMULATION_URL='data/player_dna_current_simulation.json';
  const MIN_SETTLED=150;
  const DYNAMIC_MIN_SETTLED_MARKET_OBSERVATIONS=150;
  const DYNAMIC_MIN_SETTLED_PER_MARKET=30;
  const PANEL_ID='player-dna-shadow-stats';
  const MARKET_LABELS={
    first_set_tiebreak:'Tie-break · 1. set',
    'first_set_over_8.5':'Over 8.5 · 1. set',
    'first_set_over_9.5':'Over 9.5 · 1. set',
    'first_set_over_10.5':'Over 10.5 · 1. set'
  };

  const DYNAMIC_MARKET_LABELS={
    match_p1_win:'P1 wygra mecz',
    first_set_p1_win:'P1 wygra 1. set',
    first_set_tiebreak:'Tie-break · 1. set',
    'first_set_over_8.5':'Over 8.5 · 1. set',
    'first_set_over_9.5':'Over 9.5 · 1. set',
    'first_set_over_10.5':'Over 10.5 · 1. set',
    'first_set_over_11.5':'Over 11.5 · 1. set',
    'first_set_over_12.5':'Over 12.5 · 1. set',
    'early_1:1':'1:1 po 2 gemach',
    'early_2:2':'2:2 po 4 gemach',
    'early_3:3':'3:3 po 6 gemach'
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

  function dynamicSignalMeta(signal){
    if(signal==='DYNAMIC_LEAN_PROSPECTIVE_EVIDENCE_READY_SHADOW'){
      return {label:'PRÓBKA GOTOWA DO OCENY',tone:'good'};
    }
    return {label:'ZBIERAMY DYNAMIC LEAN',tone:'collecting'};
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

  function dynamicMarketRows(dynamic){
    const evaluation=dynamic?.evaluation||{};
    const markets=evaluation.markets||{};
    const seen=Array.isArray(evaluation.candidate_markets_seen)
      ?evaluation.candidate_markets_seen
      :Object.keys(markets).filter(key=>(n(markets[key]?.n)||0)>0);
    if(!seen.length){
      return '<div class="pds-empty">Brak zamrożonych rynków dynamic-candidate w ledgerze.</div>';
    }
    return seen.map(key=>{
      const label=DYNAMIC_MARKET_LABELS[key]||key;
      const row=markets[key]||{};
      const count=n(row.n)||0;
      const gain=n(row.brier_gain_dynamic_vs_profile);
      const improved=row.dynamic_better_on_brier_and_log_loss===true;
      const verdict=count===0?'czeka na wynik':improved?'dynamic lepiej':'brak przewagi';
      const cls=count===0?'pending':improved?'good':'warn';
      return `
        <div class="pds-market-row ${cls}">
          <div><b>${esc(label)}</b><small>settled n=${count}</small></div>
          <span>PROFILE <strong>${brier(row.profile_reference_brier)}</strong></span>
          <span>DYNAMIC <strong>${brier(row.dynamic_candidate_brier)}</strong></span>
          <span>Δ <strong>${delta(gain)}</strong></span>
          <em>${esc(verdict)}</em>
        </div>`;
    }).join('');
  }

  function dynamicDirectSegmentRows(dynamic){
    const direct=dynamic?.direct_segment_readiness||{};
    const segments=direct.tour_surface||{};
    const rows=[];
    Object.entries(segments).forEach(([segment,payload])=>{
      Object.entries(payload?.candidate_markets||{}).forEach(([market,support])=>{
        const settled=n(support?.settled)||0;
        const required=n(support?.required)||DYNAMIC_MIN_SETTLED_PER_MARKET;
        const remaining=n(support?.remaining);
        const ready=support?.support_sufficient===true;
        rows.push({segment,market,settled,required,remaining,ready});
      });
    });
    if(!rows.length){
      return '<div class="pds-empty">Brak bezpośrednich tour|surface candidate cells w bieżącej generacji policy.</div>';
    }
    return rows.map(row=>`
      <div class="pds-direct-cell ${row.ready?'good':'pending'}">
        <div>
          <b>${esc(row.segment)}</b>
          <small>${esc(DYNAMIC_MARKET_LABELS[row.market]||row.market)}</small>
        </div>
        <span><strong>${row.settled} / ${row.required}</strong></span>
        <em>${row.ready?'DIRECT READY':`brakuje ${row.remaining==null?'—':row.remaining}`}</em>
      </div>
    `).join('');
  }

  function dynamicVerdictMeta(verdict){
    const signal=verdict?.signal;
    if(signal==='DYNAMIC_LEAN_PROSPECTIVE_ROBUST_SHADOW'){
      return {label:'ROBUST SHADOW',tone:'good',detail:'Global i wszystkie wspierane direct tour|surface cells wygrywają jednocześnie na Brier i log-loss.'};
    }
    if(signal==='DYNAMIC_LEAN_PROSPECTIVE_NOT_PROVEN'){
      return {label:'NIEPOTWIERDZONE',tone:'warn',detail:'Próba jest gotowa, ale co najmniej jeden rynek lub direct cell nie potwierdził przewagi na obu metrykach.'};
    }
    if(verdict?.reason==='DIRECT_TOUR_SURFACE_SUPPORT_INSUFFICIENT'){
      return {label:'CZEKA NA DIRECT',tone:'pending',detail:'Globalna próba może być gotowa, ale brakuje bezpośredniej próby w co najmniej jednym tour|surface candidate cell.'};
    }
    return {label:'CZEKA NA PRÓBĘ',tone:'pending',detail:'Za mało bieżących settled observations per rynek lub łącznie.'};
  }

  function dynamicEvidenceHTML(prospective){
    const dynamic=prospective?.dynamic_lean_evidence;
    if(!dynamic||dynamic.mode!=='SHADOW_DYNAMIC_LEAN_PROSPECTIVE_LEDGER_ONLY'){
      return `
        <section class="pds-dynamic">
          <div class="pds-subhead">
            <b>Dynamic lean · prospective ledger</b>
            <small>Osobny forward-test candidate vs profile reference.</small>
          </div>
          <div class="pds-empty">Dynamic ledger pojawi się po pierwszym refreshu raportu z kontraktem #200.</div>
        </section>`;
    }

    const counts=dynamic.counts||{};
    const readiness=dynamic.evidence_readiness||{};
    const total=readiness.settled_market_observations||{};
    const marketSupport=readiness.observed_candidate_markets||{};
    const sig=dynamicSignalMeta(dynamic.signal);
    const snapshots=n(counts.snapshots)||0;
    const settledSnapshots=n(counts.settled_snapshots)||0;
    const settledObs=n(counts.settled_market_observations)||0;
    const currentRows=n(counts.current_rows_with_dynamic_candidates)||0;
    const currentSlots=n(counts.current_dynamic_candidate_market_slots)||0;
    const remaining=n(total.remaining);
    const target=n(total.required)||DYNAMIC_MIN_SETTLED_MARKET_OBSERVATIONS;
    const progress=Math.min(100,Math.round((settledObs/Math.max(target,1))*100));
    const marketSupportRows=Object.entries(marketSupport);
    const underSupported=marketSupportRows.filter(([,row])=>row?.support_sufficient!==true);
    const integrity=dynamic.ledger_integrity||{};
    const integrityOk=integrity.status==='LEDGER_INTEGRITY_OK';
    const policyProvenance=dynamic.market_policy_provenance||{};
    const policyGenerations=n(policyProvenance.known_generation_count)||0;
    const legacyPolicySnapshots=n(policyProvenance.legacy_unknown_snapshots)||0;
    const excludedPolicySnapshots=n(policyProvenance.verdict_excluded_snapshots)||0;
    const direct=dynamic.direct_segment_readiness||{};
    const directCells=n(direct.observed_tour_surface_market_cells)||0;
    const directReady=direct.ready_for_performance_verdict===true;
    const verdict=dynamic.performance_verdict||{};
    const verdictMeta=dynamicVerdictMeta(verdict);

    return `
      <section class="pds-dynamic">
        <div class="pds-dynamic-head">
          <div class="pds-subhead">
            <b>Dynamic lean · prospective ledger</b>
            <small>Wyłącznie CONSENSUS_DYNAMIC_CANDIDATE · PROFILE jest zamrożonym benchmarkiem.</small>
          </div>
          <span class="pds-status ${sig.tone}">${esc(sig.label)}</span>
        </div>

        <div class="pds-grid">
          <div class="pds-metric">
            <span>Dynamic snapshots</span>
            <b>${snapshots}</b>
            <small>settled matches: ${settledSnapshots}</small>
          </div>
          <div class="pds-metric">
            <span>Market observations</span>
            <b>${settledObs} / ${target}</b>
            <small>pozostało: ${remaining==null?'—':remaining}</small>
          </div>
          <div class="pds-metric">
            <span>Candidate teraz</span>
            <b>${currentRows}</b>
            <small>${currentSlots} slotów rynkowych</small>
          </div>
          <div class="pds-metric">
            <span>Ledger integrity</span>
            <b>${integrityOk?'OK':'BRAK / BŁĄD'}</b>
            <small>rewrite: ${n(integrity.rewritten_predictions)||0}</small>
          </div>
        </div>

        <div class="pds-progress" aria-label="Postęp dynamic prospective">
          <span style="width:${progress}%"></span>
        </div>

        <div class="pds-dynamic-support">
          <b>Próg per rynek: ${DYNAMIC_MIN_SETTLED_PER_MARKET}</b>
          <small>
            ${marketSupportRows.length
              ?(underSupported.length
                ?`${underSupported.length} rynków nadal poniżej minimalnej próby.`
                :'Każdy obserwowany candidate market ma minimalną próbę.')
              :'Czekamy na pierwszy zamrożony candidate market.'}
          </small>
        </div>

        <div class="pds-dynamic-support">
          <b>Policy generations: ${policyGenerations}</b>
          <small>
            Verdict liczy wyłącznie bieżącą generację strict segment-consensus.
            Wykluczone ze strict verdictu: ${excludedPolicySnapshots}; legacy bez fingerprintu: ${legacyPolicySnapshots}.
          </small>
        </div>

        <div class="pds-dynamic-support">
          <b>Direct tour|surface: ${directReady?'READY':'CZEKA'} · ${directCells} cells</b>
          <small>Każdy obserwowany candidate cell potrzebuje własnych settled wyników; marginesy tour i surface nie zastępują joint evidence.</small>
        </div>

        <div class="pds-direct">
          <div class="pds-subhead">
            <b>Bezpośrednia próba tour|surface</b>
            <small>To ta warstwa blokuje verdict, jeśli choć jeden obserwowany joint cell nie ma pełnego wsparcia.</small>
          </div>
          ${dynamicDirectSegmentRows(dynamic)}
        </div>

        <div class="pds-dynamic-verdict ${verdictMeta.tone}">
          <div>
            <b>Performance verdict · ${esc(verdictMeta.label)}</b>
            <small>${esc(verdict.reason||'—')}</small>
          </div>
          <p>${esc(verdictMeta.detail)}</p>
        </div>

        <div class="pds-markets">
          <div class="pds-subhead">
            <b>Brier: PROFILE vs dynamic lean</b>
            <small>Δ dodatnia = przewaga dynamic. Gotowa próbka nie oznacza jeszcze pozytywnego verdictu.</small>
          </div>
          ${dynamicMarketRows(dynamic)}
        </div>

        <p class="pds-foot">
          ${verdict.emitted===true
            ?'Performance verdict został policzony wyłącznie z bieżącej generacji policy oraz z pełnym direct tour|surface support.'
            :directReady
              ?'Direct support jest gotowy; verdict nadal czeka na pełną próbę global/per-market.'
              :readiness.ready_for_performance_verdict===true
                ?'Global/per-market support jest gotowy, ale verdict nadal blokuje brak direct tour|surface support.'
                :'Trwa czyste zbieranie wyników bieżącej generacji policy; verdict pozostaje zablokowany.'}
          Nawet ROBUST SHADOW nie oznacza auto-promocji. SHADOW · zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE.
        </p>
      </section>`;
  }


  function trajectoryMetric(label,row,keys){
    row=row||{};
    const count=n(row.n)||0;
    const values=keys.map(([key,name])=>`
      <span><small>${esc(name)}</small><b>${pct(row[key])}</b></span>
    `).join('');
    return `
      <div class="pds-trajectory-evidence-row">
        <div><b>${esc(label)}</b><small>n=${count}</small></div>
        <div class="pds-trajectory-evidence-values">${values}</div>
      </div>`;
  }

  function trajectoryEvidenceHTML(prospective){
    const trajectory=prospective?.trajectory_evidence;
    if(!trajectory||trajectory.mode!=='SHADOW_TRAJECTORY_PROSPECTIVE_LEDGER_ONLY'){
      return `
        <section class="pds-trajectory-evidence">
          <div class="pds-subhead">
            <b>Trajectory · prospective evidence</b>
            <small>Forward-test przebiegu meczu, bez zmiany runtime.</small>
          </div>
          <div class="pds-empty">Trajectory ledger pojawi się po pierwszym refreshu nowego raportu.</div>
        </section>`;
    }

    const counts=trajectory.counts||{};
    const evaluation=trajectory.evaluation||{};
    const integrity=trajectory.ledger_integrity||{};
    const checkpoints=evaluation.checkpoint_neutral_start_server||{};
    const settled=n(counts.settled_snapshots)||0;
    const snapshots=n(counts.snapshots)||0;
    const ledgerSettled=n(counts.ledger_settled_snapshots)||0;
    const currentGeneration=n(counts.current_generation_snapshots)||0;
    const excludedGeneration=n(counts.evaluation_excluded_snapshots)||0;
    const current=n(counts.new_current_pre_match_snapshots)||0;
    const integrityOk=integrity.status==='LEDGER_INTEGRITY_OK';
    const health=settlementHealth(trajectory);
    const provenance=trajectory.provenance||{};
    const knownGenerations=n(provenance.known_generation_count)||0;
    const legacyUnknown=n(provenance.legacy_unknown_snapshots)||0;
    const mixedGenerations=provenance.mixed_known_generations===true;
    const simulatorContractId=provenance.current_simulator_contract_id||'—';
    const readiness=trajectory.sample_readiness||{};
    const readinessOverall=readiness.overall_settled_snapshots||{};
    const readinessPolicy=readiness.policy||{};
    const readyPrimary=n(readiness.ready_primary_metric_count)||0;
    const primaryCount=n(readiness.primary_metric_count)||0;
    const readyDirect=Array.isArray(readiness.ready_direct_tour_surface_segments)
      ?readiness.ready_direct_tour_surface_segments:[];
    const blockedDirect=Array.isArray(readiness.blocked_direct_tour_surface_segments)
      ?readiness.blocked_direct_tour_surface_segments:[];
    const sampleRequired=n(readinessOverall.required);
    const directRequired=n(readinessPolicy.direct_tour_surface_minimum_reuses_existing_prospective_gate);
    const sampleSufficient=readiness.sample_sufficient_for_future_performance_evaluation===true;

    return `
      <section class="pds-trajectory-evidence">
        <div class="pds-dynamic-head">
          <div class="pds-subhead">
            <b>Trajectory · prospective evidence</b>
            <small>Zamrożone przed meczem scenariusze przebiegu · bez dopasowania po wyniku.</small>
          </div>
          <span class="pds-status collecting">ZBIERAMY TRAJECTORY</span>
        </div>

        <div class="pds-grid">
          <div class="pds-metric">
            <span>Trajectory ledger</span>
            <b>${snapshots}</b>
            <small>settled łącznie: ${ledgerSettled}</small>
          </div>
          <div class="pds-metric">
            <span>Bieżąca generacja</span>
            <b>${currentGeneration}</b>
            <small>settled do metryk: ${settled}</small>
          </div>
          <div class="pds-metric">
            <span>Nowe przed meczem</span>
            <b>${current}</b>
            <small>z bieżącego refreshu</small>
          </div>
          <div class="pds-metric">
            <span>Ledger integrity</span>
            <b>${integrityOk?'OK':'BRAK / BŁĄD'}</b>
            <small>rewrite: ${n(integrity.rewritten_predictions)||0}</small>
          </div>
          <div class="pds-metric">
            <span>Próbka trajectory</span>
            <b>${settled} / ${sampleRequired??'—'}</b>
            <small>sample-size gate, nie verdict</small>
          </div>
          <div class="pds-metric">
            <span>Performance verdict</span>
            <b>NIE</b>
            <small>${sampleSufficient?'próbka gotowa; próg skuteczności nadal niezdefiniowany':'najpierw czysta próbka'}</small>
          </div>
        </div>

        ${health.ready?`
          <div class="pds-health-grid">
            <div class="pds-health-item">
              <span>Nadchodzące</span>
              <b>${health.upcoming}</b>
              <small>jeszcze przed startem</small>
            </div>
            <div class="pds-health-item ${health.overdue?'warn':'good'}">
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
              <small>frozen schedule bez rewrite</small>
            </div>
          </div>
        `:''}

        <div class="pds-dynamic-support">
          <b>Simulator generations: ${knownGenerations}</b>
          <small>
            Semantic contract: ${esc(simulatorContractId)} · source SHA służy tylko do audytu.
            ${mixedGenerations
              ?'UWAGA: ledger zawiera więcej niż jedną znaną wersję simulatora — przyszły verdict musi liczyć je osobno.'
              :knownGenerations===1
                ?'Jedna znana generacja simulatora w ledgerze.'
                :'Czekamy na pierwszą snapshotowaną generację simulatora.'}
            Wykluczone z bieżących metryk: ${excludedGeneration}.
            ${legacyUnknown?` Legacy bez fingerprintu: ${legacyUnknown}.`:''}
          </small>
        </div>

        <div class="pds-dynamic-support">
          <b>Sample readiness: ${sampleSufficient?'GOTOWA DO PÓŹNIEJSZEJ OCENY':'ZBIERAMY'}</b>
          <small>
            Główne metryki: ${readyPrimary}/${primaryCount||'—'} gotowych.
            Direct tour|surface: ${readyDirect.length} gotowych, ${blockedDirect.length} jeszcze zbiera próbkę.
            ${directRequired!=null?` Minimum per direct segment: ${directRequired} settled.`:''}
            To jest wyłącznie gate wielkości próby; nie ocenia skuteczności i nie uruchamia performance verdictu.
          </small>
        </div>

        <div class="pds-trajectory-evidence-list">
          ${trajectoryMetric('Po 2 gemach',checkpoints.after_2_games,[['top1','TOP1'],['top3','TOP3']])}
          ${trajectoryMetric('Po 4 gemach',checkpoints.after_4_games,[['top1','TOP1'],['top3','TOP3']])}
          ${trajectoryMetric('Po 6 gemach',checkpoints.after_6_games,[['top1','TOP1'],['top3','TOP3']])}
          ${trajectoryMetric(
            'Rodzina wyniku meczu',
            evaluation.primary_storyline_match_score_conditioned_on_observed_first_server,
            [['top1','TOP1'],['top3','TOP3']]
          )}
          ${trajectoryMetric(
            'Pełna ścieżka 1. seta',
            evaluation.first_set_complete_path_conditioned_on_observed_first_server,
            [['top1','TOP1'],['top3','TOP3'],['top8','TOP8']]
          )}
          ${trajectoryMetric(
            'Sekwencja wyników setów',
            evaluation.match_set_sequence_conditioned_on_observed_first_server,
            [['top1','TOP1'],['top3','TOP3'],['top12','TOP12']]
          )}
          ${trajectoryMetric(
            'Pełna ścieżka meczu',
            evaluation.full_match_game_path_conditioned_on_observed_first_server,
            [['top1','TOP1'],['top2','TOP2'],['top4','TOP4']]
          )}
        </div>

        <p class="pds-foot">
          Dokładna ścieżka gem po gemie pozostaje diagnostyką SHADOW. Pierwszy serwujący jest używany do oceny ścieżek dopiero po meczu;
          checkpointy 2/4/6 pozostają neutralne przed startem. Główne metryki liczą wyłącznie bieżącą generację simulatora;
          legacy i starsze znane generacje zostają tylko w diagnostyce ledger-wide. Nierozliczone snapshoty są rozdzielone na nadchodzące i faktycznie opóźnione;
          zmiana planowanej godziny nigdy nie przepisuje frozen prediction. Gotowość próbki nie jest performance verdictem.
          Nie ustawiamy jeszcze arbitralnego progu skuteczności. Zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE.
        </p>
      </section>`;
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

      ${dynamicEvidenceHTML(prospective)}

      ${trajectoryEvidenceHTML(prospective)}

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
    const app=document.querySelector('#app[data-match-key]');
    if(!app?.querySelector('.p751-detail-screen'))return null;
    const key=String(app.dataset.matchKey||'');
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
    const storylines=Array.isArray(branch?.match_storylines)?branch.match_storylines:[];
    const full=Array.isArray(branch?.full_match_top_game_paths)?branch.full_match_top_game_paths:[];
    const setPaths=Array.isArray(branch?.match_top_set_paths)?branch.match_top_set_paths:[];
    const firstSet=Array.isArray(branch?.first_set_top_game_paths)?branch.first_set_top_game_paths:[];
    const primary=storylines.length?storylines:(setPaths.length?setPaths:full);
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
              ${path.probability_scope==='MATCH_SCORE_FAMILY'
                ?`<small>${pct(path.probability)} = cała rodzina wyniku ${esc(path.match_score)}. Przebieg gem po gemie jest najbardziej prawdopodobnym reprezentantem tej rodziny.</small>`
                :(path.total_games!=null?`<small>Łącznie gemów: ${esc(path.total_games)} · setów: ${esc(path.sets_played)}</small>`:'')}
            </div>
          </details>
        `).join(''):`
          <div class="pds-empty">Pełne ścieżki meczu pojawią się po publikacji nowego raportu trajektorii.</div>
        `}
        ${!storylines.length&&!setPaths.length&&!full.length&&firstSet[0]?`
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
          <div>
            <b class="phase11-simple-only">🧬 Przewidywany przebieg meczu</b>
            <b class="phase11-technical">🧬 Player DNA · przebieg meczu</b>
            <small class="phase11-simple-only">Scenariusze pojawią się po przeliczeniu meczu.</small>
            <small class="phase11-technical">SHADOW trajectory</small>
          </div>
          <span class="pds-status collecting"><span class="phase11-simple-only">CZEKA NA DANE</span><span class="phase11-technical">CZEKA NA RAPORT</span></span>
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
          <b class="phase11-simple-only">🧬 Najbardziej prawdopodobny przebieg</b>
          <b class="phase11-technical">🧬 Player DNA · mapa przebiegu meczu</b>
          <small class="phase11-simple-only">Kilka możliwych scenariuszy — nie jeden pewny wynik.</small>
          <small class="phase11-technical">ranking scenariuszy, nie jeden pewny skrypt</small>
        </div>
        <span class="pds-status collecting"><span class="phase11-simple-only">TRYB TESTOWY</span><span class="phase11-technical">SHADOW</span></span>
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

      <p class="pds-foot phase11-simple-only">
        To są możliwe scenariusze, a nie pewny wynik. Pierwszy serwujący jest przed meczem nieznany,
        dlatego pokazujemy osobno oba warianty rozpoczęcia.
      </p>
      <p class="pds-foot phase11-technical">
        Pierwszy serwujący jest przed meczem nieznany, dlatego pokazujemy oba warunki osobno.
        Prawdopodobieństwo głównego scenariusza dotyczy rodziny wyniku meczu przy wskazanym pierwszym serwisie.
        Przebieg gem po gemie jest reprezentatywną ścieżką tej rodziny; dokładne pełne ścieżki pozostają diagnostyką SHADOW.
        ${row.hold_calibrated_candidate?'Hold-calibrated DNA pozostaje kandydatem i nie zastępuje tej referencyjnej trajektorii. ':''}
        UNVALIDATED_MATCH_LEVEL · zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE.
      </p>`;
  }

  async function injectTrajectory(force=false){
    const app=document.querySelector('#app[data-match-key]');
    const screen=app?.querySelector('.p751-detail-screen');
    if(!app||!screen)return false;
    const key=String(app.dataset.matchKey||'');
    const match=activeDetailMatch();
    if(!match)return false;

    const report=await loadSimulation(force);
    const currentApp=document.querySelector('#app[data-match-key]');
    if(!currentApp||String(currentApp.dataset.matchKey||'')!==key)return false;
    const currentScreen=currentApp.querySelector('.p751-detail-screen');
    if(!currentScreen)return false;
    const row=simulationRow(report,match);

    let panel=currentScreen.querySelector('#player-dna-match-trajectory');
    if(!panel){
      panel=document.createElement('section');
      panel.id='player-dna-match-trajectory';
      panel.className='pds-trajectory-panel';
      panel.dataset.playerDnaTrajectory='1';
    }
    panel.innerHTML=trajectoryHTML(row);

    const playerContext=currentScreen.querySelector('[data-pi851-detail],#pi85-detail');
    const verdict=currentScreen.querySelector('.p751-verdict');
    const matchup=currentScreen.querySelector('.p751-matchup');
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
    if(document.querySelector('#app[data-match-key] .p751-detail-screen')){
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
