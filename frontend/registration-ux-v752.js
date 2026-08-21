/* Tenis AI v7.8C5 — clean mobile registration UX
   Native Android inputs + inline validation. No MutationObserver, no forced focus.
*/
(() => {
  const USER_RE=/^[\p{L}\p{N}_.-]+$/u;
  const EMAIL_RE=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const RATE_KEY='tenis-ai-register-rate-limit-until';

  const form=()=>document.querySelector('#account-auth-form');
  const msg=()=>document.querySelector('#account-form-message');
  const registerMode=()=>Boolean(form()?.elements?.username);

  const META={
    username:{title:'Nick',hint:'3–24 znaki · litery, cyfry, _ . - · bez spacji i @'},
    email:{title:'E-mail',hint:'Prawidłowy adres e-mail · bez spacji'},
    password:{title:'Hasło',hint:'Minimum 8 znaków'},
    password2:{title:'Powtórz hasło',hint:'Musi być identyczne jak pierwsze hasło'}
  };

  function rateUntil(){
    const t=Number(localStorage.getItem(RATE_KEY)||0);
    return Number.isFinite(t)?t:0;
  }

  function esc(s){
    return String(s??'').replace(/[&<>"']/g,c=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  function showMessage(text,type='info'){
    const el=msg(); if(!el)return;
    el.innerHTML=`<div class="account-message ${type} reg-msg-v752">${esc(text).replace(/\n/g,'<br>')}</div>`;
  }

  function ensureInline(name){
    const f=form(), input=f?.elements?.[name];
    if(!input)return null;

    input.id=input.id||`reg-${name}-v78c5`;

    let box=input.parentElement?.querySelector(`.reg-inline-v78c5[data-for="${name}"]`);
    if(!box){
      box=document.createElement('div');
      box.className='reg-inline-v78c5';
      box.dataset.for=name;
      box.innerHTML=`
        <div class="reg-inline-v78c5-copy">
          <b>${META[name].title}</b>
          <span>${META[name].hint}</span>
        </div>
        <em class="reg-inline-v78c5-status"></em>`;
      input.insertAdjacentElement('afterend',box);
    }
    return box;
  }

  function result(name){
    const f=form();
    if(!f)return {ok:false,empty:true,text:''};

    const u=String(f.elements.username?.value||'').trim();
    const e=String(f.elements.email?.value||'').trim();
    const p=String(f.elements.password?.value||'');
    const p2=String(f.elements.password2?.value||'');

    if(name==='username'){
      if(!u)return {ok:false,empty:true,text:''};
      return {ok:u.length>=3&&u.length<=24&&USER_RE.test(u),empty:false,text:'3–24 znaki, bez spacji/@'};
    }
    if(name==='email'){
      if(!e)return {ok:false,empty:true,text:''};
      return {ok:EMAIL_RE.test(e),empty:false,text:'Nieprawidłowy e-mail'};
    }
    if(name==='password'){
      if(!p)return {ok:false,empty:true,text:''};
      return {ok:p.length>=8,empty:false,text:'Minimum 8 znaków'};
    }
    if(name==='password2'){
      if(!p2)return {ok:false,empty:true,text:''};
      return {ok:p2.length>=8&&p===p2,empty:false,text:'Hasła są różne'};
    }
    return {ok:false,empty:true,text:''};
  }

  function paint(name){
    const box=ensureInline(name);
    if(!box)return true;
    const r=result(name);
    box.classList.remove('ok','bad');
    const status=box.querySelector('.reg-inline-v78c5-status');
    if(r.empty){
      if(status)status.textContent='';
      return false;
    }
    box.classList.add(r.ok?'ok':'bad');
    if(status)status.textContent=r.ok?'✓ OK':`✕ ${r.text}`;
    return r.ok;
  }

  function validateAll(show=false){
    if(!registerMode())return true;
    const names=['username','email','password','password2'];
    const oks=names.map(paint);
    if(show && oks.some(x=>!x)){
      showMessage('Popraw pola oznaczone na czerwono.','error');
    }
    return oks.every(Boolean);
  }

  function decorate(){
    const f=form();
    if(!f||!registerMode())return;

    const cfg=[
      ['username','Np. TenisFan87'],
      ['email','np. nazwa@gmail.com'],
      ['password','min. 8 znaków'],
      ['password2','powtórz to samo hasło']
    ];

    cfg.forEach(([name,ph])=>{
      const el=f.elements?.[name];
      if(!el)return;
      el.placeholder=ph;
      el.setAttribute('enterkeyhint',name==='password2'?'done':'next');

      if(el.dataset.v78c5)return;
      el.dataset.v78c5='1';

      // Celowo tylko blur/change. Zero walidacji podczas kompozycji Gboard.
      el.addEventListener('blur',()=>paint(name));
      el.addEventListener('change',()=>paint(name));

      ensureInline(name);
    });
  }

  function init(){
    if(!registerMode())return;
    decorate();
  }

  // Walidacja PRZED istniejącym handlerem rejestracji.
  document.addEventListener('submit',e=>{
    const f=e.target;
    if(!(f instanceof HTMLFormElement)||f.id!=='account-auth-form'||!f.elements?.username)return;

    if(Date.now()<rateUntil()){
      e.preventDefault();
      e.stopImmediatePropagation();
      showMessage('Wysyłka e-maili potwierdzających jest chwilowo na limicie. Spróbuj później.','error');
      return;
    }

    if(!validateAll(true)){
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  },true);

  // Modal jest renderowany dynamicznie, więc inicjalizujemy po kliknięciach zakładek/konta.
  document.addEventListener('click',()=>setTimeout(init,0));
  setTimeout(init,200);
  setTimeout(init,700);
})();
