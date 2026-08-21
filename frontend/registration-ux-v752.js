/* Tenis AI v7.5.2 — Registration UX
   Clear rules + live validation + friendly Supabase auth errors.
*/
(() => {
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const USER_RE=/^[\p{L}\p{N}_.-]+$/u;
  const EMAIL_RE=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const RATE_KEY='tenis-ai-register-rate-limit-until';

  const form=()=>document.querySelector('#account-auth-form');
  const msg=()=>document.querySelector('#account-form-message');
  const registerMode=()=>Boolean(form()?.elements?.username);

  function rateUntil(){
    const t=Number(localStorage.getItem(RATE_KEY)||0);
    return Number.isFinite(t)?t:0;
  }
  function setRateCooldown(ms=10*60*1000){
    try{localStorage.setItem(RATE_KEY,String(Date.now()+ms))}catch{}
  }

  function rulesHtml(){
    return `<section id="reg-rules-v752" class="reg-rules-v752">
      <div class="reg-rules-title"><span>ℹ️</span><div><b>Zasady rejestracji</b><small>Wypełnij dokładnie tak — od razu pokażemy, co jest OK.</small></div></div>
      <div class="reg-rules-grid">
        <div data-rule="username"><span>Nick</span><b>3–24 znaki</b><small>Litery, cyfry, <code>_</code> <code>.</code> <code>-</code>. Bez spacji i @.</small></div>
        <div data-rule="email"><span>E-mail</span><b>Prawdziwy adres</b><small>Bez spacji. Jeśli potwierdzanie maila jest włączone, musisz mieć dostęp do skrzynki.</small></div>
        <div data-rule="password"><span>Hasło</span><b>Minimum 8 znaków</b><small>Najlepiej litery + cyfry. Nie używaj hasła z innego serwisu.</small></div>
        <div data-rule="password2"><span>Powtórz hasło</span><b>Identyczne</b><small>Drugie hasło musi być dokładnie takie samo jak pierwsze.</small></div>
      </div>
      <div class="reg-rules-warning"><b>Nie klikaj „Utwórz konto” wiele razy.</b><span>Jeśli zobaczysz „limit e-maili”, formularz jest poprawny — chwilowo zablokowana jest wysyłka maili potwierdzających.</span></div>
    </section>`;
  }

  function injectRules(){
    const f=form();
    if(!f||!registerMode())return;
    if(!document.querySelector('#reg-rules-v752')){
      f.insertAdjacentHTML('beforebegin',rulesHtml());
    }
    decorateInputs();
    validateAll(false);
  }

  function decorateInputs(){
    const f=form(); if(!f)return;
    const labels=[['username','Np. Abeel87'],['email','np. nazwa@gmail.com'],['password','min. 8 znaków'],['password2','powtórz to samo hasło']];
    labels.forEach(([name,ph])=>{
      const el=f.elements?.[name];
      if(!el||el.dataset.v752)return;
      el.dataset.v752='1';
      el.placeholder=ph;
      el.addEventListener('input',()=>validateAll(false));
      el.addEventListener('blur',()=>validateAll(false));
    });
  }

  function setRule(name,state,text=''){
    const el=document.querySelector(`#reg-rules-v752 [data-rule="${name}"]`);
    if(!el)return;
    el.classList.remove('ok','bad','wait');
    if(state)el.classList.add(state);
    const status=el.querySelector('.reg-rule-status')||document.createElement('em');
    status.className='reg-rule-status';
    status.textContent=state==='ok'?'✓ OK':state==='bad'?(text||'✕ POPRAW'):'';
    if(!status.parentNode)el.appendChild(status);
  }

  function validateAll(show=false){
    const f=form(); if(!f||!registerMode())return false;
    const u=String(f.elements.username?.value||'').trim();
    const e=String(f.elements.email?.value||'').trim();
    const p=String(f.elements.password?.value||'');
    const p2=String(f.elements.password2?.value||'');

    const uok=u.length>=3&&u.length<=24&&USER_RE.test(u);
    const eok=EMAIL_RE.test(e);
    const pok=p.length>=8;
    const p2ok=p2.length>=8&&p===p2;

    setRule('username',u?uok?'ok':'bad':'',u?'✕ 3–24 znaki, bez spacji/@':'');
    setRule('email',e?eok?'ok':'bad':'',e?'✕ Nieprawidłowy e-mail':'');
    setRule('password',p?pok?'ok':'bad':'',p?'✕ Minimum 8 znaków':'');
    setRule('password2',p2?p2ok?'ok':'bad':'',p2?'✕ Hasła są różne':'');

    if(show){
      const problems=[];
      if(!uok)problems.push('Nick: 3–24 znaki; litery/cyfry/_/./-; bez spacji i @.');
      if(!eok)problems.push('E-mail: wpisz pełny adres, np. nazwa@gmail.com.');
      if(!pok)problems.push('Hasło: minimum 8 znaków.');
      if(!p2ok)problems.push('Powtórz hasło: oba hasła muszą być identyczne.');
      if(problems.length)showMessage('Popraw formularz:\n• '+problems.join('\n• '),'error');
    }
    return uok&&eok&&pok&&p2ok;
  }

  function showMessage(text,type='info'){
    const el=msg(); if(!el)return;
    el.innerHTML=`<div class="account-message ${type} reg-msg-v752">${esc(text).replace(/\n/g,'<br>')}</div>`;
  }

  function friendlyError(raw){
    const s=String(raw||'').trim();
    if(/email rate limit exceeded|rate limit.*email|over_email_send_rate_limit/i.test(s)){
      setRateCooldown();
      return 'Limit wysyłki e-maili został chwilowo przekroczony. Twoje dane w formularzu mogą być poprawne. Nie klikaj ponownie wiele razy — spróbuj później. Podczas testów administrator może też wyłączyć obowiązkowe potwierdzanie e-maila w Supabase.';
    }
    if(/user already registered|already registered/i.test(s))return 'Ten e-mail ma już konto. Przejdź do zakładki „Logowanie”.';
    if(/email.*invalid|invalid email/i.test(s))return 'Nieprawidłowy e-mail. Wpisz pełny adres, np. nazwa@gmail.com.';
    if(/password/i.test(s)&&/weak|least|characters|length/i.test(s))return 'Hasło jest za krótkie lub za słabe. Wpisz minimum 8 znaków.';
    if(/username/i.test(s)&&/taken|already|exists/i.test(s))return 'Ten nick jest już zajęty. Wybierz inny.';
    if(/network|fetch/i.test(s))return 'Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.';
    return s||'Nie udało się utworzyć konta.';
  }

  // Runs before v7.4.1 handler because capture listener is added later in document lifetime.
  document.addEventListener('submit',e=>{
    const f=e.target;
    if(!(f instanceof HTMLFormElement)||f.id!=='account-auth-form'||!f.elements?.username)return;
    if(Date.now()<rateUntil()){
      e.preventDefault();e.stopImmediatePropagation();
      showMessage('Wysyłka e-maili potwierdzających jest chwilowo na limicie. Nie klikaj ponownie — spróbuj później.','error');
      return;
    }
    if(!validateAll(true)){
      e.preventDefault();e.stopImmediatePropagation();
    }
  },true);

  // Translate errors produced by the existing registration-fix handler.
  const observer=new MutationObserver(()=>{
    injectRules();
    const box=msg();
    const raw=box?.textContent?.trim()||'';
    if(raw&&(
      /email rate limit exceeded|already registered|invalid email|password|network|fetch/i.test(raw)
    )&&!box.dataset.v752Translated){
      box.dataset.v752Translated='1';
      showMessage(friendlyError(raw),'error');
    }else if(box && !raw){
      delete box.dataset.v752Translated;
    }
  });
  observer.observe(document.body,{subtree:true,childList:true});

  document.addEventListener('click',()=>setTimeout(injectRules,0));
  setTimeout(injectRules,250);
  setTimeout(injectRules,900);
})();