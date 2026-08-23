/* Tenis AI v7.2 — Serve Props: asy + podwójne błędy */
(() => {
  if(typeof renderMatchDetail!=='function') return;
  const baseRender=renderMatchDetail;
  const escS=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

  function poissonOver(mean,line){
    mean=Number(mean);line=Number(line);
    if(!Number.isFinite(mean)||mean<0||!Number.isFinite(line))return null;
    const threshold=Math.floor(line)+1;
    let term=Math.exp(-mean),cdf=term;
    for(let k=1;k<threshold;k++){term*=mean/k;cdf+=term}
    return clamp(1-cdf,0,1);
  }
  function fair(p){return p>0.001?(1/p).toFixed(2):'—'}
  function lineValue(x){return Number.isFinite(Number(x))?Number(x):0.5}

  function market(kind,mkt,side,id){
    const title=kind==='aces'?'🎯 Asy':'⚠️ Podwójne błędy';
    if(!mkt?.ready)return `<div class="sp72-market nd"><div class="sp72-market-head"><b>${title}</b><span>N/D</span></div><p>Za mało wiarygodnych meczów ze statystyką ${kind==='aces'?'asów':'podwójnych błędów'}.</p></div>`;
    const mean=Number(mkt.mean);
    const def=lineValue(mkt.suggested_line);
    const key=`${id}-${side}-${kind}`;
    return `<div class="sp72-market" data-sp-market="${key}" data-sp-mean="${mean}">
      <div class="sp72-market-head"><b>${title}</b><span>MODEL ŚR. ${mean.toFixed(1)}</span></div>
      <div class="sp72-market-meta"><span>${mkt.sample||0} meczów</span><span>cały mecz · BO3</span></div>
      <div class="sp72-line-tool">
        <label>Linia buka <input type="number" inputmode="decimal" min="0.5" max="${kind==='aces'?'20.5':'12.5'}" step="0.5" value="${def.toFixed(1)}" data-sp-line></label>
        <div class="sp72-probs" data-sp-output></div>
      </div>
    </div>`;
  }

  function histAvg(side,kind){
    const h=side?.history?.all?.['10']?.[kind];
    if(!h||h.avg==null)return 'N/D';
    return `${Number(h.avg).toFixed(1)} (${h.sample||0} meczów)`;
  }

  function player(m,side){
    const s=m.serve_props_v72?.[side]||{};
    const name=m[side]||'—';
    return `<article class="sp72-player">
      <div class="sp72-player-name"><b>${escS(name)}</b><span>DANE ${escS(s.quality||'LOW')}</span></div>
      <div class="sp72-history-mini">
        <span>Śr. asy · ostatnie 10 <b>${escS(histAvg(s,'aces'))}</b></span>
        <span>Śr. DF · ostatnie 10 <b>${escS(histAvg(s,'double_faults'))}</b></span>
      </div>
      ${market('aces',s.aces,side,m.id||'m')}
      ${market('df',s.double_faults,side,m.id||'m')}
    </article>`;
  }

  function box(m){
    const s=m.serve_props_v72;if(!s)return '';
    return `<section class="sp72-box">
      <div class="sp72-head"><div><b>⚡ Serve Props v7.2 · asy + podwójne błędy</b><small>forma serwisowa + nawierzchnia + przeciwnik + przewidywana długość meczu</small></div><span>${s.ready?'MODEL':'N/D'}</span></div>
      <div class="sp72-info">Wpisz dokładnie linię, którą widzisz u bukmachera. Dostaniesz modelowe OVER/UNDER i „uczciwy kurs” wynikający z modelu.</div>
      <div class="sp72-grid">${player(m,'p1')}${player(m,'p2')}</div>
      <div class="sp72-foot">„Uczciwy kurs” = 1 / modelowe prawdopodobieństwo. Sama niższa linia nie oznacza jeszcze value — kurs buka musi być lepszy od kursu modelowego. Model count jest estymacją BO3 i nie jest jeszcze kalibrowanym rynkiem bukmacherskim.</div>
    </section>`;
  }

  renderMatchDetail=function(m){
    const html=baseRender(m),panel=box(m);if(!panel)return html;
    return html.replace('<div class="match-detail">',`<div class="match-detail">${panel}`);
  };

  function refreshMarket(el){
    const mean=Number(el.dataset.spMean),input=el.querySelector('[data-sp-line]'),out=el.querySelector('[data-sp-output]');
    if(!input||!out)return;
    const line=Number(input.value);
    const p=poissonOver(mean,line);
    if(p==null)return;
    const over=100*p,under=100*(1-p);
    const oc=over>=67?'strong':over>=58?'lean':'';
    const uc=under>=67?'strong':under>=58?'lean':'';
    out.innerHTML=`<div class="${oc}"><span>OVER ${line.toFixed(1)}</span><b>${over.toFixed(0)}%</b><small>fair ${fair(p)}</small></div><div class="${uc}"><span>UNDER ${line.toFixed(1)}</span><b>${under.toFixed(0)}%</b><small>fair ${fair(1-p)}</small></div>`;
  }
  function refreshAll(root=document){root.querySelectorAll('[data-sp-market]').forEach(refreshMarket)}
  document.addEventListener('input',e=>{if(e.target.matches?.('[data-sp-line]'))refreshMarket(e.target.closest('[data-sp-market]'))});
  document.addEventListener('change',e=>{if(e.target.matches?.('[data-sp-line]'))refreshMarket(e.target.closest('[data-sp-market]'))});
  const obs=new MutationObserver(()=>{
    // v8.1: mutacje profilu nie mogą uruchamiać pełnego skanu dokumentu.
    if(window.TENIS_AI_PLAYER_PROFILE_ACTIVE)return;
    requestAnimationFrame(()=>refreshAll(document));
  });
  obs.observe(document.body,{childList:true,subtree:true});
  setTimeout(()=>refreshAll(document),300);

  // Add ace / DF history to the full player profile too.
  const profile=document.querySelector('#player-profile-panel'),search=document.querySelector('#player-search-input');
  function same(a,b){return String(a||'').localeCompare(String(b||''),'pl',{sensitivity:'base'})===0}
  function currentData(name){
    try{
      const rows=(Array.isArray(all)?all:[]).filter(m=>same(m.p1,name)||same(m.p2,name));
      const m=rows.find(x=>x.serve_props_v72);if(!m)return null;
      return {m,side:same(m.p1,name)?'p1':'p2',data:m.serve_props_v72?.[same(m.p1,name)?'p1':'p2']};
    }catch{return null}
  }
  function histRows(kind,h){
    if(!h)return '<div class="player-empty">N/D</div>';
    const lines=Object.entries(h.over||{}).filter(([,v])=>v?.pct!=null&&v.n>=3)
      .sort((a,b)=>Math.abs(Number(a[0])-Number(h.avg||0))-Math.abs(Number(b[0])-Number(h.avg||0))).slice(0,4);
    return `<div class="sp72-profile-stat"><div><span>Średnia</span><b>${h.avg==null?'N/D':Number(h.avg).toFixed(1)}</b><small>${h.sample||0} meczów</small></div>${lines.map(([l,v])=>`<div><span>Over ${l}</span><b>${Number(v.pct).toFixed(0)}%</b><small>${v.hits}/${v.n}</small></div>`).join('')}</div>`;
  }
  function injectProfile(){
    if(!profile||profile.hidden||profile.querySelector('#sp72-profile'))return;
    const name=search?.value?.trim();if(!name)return;
    const d=currentData(name);if(!d?.data?.history)return;
    const h=d.data.history;
    const sec=document.createElement('section');sec.className='player-section sp72-profile';sec.id='sp72-profile';
    sec.innerHTML=`<div class="player-section-title"><b>⚡ Asy i podwójne błędy</b><small>ostatnie 5 / 10 / 20</small></div>
      <div class="sp72-profile-controls"><button data-spw="5">5</button><button class="active" data-spw="10">10</button><button data-spw="20">20</button><button class="active" data-sps="all">Wszystkie</button><button data-sps="surface">${escS((h.surface_name||'surface').toUpperCase())}</button></div>
      <div data-sp-profile-body></div>`;
    const target=[...profile.querySelectorAll('.player-section')].find(x=>x.querySelector('.player-section-title b')?.textContent.includes('Profil Tendencji'));
    if(target)target.insertAdjacentElement('afterend',sec);else profile.appendChild(sec);
    let win='10',scope='all';
    const render=()=>{
      const b=h?.[scope]?.[win];
      sec.querySelector('[data-sp-profile-body]').innerHTML=`<div class="sp72-profile-two"><div><h4>🎯 Asy</h4>${histRows('aces',b?.aces)}</div><div><h4>⚠️ Podwójne błędy</h4>${histRows('df',b?.double_faults)}</div></div>`;
    };
    sec.querySelectorAll('[data-spw]').forEach(b=>b.onclick=()=>{win=b.dataset.spw;sec.querySelectorAll('[data-spw]').forEach(x=>x.classList.toggle('active',x===b));render()});
    sec.querySelectorAll('[data-sps]').forEach(b=>b.onclick=()=>{scope=b.dataset.sps;sec.querySelectorAll('[data-sps]').forEach(x=>x.classList.toggle('active',x===b));render()});
    render();
  }
  function mountProfile(){injectProfile()}
  window.TENIS_AI_SERVE_PROPS_V81={mountProfile,refreshAll};
  if(profile&&!profile.hidden)setTimeout(injectProfile,80);
})();