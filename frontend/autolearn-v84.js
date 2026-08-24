/* Tenis AI v8.4B — AutoLearn bridge + model comparison UI
   v8.4C adds read-only telemetry for specialist/ML/generator performance.
*/
(() => {
  'use strict';
  const VERSION='v8.4B';
  const REPORT='data/autolearn_v84.json';
  const TELEMETRY='data/model_telemetry_v84c.json';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const brier=x=>num(x)==null?'—':Number(x).toFixed(3);
  const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
  let reportPromise=null,telemetryPromise=null;

  function lineOf(s){
    const direct=num(s?.line??s?.selected_line??s?.suggested_line);if(direct!=null)return direct;
    const p=String(s?.key||s?.signal_key||'').split('|');
    return p.length>1?num(p[1]):null;
  }
  function marketAlias(m){
    return ({match_win:'match_winner',set1_win:'set1_winner',set2_win:'set2_winner',set3_win:'set3_winner'})[String(m||'').toLowerCase()]||String(m||'').toLowerCase();
  }
  function scoreFor(match,signal){
    const a=match?.autolearn_v84;if(!a)return null;
    const key=String(signal?.key||signal?.signal_key||'');
    const direct=a?.by_key?.[key];
    if(direct)return {...direct,status:a.status,weights:a.weights,weight_policy:a.weight_policy||null};
    const market=marketAlias(signal?.market),pick=norm(signal?.pick),line=lineOf(signal);
    const row=(a?.signals||[]).find(x=>{
      if(marketAlias(x?.market)!==market||norm(x?.pick)!==pick)return false;
      const xl=lineOf(x);
      return line==null?xl==null:xl!=null&&Math.abs(xl-line)<0.001;
    });
    return row?{...row,status:a.status,weights:a.weights,weight_policy:a.weight_policy||null}:null;
  }

  function modelVoteText(row){
    if(!row)return 'AI N/D';
    const parts=[];
    if(num(row.catboost)!=null)parts.push(`C${Math.round(Number(row.catboost))}`);
    if(num(row.tabpfn)!=null)parts.push(`T${Math.round(Number(row.tabpfn))}`);
    if(num(row.current)!=null)parts.push(`E${Math.round(Number(row.current))}`);
    return parts.length?`Ensemble ${parts.join('/')}`:'Ensemble';
  }

  async function loadReport(force=false){
    if(force)reportPromise=null;
    if(!reportPromise)reportPromise=fetch(`${REPORT}?v=84b1&ts=${Date.now()}`,{cache:'no-store'})
      .then(r=>r.ok?r.json():{}).catch(()=>({}));
    return reportPromise;
  }
  async function loadTelemetry(force=false){
    if(force)telemetryPromise=null;
    if(!telemetryPromise)telemetryPromise=fetch(`${TELEMETRY}?v=84c1&ts=${Date.now()}`,{cache:'no-store'})
      .then(r=>r.ok?r.json():{}).catch(()=>({}));
    return telemetryPromise;
  }
  function metric(report,id){
    const track=report?.tracking?.[id]||{};
    const val=report?.validation?.[id]||{};
    const useTrack=Number(track?.selected_n||0)>=5;
    return {data:useTrack?track:val,scope:useTrack?'TRACKING':'WALK-FORWARD'};
  }
  function card(report,id,label,icon,status){
    const {data,scope}=metric(report,id);
    const st=String(status||'N/D').toUpperCase();
    return `<article class="al84-card">
      <header><span>${icon}</span><div><b>${esc(label)}</b><small>${esc(scope)}</small></div><em class="${st==='ACTIVE'||st==='OK'?'ok':st==='UNAVAILABLE'?'off':'shadow'}">${esc(st)}</em></header>
      <strong>${pct(data?.accuracy)}</strong>
      <div class="al84-meta"><span>wybrane n=${Number(data?.selected_n||0)}</span><span>Brier ${brier(data?.brier)}</span><span>log-loss ${num(data?.log_loss)==null?'—':Number(data.log_loss).toFixed(3)}</span></div>
    </article>`;
  }

  const TELEMETRY_ORDER=['adaptive','early','serve','form','surface','consensus','current','catboost','tabpfn','ensemble','dynamic','generator'];
  function scopeModel(telemetry,scope,id){return telemetry?.scopes?.[scope]?.by_model?.[id]||{}}
  function roiText(m){return num(m?.roi)==null?'N/D':pct(m.roi)}
  function telemetryRows(telemetry){
    return TELEMETRY_ORDER.map(id=>{
      const d7=scopeModel(telemetry,'7d',id),d30=scopeModel(telemetry,'30d',id);
      const label=d30.label||d7.label||telemetry?.models?.[id]||id;
      return `<tr>
        <td><b>${esc(label)}</b><small>${id==='generator'?'finalny wybór':'próg ≥65'}</small></td>
        <td>${Number(d7.selected_n||0)}<small>${pct(d7.accuracy)}</small></td>
        <td>${Number(d30.hits||0)}–${Number(d30.misses||0)}</td>
        <td><b>${pct(d30.accuracy)}</b><small>n=${Number(d30.selected_n||0)}</small></td>
        <td>${brier(d30.brier)}</td>
        <td>${roiText(d30)}<small>${Number(d30.odds_n||0)?`kursy n=${Number(d30.odds_n||0)}`:'brak kursów'}</small></td>
      </tr>`;
    }).join('');
  }
  function agreementBlock(telemetry,title,key){
    const data=telemetry?.agreement?.[key]||{};
    const labels={strong_consensus:'mocna zgodność',majority:'większość',weak:'słabe',conflict:'konflikt'};
    const rows=['strong_consensus','majority','weak','conflict'].map(id=>{
      const x=data[id]||{};return `<span><b>${esc(labels[id])}</b> n=${Number(x.n||0)} · ${pct(x.accuracy)}</span>`;
    }).join('');
    return `<div class="al84-agreement"><b>${esc(title)}</b><div>${rows}</div></div>`;
  }
  function telemetryHtml(telemetry){
    if(!telemetry||telemetry.version!=='v8.4C'){
      return `<section class="al84-telemetry"><div class="al84-telemetry-head"><b>📡 TELEMETRIA v8.4C</b><span>OCZEKUJE NA PIERWSZY RAPORT</span></div><p class="al84-note">Moduł nie zmienia typów. Po pierwszym przebiegu workflow pokaże skuteczność modeli i segmentów.</p></section>`;
    }
    const top=(telemetry.top_segments_30d||[]).slice(0,6).map(x=>`<span><b>${esc(x.label)}</b> · ${esc(x.dimension)}=${esc(x.value)} · n=${Number(x.selected_n||0)} · ${pct(x.accuracy)}</span>`).join('');
    return `<section class="al84-telemetry">
      <div class="al84-telemetry-head"><div><b>📡 TELEMETRIA v8.4C</b><small>Modele bazowe + ML + finalny Generator AI</small></div><span>${esc(telemetry.status||'COLLECTING')}</span></div>
      <div class="al84-table-wrap"><table class="al84-table"><thead><tr><th>Model</th><th>7 dni</th><th>HIT–MISS 30d</th><th>Accuracy 30d</th><th>Brier</th><th>ROI</th></tr></thead><tbody>${telemetryRows(telemetry)}</tbody></table></div>
      <div class="al84-agreement-grid">${agreementBlock(telemetry,'Zgodność modeli bazowych','specialists')}${agreementBlock(telemetry,'Zgodność Current / CatBoost / TabPFN','ml')}</div>
      <div class="al84-top-segments"><b>Najlepsze segmenty 30d</b><div>${top||'<span>Za mała próbka — zbieramy dane.</span>'}</div></div>
      <p class="al84-note">ROI pokazujemy tylko z rzeczywiście zapisanych kursów; brak kursu = N/D. Segmenty są na razie telemetryką i nie zmieniają automatycznie wag produkcyjnych.</p>
    </section>`;
  }

  function html(report,telemetry){
    const models=report?.models||{},w=report?.weights||{},tr=report?.training||{},gen=report?.generator||{};
    const tab=models.tabpfn||{};
    return `<section id="al84-performance" class="al84-performance">
      <div class="al84-head"><div><span>🤖 AUTOLEARN v8.4B</span><h3>Porównanie modeli AI</h3><p>Te same rozliczone sygnały, osobno mierzona jakość i finalny selector generatora.</p></div><b>${esc(report?.status||'COLLECTING')}</b></div>
      <div class="al84-grid">
        ${card(report,'current','Current Engine · kalibrowany','🧠',models.current?.status||'active')}
        ${card(report,'catboost','CatBoost','🐱',models.catboost?.status||'collecting')}
        ${card(report,'tabpfn','TabPFN-2','🧬',tab.status||'unavailable')}
        ${card(report,'generator','Ensemble Generator','⚡',models.ensemble?.status||'fallback')}
      </div>
      <div class="al84-weights"><b>Wagi produkcyjne</b><span>Engine ${Math.round(Number(w.current||0)*100)}%</span><span>CatBoost ${Math.round(Number(w.catboost||0)*100)}%</span><span>TabPFN ${Math.round(Number(w.tabpfn||0)*100)}%</span></div>
      <div class="al84-policy"><b>Kalibracja Engine</b><span>${esc(report?.current_calibration?.gate_status||report?.current_calibration?.status||'N/D')}</span><small>${report?.current_calibration?.status==='active'?`Platt · TRAIN n=${Number(report?.current_calibration?.fit_rows||0)} · gate CAL n=${Number(report?.current_calibration?.gate_rows||0)} · ΔBrier ${num(report?.current_calibration?.gate_brier_delta)==null?'—':Number(report.current_calibration.gate_brier_delta).toFixed(4)}`:`Identity · ${esc(report?.current_calibration?.reason||'gate odrzucił kalibrator lub próbka za mała')}`}</small></div>
      <div class="al84-policy"><b>Stabilność Ensemble</b><span>${report?.weight_policy?.stability?.guard_active?'GUARD':'PEŁNA'}</span><small>${report?.weight_policy?.stability?.guard_active?`CAL ${Number(report.weight_policy.stability.calibration_matches||0)} meczów · max model ${Math.round(Number(report.weight_policy.stability.single_model_cap||0.8)*100)}% · Engine min ${Math.round(Number(report.weight_policy.stability.current_floor||0)*100)}%`:'Próbka CAL wystarczająca do pełnej optymalizacji wag'}</small></div>
      <div class="al84-policy"><b>Challenger</b><span>${esc(report?.weight_policy?.status||'N/D')}</span><small>${esc(report?.weight_policy?.reason||report?.weight_policy?.evidence||'waga ograniczona guardem jakości')}</small></div>
      <div class="al84-foot"><span>Trening: ${Number(tr.rows||0)} sygnałów · ${Number(tr.matches||0)} meczów</span><span>Próg bazowy: ${pct(gen.selection_threshold)}</span>${tab.reason?`<span>TabPFN: ${esc(tab.reason)}</span>`:''}</div>
      ${telemetryHtml(telemetry)}
      <p class="al84-note">Accuracy dotyczy wyborów modelu na rozliczonej próbce, nie jest gwarancją przyszłego wyniku. Brier: niżej = lepiej.</p>
    </section>`;
  }
  async function injectPerformance(){
    const host=document.querySelector('#pc77');if(!host)return;
    const [report,telemetry]=await Promise.all([loadReport(true),loadTelemetry(true)]);if(!document.querySelector('#pc77'))return;
    document.querySelector('#al84-performance')?.remove();
    host.insertAdjacentHTML('afterbegin',html(report,telemetry));
  }
  function scheduleInject(){[0,120,450,1000].forEach(ms=>setTimeout(injectPerformance,ms))}

  if(typeof renderStats==='function'){
    const base=renderStats;
    renderStats=function(){const r=base.apply(this,arguments);scheduleInject();return r};
  }

  window.TENIS_AI_AUTOLEARN_V84={version:VERSION,scoreFor,modelVoteText,loadReport,loadTelemetry,injectPerformance};
})();
