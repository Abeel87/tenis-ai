/* Tenis AI v7.8E3 — mobile auth + Cloudflare Turnstile */
(() => {
  const USER_RE=/^[\p{L}\p{N}_.-]+$/u;
  const EMAIL_RE=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const RATE_KEY='tenis-ai-register-rate-limit-until';
  const TURNSTILE_SITE_KEY='0x4AAAAAAEX7JDePX3k2rQXE';

  let loadPromise=null, widgetId=null, widgetHost=null, captchaToken='';

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

  function ensureStyle(){
    if(document.querySelector('#tenis-ai-turnstile-style'))return;
    const style=document.createElement('style');
    style.id='tenis-ai-turnstile-style';
    style.textContent=`
      .turnstile-shell-v78e3{margin:12px 0 14px;max-width:100%;overflow:hidden}
      .turnstile-shell-v78e3-label{display:flex;align-items:center;gap:7px;margin:0 0 7px;font-size:.82rem;opacity:.82}
      .turnstile-host-v78e3{width:100%;min-height:65px}
      .turnstile-shell-v78e3[data-verified="1"] .turnstile-shell-v78e3-label{color:var(--neon-lime,#b7ff00);opacity:1}
    `;
    document.head.appendChild(style);
  }

  function loadTurnstile(){
    if(window.turnstile)return Promise.resolve(window.turnstile);
    if(loadPromise)return loadPromise;
    loadPromise=new Promise((resolve,reject)=>{
      const done=()=>window.turnstile
        ? resolve(window.turnstile)
        : reject(new Error('Turnstile nie uruchomił się poprawnie.'));
      let script=document.querySelector('script[data-tenis-turnstile]');
      if(script){
        script.addEventListener('load',done,{once:true});
        script.addEventListener('error',()=>reject(new Error('Nie udało się załadować ochrony antyspamowej.')),{once:true});
        return;
      }
      script=document.createElement('script');
      script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async=true;
      script.defer=true;
      script.dataset.tenisTurnstile='1';
      script.addEventListener('load',done,{once:true});
      script.addEventListener('error',()=>reject(new Error('Nie udało się załadować ochrony antyspamowej.')),{once:true});
      document.head.appendChild(script);
    });
    return loadPromise;
  }

  function resetCaptcha(){
    captchaToken='';
    if(widgetHost?.parentElement)widgetHost.parentElement.dataset.verified='0';
    try{
      if(window.turnstile && widgetId!==null)window.turnstile.reset(widgetId);
    }catch{}
  }

  function dropOldWidget(nextHost){
    if(!widgetHost || widgetHost===nextHost)return;
    try{
      if(window.turnstile && widgetId!==null)window.turnstile.remove(widgetId);
    }catch{}
    widgetId=null;
    widgetHost=null;
    captchaToken='';
  }

  async function ensureCaptcha(){
    const f=form();
    if(!f)return;

    ensureStyle();

    let shell=f.querySelector('.turnstile-shell-v78e3');
    if(!shell){
      shell=document.createElement('div');
      shell.className='turnstile-shell-v78e3';
      shell.dataset.verified='0';
      shell.innerHTML=`
        <div class="turnstile-shell-v78e3-label">🛡️ <span>Ochrona antyspamowa</span></div>
        <div class="turnstile-host-v78e3"></div>`;
      const submit=f.querySelector('button[type="submit"]');
      submit ? f.insertBefore(shell,submit) : f.appendChild(shell);
    }

    const host=shell.querySelector('.turnstile-host-v78e3');
    if(!host)return;

    dropOldWidget(host);
    if(widgetHost===host && widgetId!==null)return;

    widgetHost=host;
    captchaToken='';

    try{
      const ts=await loadTurnstile();
      if(!host.isConnected || form()!==f)return;
      widgetId=ts.render(host,{
        sitekey:TURNSTILE_SITE_KEY,
        theme:'dark',
        size:'flexible',
        language:'pl',
        appearance:'always',
        action:registerMode()?'signup':'signin',
        callback:token=>{
          captchaToken=String(token||'');
          shell.dataset.verified=captchaToken?'1':'0';
        },
        'expired-callback':()=>{
          captchaToken='';
          shell.dataset.verified='0';
        },
        'timeout-callback':()=>{
          captchaToken='';
          shell.dataset.verified='0';
          showMessage('Weryfikacja antyspamowa wygasła. Spróbuj ponownie.','error');
        },
        'error-callback':()=>{
          captchaToken='';
          shell.dataset.verified='0';
          showMessage('Nie udało się wykonać weryfikacji antyspamowej. Odśwież stronę i spróbuj ponownie.','error');
        }
      });
    }catch(err){
      showMessage(err?.message||'Nie udało się uruchomić ochrony antyspamowej.','error');
    }
  }

  function requireCaptcha(){
    const token=String(captchaToken||'');
    if(!token)throw new Error('Poczekaj na potwierdzenie ochrony antyspamowej i spróbuj ponownie.');
    return token;
  }

  function patchAuth(){
    const auth=window.tenisAIAccount?.client?.auth;
    if(!auth || auth.__tenisTurnstilePatched)return;

    const originalSignUp=auth.signUp.bind(auth);
    const originalSignIn=auth.signInWithPassword.bind(auth);

    auth.signUp=async credentials=>{
      const token=requireCaptcha();
      try{
        return await originalSignUp({
          ...(credentials||{}),
          options:{...(credentials?.options||{}),captchaToken:token}
        });
      }finally{
        resetCaptcha();
      }
    };

    auth.signInWithPassword=async credentials=>{
      const token=requireCaptcha();
      try{
        return await originalSignIn({
          ...(credentials||{}),
          options:{...(credentials?.options||{}),captchaToken:token}
        });
      }finally{
        resetCaptcha();
      }
    };

    auth.__tenisTurnstilePatched=true;
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
    const oks=['username','email','password','password2'].map(paint);
    if(show && oks.some(x=>!x))showMessage('Popraw pola oznaczone na czerwono.','error');
    return oks.every(Boolean);
  }

  function decorate(){
    const f=form();
    if(!f||!registerMode())return;
    [
      ['username','Np. TenisFan87'],
      ['email','np. nazwa@gmail.com'],
      ['password','min. 8 znaków'],
      ['password2','powtórz to samo hasło']
    ].forEach(([name,ph])=>{
      const el=f.elements?.[name];
      if(!el)return;
      el.placeholder=ph;
      el.setAttribute('enterkeyhint',name==='password2'?'done':'next');
      if(el.dataset.v78c5)return;
      el.dataset.v78c5='1';
      el.addEventListener('blur',()=>paint(name));
      el.addEventListener('change',()=>paint(name));
      ensureInline(name);
    });
  }

  function init(){
    patchAuth();
    const f=form();
    if(!f)return;
    ensureCaptcha();
    if(registerMode())decorate();
  }

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

  document.addEventListener('click',()=>setTimeout(init,0));
  init();
  setTimeout(init,200);
  setTimeout(init,700);
})();
