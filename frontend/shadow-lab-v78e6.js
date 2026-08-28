/* Tenis AI v7.8E9 — Shadow Lab inline signals */
(() => {
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }[c]));

  const sc=x=>x==null||!Number.isFinite(Number(x))
    ? 'N/D'
    : `${Number(x).toFixed(1).replace('.0','')}/100`;

  const pc=x=>x==null||!Number.isFinite(Number(x))
    ? '—'
    : `${Number(x).toFixed(1).replace('.0','')}%`;

  let current=[];
  let stats={};
  let active=false;

  async function safeJson(url,fallback){
    try{
      const r=await fetch(url+'?v='+Date.now());
      return r.ok?await r.json():fallback;
    }catch{
      return fallback;
    }
  }

  async function reload(){
    [current,stats]=await Promise.all([
      safeJson('data/shadow_current.json',[]),
      safeJson('data/shadow_stats.json',{})
    ]);

    if(!Array.isArray(current))current=[];
    if(!stats||typeof stats!=='object')stats={};
  }

  function tour(x){
    const t=String(x?.tour||'').toLowerCase();
    if(t.includes('chall'))return 'CH';
    if(t.includes('itf'))return 'ITF';
    return t.toUpperCase()||'TENIS';
  }

  function surface(x){
    const s=String(x?.surface||'').trim();
    if(!s)return '—';

    const k=s.toLowerCase();
    if(k==='hard')return 'Hard';
    if(k==='clay')return 'Clay';
    if(k==='grass')return 'Grass';
    return s;
  }

  function time(x){
    const d=new Date(x?.scheduled_time||'');
    return Number.isFinite(d.getTime())
      ? d.toLocaleTimeString('pl-PL',{
          hour:'2-digit',
          minute:'2-digit'
        })
      : '—';
  }

  function currentTourFilter(){
    try{
      return typeof filter!=='undefined'
        ? String(filter||'all')
        : 'all';
    }catch{
      return 'all';
    }
  }

  function shadowTourKey(x){
    const t=String(x?.tour||'').toLowerCase();
    if(t.includes('chall'))return 'challenger';
    if(t.includes('itf'))return 'itf';
    if(t.includes('wta'))return 'wta';
    if(t.includes('atp'))return 'atp';
    return t||'other';
  }

  function validSignals(x){
    return (Array.isArray(x?.signals)?x.signals:[])
      .filter(s=>Number.isFinite(Number(s?.score)))
      .filter(s=>Number(s.score)>=55&&Number(s.score)<72)
      .sort((a,b)=>Number(b.score)-Number(a.score));
  }

  function signalLabel(s){
    const label=String(s?.label||'Sygnał').trim();
    const pick=String(s?.pick||'').trim().toUpperCase();

    if(!pick)return label;
    if(label.toUpperCase().includes(pick))return label;

    return `${label} · ${pick}`;
  }

  function filteredRows(){
    const f=currentTourFilter();

    return current
      .filter(Boolean)
      .filter(x=>window.TENIS_AI_MATCH_TIME?.isCurrent?.(x)===true)
      .filter(x=>f==='all'||shadowTourKey(x)===f)
      .sort((a,b)=>{
        const as=validSignals(a).length?1:0;
        const bs=validSignals(b).length?1:0;

        if(as!==bs)return bs-as;

        return new Date(a.scheduled_time||0)
          -new Date(b.scheduled_time||0);
      });
  }

  function matchExists(x){
    try{
      return !!window.TENIS_AI_PROJECT_UI?.findMatch?.(
        String(x?.match_id??'')
      );
    }catch{
      return false;
    }
  }

  function player(name){
    return `<b class="v762-player-link"
      role="link"
      tabindex="0"
      title="Otwórz profil zawodnika">${esc(name)}</b>`;
  }

  function card(x){
    const rows=validSignals(x);
    const sig=rows[0]||null;
    const score=sig?Number(sig.score):null;
    const hasShadow=rows.length>0;
    const canOpen=matchExists(x)&&!!x.model_ready;

    const state=hasShadow
      ? 'SHADOW 55–71'
      : 'N/D';

    const reason=x.rejection_reason
      ||(hasShadow
        ?'Sygnał nie przekroczył progu zielonego 72/100.'
        :'Brak wystarczającej próbki do wiarygodnego sygnału.');

    const source=String(sig?.source_model||'adaptive');

    return `
      <article
        class="p751-match-card sl78-main-card ${hasShadow?'':'sl78-main-nodata'}"
        ${canOpen?`data-shadow-match="${esc(String(x.match_id))}"`:''}
        role="button"
        tabindex="0"
      >
        <div class="p751-match-meta">
          <span class="p751-status sl78-shadow-status">${state}</span>
          <b>${esc(tour(x))}</b>
          <span>${esc(x.tournament||'Turniej')}</span>
          <span>• ${esc(surface(x))}</span>
          <time>${esc(time(x))}</time>
        </div>

        <div class="p751-card-center">
          <div class="p751-names">
            ${player(x.p1)}
            <span>VS</span>
            ${player(x.p2)}
          </div>

          ${
            hasShadow
              ?`
                <div class="p751-top-pick">
                  <span>🧪 Odrzucony sygnał</span>
                  <b>${esc(signalLabel(sig))}</b>
                  <em>${sc(score)}</em>
                </div>

                ${
                  rows.length>1
                    ?`<div class="sl78-extra-signals">
                        ${rows.slice(1,4).map(s=>`
                          <div>
                            <span>${esc(signalLabel(s))}</span>
                            <b>${sc(s.score)}</b>
                          </div>
                        `).join('')}
                      </div>`
                    :''
                }
              `
              :`
                <div class="p751-top-pick sl78-nd-pick">
                  <span>ℹ️ Obserwacja</span>
                  <b>Brak rozliczalnego sygnału</b>
                  <em>N/D</em>
                </div>
              `
          }
        </div>

        <aside class="p751-strength">
          <span>Odrzucone sygnały</span>
          <b>${hasShadow?rows.length:'—'}</b>
          <small>${hasShadow?'zakres 55–71':'brak próbki'}</small>
        </aside>

        <div class="p753-match-total-preview sl78-reason">
          <span>
            ${hasShadow
              ?'🧪 Dlaczego nie jest zielony'
              :'ℹ️ Dlaczego N/D'}
          </span>

          <b>${esc(reason)}</b>

          <em>
            ${esc(x.p1)} n=${x.p1_matches??'—'}
            ·
            ${esc(x.p2)} n=${x.p2_matches??'—'}
          </em>
        </div>

        <footer>
          <span>🧪 Shadow Lab</span>
          <span>🧠 ${esc(source)}</span>
          <span>DANE ${esc(x.quality||'—')}</span>
          <b>${canOpen?'Analiza ›':hasShadow?'Sygnał Shadow':'N/D'}</b>
        </footer>
      </article>
    `;
  }

  function groupRows(rows){
    const groups=new Map();

    rows.forEach(x=>{
      const k=`${tour(x)}|${x.tournament||'Turniej'}`;

      if(!groups.has(k)){
        groups.set(k,{
          tour:tour(x),
          name:x.tournament||'Turniej',
          rows:[]
        });
      }

      groups.get(k).rows.push(x);
    });

    return [...groups.values()];
  }

  function groupsHtml(rows,openCount=4){
    if(!rows.length){
      return `
        <div class="p751-empty">
          <b>Brak sygnałów dla tego filtra.</b>
          <span>Wybierz „Wszystkie” albo inny tour.</span>
        </div>
      `;
    }

    return `
      <div class="p751-groups">
        ${groupRows(rows).map((g,i)=>`
          <details class="p751-group" ${i<openCount?'open':''}>
            <summary>
              <div>
                <span>${esc(g.tour)}</span>
                <b>${esc(g.name)}</b>
                <small>
                  ${g.rows.length}
                  ${g.rows.length===1?'mecz':'meczów'}
                  ·
                  ${esc([...new Set(g.rows.map(surface))].join('/'))}
                </small>
              </div>
              <i>⌄</i>
            </summary>

            <div class="p751-group-body">
              ${g.rows.map(card).join('')}
            </div>
          </details>
        `).join('')}
      </div>
    `;
  }

  function summary(signalRows,ndRows){
    const o=stats.overall||{};

    const signalCount=signalRows.reduce(
      (n,x)=>n+validSignals(x).length,
      0
    );

    return `
      <section class="sl78-inline-summary">
        <div>
          <b>🧪 Shadow Lab</b>
          <span>Tu śledzimy odrzucone SYGNAŁY, nie całe mecze.</span>
        </div>

        <div class="sl78-inline-numbers">
          <span>Sygnały 55–71 <b>${signalCount}</b></span>
          <span>Mecze Shadow <b>${signalRows.length}</b></span>
          <span>N/D <b>${ndRows.length}</b></span>
          <span>Skuteczność <b>${o.accuracy==null?'—':pc(o.accuracy)}</b></span>
        </div>

        <small>
          Ten sam mecz może być również na głównej liście,
          jeżeli ma inny zielony sygnał ≥72/100.
          Shadow nie miesza się z oficjalną skutecznością modelu.
          Nauka progów dopiero po minimum
          ${stats.learning_target_sample||300}
          rozliczalnych sygnałach.
        </small>
      </section>
    `;
  }

  function updateTourCounts(){
    const counts={
      all:current.length,
      atp:0,
      wta:0,
      challenger:0,
      itf:0
    };

    current.forEach(x=>{
      const k=shadowTourKey(x);

      if(Object.prototype.hasOwnProperty.call(counts,k)){
        counts[k]++;
      }
    });

    document
      .querySelectorAll('#tour-nav [data-filter]')
      .forEach(b=>{
        const k=b.dataset.filter;
        const c=b.querySelector('.count');

        if(c&&Object.prototype.hasOwnProperty.call(counts,k)){
          c.textContent=String(counts[k]);
        }
      });
  }

  function overlayShadowInfo(x){
    const rows=validSignals(x);
    if(!rows.length)return;

    requestAnimationFrame(()=>{
      const screen=document.querySelector(
        '#p751-match-overlay .p751-detail-screen'
      );

      if(!screen)return;

      screen.querySelector('.sl78-overlay-note')?.remove();

      const matchup=screen.querySelector('.p751-matchup');
      if(!matchup)return;

      const box=document.createElement('section');
      box.className='sl78-overlay-note';

      box.innerHTML=`
        <header>
          <b>🧪 Shadow Lab · sygnały odrzucone</b>
          <span>55–71/100</span>
        </header>

        <p>
          Poniższe sygnały nie są oficjalnymi zielonymi typami.
          Pełna analiza głównego modelu jest dalej poniżej.
        </p>

        <div>
          ${rows.slice(0,5).map(s=>`
            <span>
              ${esc(signalLabel(s))}
              <b>${sc(s.score)}</b>
            </span>
          `).join('')}
        </div>
      `;

      matchup.insertAdjacentElement('afterend',box);
    });
  }

  function bindCards(){
    document
      .querySelectorAll('[data-shadow-match]')
      .forEach(b=>{
        const open=()=>{
          const id=String(b.dataset.shadowMatch||'');

          const x=current.find(
            z=>String(z?.match_id??'')===id
          );

          window.TENIS_AI_PROJECT_UI?.openMatch?.(id);

          if(x){
            overlayShadowInfo(x);
          }
        };

        b.onclick=e=>{
          if(e.target.closest?.('.v762-player-link'))return;
          open();
        };

        b.onkeydown=e=>{
          if(e.target.closest?.('.v762-player-link'))return;
          if(e.key!=='Enter'&&e.key!==' ')return;
          e.preventDefault();
          open();
        };
      });
  }

  function bindCollapse(){
    const c=document.querySelector('#collapse-all');
    const e=document.querySelector('#expand-all');

    if(c&&!c.dataset.shadowBound){
      c.dataset.shadowBound='1';

      c.addEventListener('click',()=>{
        if(!active)return;

        document
          .querySelectorAll('#app .p751-group')
          .forEach(d=>d.open=false);
      });
    }

    if(e&&!e.dataset.shadowBound){
      e.dataset.shadowBound='1';

      e.addEventListener('click',()=>{
        if(!active)return;

        document
          .querySelectorAll('#app .p751-group')
          .forEach(d=>d.open=true);
      });
    }
  }

  function syncButton(){
    const b=document.querySelector('#app [data-shadow-open]');
    if(b){
      b.classList.toggle('active',active);
    }
  }

  function renderShadow(){
    active=true;

    window.TENIS_AI_PROJECT_UI?.renderMatches?.();

    const app=document.querySelector('#app');
    if(!app)return;

    const focus=app.querySelector('.p751-focus');
    if(!focus)return;

    [...app.children].forEach(el=>{
      if(el!==focus)el.remove();
    });

    const rows=filteredRows();
    const signalRows=rows.filter(x=>validSignals(x).length);
    const ndRows=rows.filter(x=>!validSignals(x).length);

    const holder=document.createElement('div');
    holder.className='sl78-inline-view';

    holder.innerHTML=`
      ${summary(signalRows,ndRows)}

      <section class="sl78-signal-section">
        <div class="sl78-section-title">
          <b>🎯 Odrzucone sygnały 55–71</b>
          <span>${signalRows.length} meczów</span>
        </div>

        ${groupsHtml(signalRows)}
      </section>

      ${
        ndRows.length
          ?`
            <details class="sl78-nd-wrap">
              <summary>
                ℹ️ Obserwacje bez pełnej próbki
                <b>${ndRows.length}</b>
              </summary>

              <div class="sl78-nd-body">
                ${groupsHtml(ndRows,0)}
              </div>
            </details>
          `
          :''
      }
    `;

    app.appendChild(holder);

    syncButton();
    updateTourCounts();
    bindCards();
    bindCollapse();
  }

  async function openShadow(){
    active=true;
    await reload();
    renderShadow();
  }

  document.addEventListener('click',e=>{
    const normalFocus=e.target.closest(
      '.p751-focus button:not([data-shadow-open])'
    );

    if(normalFocus){
      active=false;
    }

    const bottom=e.target.closest(
      '#p751-bottom-nav [data-p751-nav]'
    );

    if(bottom){
      active=false;
    }

    const tourButton=e.target.closest(
      '#tour-nav [data-filter]'
    );

    if(tourButton&&active){
      setTimeout(renderShadow,0);
    }
  },true);

  reload();

  window.TENIS_AI_SHADOW_LAB={
    reload,
    open:openShadow,
    render:renderShadow
  };
})();
