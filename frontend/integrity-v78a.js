/* Tenis AI v7.8A — Integrity Guard + v7.8E6 Shadow Lab loader */
(() => {
  async function boot(){
    try{
      const r=await fetch('data/integrity_report_v78a.json?v='+Date.now());
      if(!r.ok)return;
      const d=await r.json();
      const host=document.querySelector('.status');
      if(!host||document.querySelector('#integrity-v78a-chip'))return;
      const el=document.createElement('span');
      el.id='integrity-v78a-chip';
      el.className='integrity-v78a-chip '+(d.status==='PASS'?'ok':'bad');
      el.textContent=d.status==='PASS'?`✓ INTEGRITY PASS · ${d.matches||0}`:`⚠ INTEGRITY FAIL · ${d.hard_errors||0}`;
      el.title=d.status==='PASS'?'Automatyczne testy spójności danych przeszły.':'Wykryto twardy błąd spójności danych.';
      host.appendChild(el);
    }catch{}
  }
  function bootShadowLab(){
    if(!document.querySelector('link[data-shadow-v78e6]')){
      const link=document.createElement('link');link.rel='stylesheet';link.href='shadow-lab-v78e6.css';link.dataset.shadowV78e6='1';document.head.appendChild(link);
    }
    if(!document.querySelector('script[data-shadow-v78e6]')){
      const script=document.createElement('script');script.src='shadow-lab-v78e6.js';script.dataset.shadowV78e6='1';document.body.appendChild(script);
    }
  }
  bootShadowLab();
  setTimeout(boot,500);
})();
