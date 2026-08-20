/* Tenis AI v7.0.3 — prosty przewodnik po modelach */
(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const STORE='tenis-ai-v703-guide-open';

  const EXPLAIN={
    consensus:{
      icon:'⚡',name:'Consensus',
      short:'Najprościej na start: pokazuje typy, przy których zgadza się kilka modeli.',
      use:'Gdy chcesz szybko zobaczyć najmocniejsze wspólne sygnały.',
      how:'Porównuje 5 wariantów: Adaptive, Early Hold, Serve/Return, Form i Surface. Im więcej z nich popiera ten sam typ, tym mocniejszy jest consensus.'
    },
    adaptive:{
      icon:'🧠',name:'Adaptive',
      short:'Model ogólny: forma + serwis/return + nawierzchnia + ranking + zmęczenie.',
      use:'Do ogólnej analizy meczu, setów i gemów.',
      how:'Łączy wiele danych przedmeczowych. To model bazowy. Jeśli Early Hold ma PBP OK, dla początku 1. seta pierwszeństwo ma specjalista PBP.'
    },
    early:{
      icon:'🎯',name:'Early Hold',
      short:'Specjalista od początku 1. seta i pierwszych gemów serwisowych.',
      use:'Do 1:1 po 2, 2:2 po 4, 3:3 po 6, overów 1. seta i prowadzenia po 6.',
      how:'Przy PBP OK korzysta z prawdziwych danych point-by-point: 1., 2. i 3. własnego gema serwisowego. Gdy danych jest za mało, pokazuje N/D zamiast zgadywać.'
    },
    serve:{
      icon:'🎾',name:'Serve/Return',
      short:'Patrzy przede wszystkim na siłę serwisu i returnu obu zawodników.',
      use:'Gdy chcesz ocenić holdy, przełamania i przewagę jakości gry.',
      how:'Mocniej waży hold, break, wygrane punkty przy serwisie i returnie. Mniej ufa samej ogólnej formie.'
    },
    form:{
      icon:'🔥',name:'Form',
      short:'Mocniej patrzy na to, co zawodnik robi ostatnio.',
      use:'Gdy ważna jest świeża forma, seria wyników i obciążenie.',
      how:'Większą wagę dostają ostatnie wyniki, sety, świeżość i zmęczenie. Starsza forma ma mniejsze znaczenie.'
    },
    surface:{
      icon:'🏟️',name:'Surface',
      short:'Sprawdza, jak zawodnicy wyglądają właśnie na tej nawierzchni.',
      use:'Gdy hard, clay lub grass mocno zmienia obraz meczu.',
      how:'Najbardziej ufa próbce z bieżącej nawierzchni. Jeżeli takich meczów jest mało, sygnał jest wygaszany.'
    }
  };

  const safe = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function activeId(){
    const b=$('[data-model].active');
    return b?.dataset.model || 'consensus';
  }

  function setDesc(id){
    const d=EXPLAIN[id] || EXPLAIN.consensus;
    const el=$('#model-description');
    if(el) el.textContent=d.short;
    const box=$('#model-guide-selected');
    if(box) box.innerHTML=`<span>${d.icon}</span><div><b>${safe(d.name)}</b><small>${safe(d.use)}</small></div>`;
  }

  function modelCard(id){
    const d=EXPLAIN[id];
    return `<article class="mg-model-card" data-guide-model="${id}">
      <div class="mg-model-title"><span>${d.icon}</span><b>${safe(d.name)}</b></div>
      <p>${safe(d.short)}</p>
      <div><span>Najlepszy do</span><b>${safe(d.use)}</b></div>
      <small>${safe(d.how)}</small>
    </article>`;
  }

  function html(){
    return `<section class="model-guide" id="model-guide">
      <button class="mg-summary" id="model-guide-toggle" type="button" aria-expanded="false">
        <div>
          <b>❓ Nie wiesz, który model wybrać?</b>
          <small><strong>Consensus</strong> na start · <strong>Early Hold</strong> początek 1. seta · <strong>Adaptive</strong> cały mecz</small>
        </div>
        <span class="mg-chev">⌄</span>
      </button>

      <div class="mg-selected" id="model-guide-selected"></div>

      <div class="mg-body" id="model-guide-body" hidden>
        <div class="mg-intro">
          <b>Jak Tenis AI dochodzi do wyniku?</b>
          <div class="mg-flow">
            <span><i>1</i><strong>Dane</strong><small>forma, serwis, return, nawierzchnia, PBP</small></span>
            <span><i>2</i><strong>Model</strong><small>każdy patrzy na mecz trochę inaczej</small></span>
            <span><i>3</i><strong>Sygnał</strong><small>ocena 0–100 + konkretny typ</small></span>
          </div>
        </div>

        <div class="mg-quick">
          <div><span>⚡</span><b>Chcę szybko</b><small>Consensus</small></div>
          <div><span>🎯</span><b>Gram początek seta</b><small>Early Hold</small></div>
          <div><span>🧠</span><b>Chcę cały obraz</b><small>Adaptive</small></div>
        </div>

        <div class="mg-models">${Object.keys(EXPLAIN).map(modelCard).join('')}</div>

        <section class="mg-glossary">
          <h4>📖 Co oznaczają napisy i liczby?</h4>
          <div><b>72 / 100</b><span>Siła sygnału modelu. To <strong>nie jest gwarancja</strong> ani pewne 72% szans.</span></div>
          <div><b>🟢 Zielony</b><span>Sygnał osiągnął nasz próg 72/100. Nadal może nie wejść.</span></div>
          <div><b>PBP OK</b><span>Dla zawodnika mamy min. 5 wiarygodnych meczów point-by-point. Early Hold dla całego meczu działa w pełni dopiero, gdy warunek spełniają obaj.</span></div>
          <div><b>N/D</b><span>Za mało wiarygodnych danych. Aplikacja celowo nie zgaduje.</span></div>
          <div><b>EHS</b><span>Early Hold Score 0–100: stabilność 1., 2. i 3. własnego gema serwisowego w 1. secie. To nie jest procent wygranej meczu.</span></div>
          <div><b>3/5, 4/5…</b><span>Tyle z 5 modeli specjalistycznych popiera ten sam sygnał w Consensus.</span></div>
          <div><b>PREDYKCJA BO3</b><span>Wartość policzona przez model dla meczu best-of-3. To nie jest surowa statystyka ani gwarancja wyniku.</span></div>
          <div><b>Jakość danych</b><span>Ocena 0–100 mówi, jak kompletne i użyteczne są dane do analizy tego meczu. Nie mówi, że zawodnik ma tyle procent szans na wygraną.</span></div>
          <div><b>Częstość hist.</b><span>Ile razy zdarzenie naprawdę wystąpiło w poprzednich meczach zawodnika, np. 8/10 = 80%. To opis przeszłości, nie prognoza.</span></div>
          <div><b>Skuteczność AI</b><span>Jak często wcześniejsze zapisane typy Tenis AI zostały później trafnie rozliczone. To osobna liczba od tendencji zawodnika.</span></div>
        </section>

        <div class="mg-warning">
          <b>Ważne</b>
          <span>Tenis AI pomaga analizować dane i scenariusze. Oceny modeli nie są kursem bukmacherskim ani obietnicą wyniku.</span>
        </div>
      </div>
    </section>`;
  }

  function install(){
    const switcher=$('#model-switcher');
    const buttons=switcher?.querySelector('.model-buttons');
    if(!switcher || !buttons || $('#model-guide')) return;

    buttons.insertAdjacentHTML('afterend',html());

    const toggle=$('#model-guide-toggle');
    const body=$('#model-guide-body');
    let open=false;
    try{open=localStorage.getItem(STORE)==='1'}catch{}
    function apply(){
      body.hidden=!open;
      toggle.setAttribute('aria-expanded',String(open));
      $('#model-guide')?.classList.toggle('open',open);
      try{localStorage.setItem(STORE,open?'1':'0')}catch{}
    }
    toggle.onclick=()=>{open=!open;apply()};
    apply();

    $$('[data-guide-model]').forEach(card=>{
      card.onclick=()=>{
        const id=card.dataset.guideModel;
        document.querySelector(`[data-model="${id}"]`)?.click();
        card.scrollIntoView({behavior:'smooth',block:'nearest'});
      };
    });

    $$('[data-model]').forEach(btn=>{
      btn.addEventListener('click',()=>setTimeout(()=>setDesc(btn.dataset.model),0));
    });

    setDesc(activeId());
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();