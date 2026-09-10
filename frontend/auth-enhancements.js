/* Tenis AI — restores CAPTCHA-protected auth and registration after UI rewrite. */
(()=>{
'use strict';
if(typeof document==='undefined'||typeof document.createElement!=='function')return;
const SITE_KEY='0x4AAAAAAEX7JDePX3k2rQXE';
const USER_RE=/^[\p{L}\p{N}_.-]+$/u;
const $=s=>document.querySelector(s);
let mode='login', recovery=false, busy=false, captchaToken='', widgetId=null, loadPromise=null, captchaGeneration=0;

function form(){return $('#login-form')}
function account(){return window.TenisAccount}
function message(text,type='info'){
  const el=$('#auth-message');
  if(!el)return;
  el.textContent=String(text||'');
  el.dataset.type=type;
}
function loadTurnstile(){
  if(window.turnstile)return Promise.resolve(window.turnstile);
  if(loadPromise)return loadPromise;
  loadPromise=new Promise((resolve,reject)=>{
    const done=()=>window.turnstile?resolve(window.turnstile):reject(new Error('Ochrona antyspamowa nie uruchomiła się poprawnie.'));
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
  const shell=$('#auth-captcha-shell');
  if(shell)shell.dataset.verified='0';
  try{if(window.turnstile&&widgetId!==null)window.turnstile.reset(widgetId)}catch{}
}
function removeCaptcha(){
  captchaToken='';
  try{if(window.turnstile&&widgetId!==null)window.turnstile.remove(widgetId)}catch{}
  widgetId=null;
  const host=$('#auth-captcha');
  if(host)host.innerHTML='';
}
async function renderCaptcha(){
  const generation=++captchaGeneration;
  const shell=$('#auth-captcha-shell'),host=$('#auth-captcha');
  if(!shell||!host)return;
  if(recovery){shell.hidden=true;removeCaptcha();return;}
  shell.hidden=false;
  shell.dataset.verified='0';
  removeCaptcha();
  try{
    const ts=await loadTurnstile();
    if(generation!==captchaGeneration||!host.isConnected||recovery)return;
    widgetId=ts.render(host,{
      sitekey:SITE_KEY,
      theme:'dark',
      size:'flexible',
      language:'pl',
      appearance:'always',
      action:mode==='register'?'signup':'signin',
      callback:token=>{captchaToken=String(token||'');shell.dataset.verified=captchaToken?'1':'0'},
      'expired-callback':()=>{captchaToken='';shell.dataset.verified='0'},
      'timeout-callback':()=>{captchaToken='';shell.dataset.verified='0';message('Weryfikacja antyspamowa wygasła. Spróbuj ponownie.','error')},
      'error-callback':()=>{captchaToken='';shell.dataset.verified='0';message('Nie udało się wykonać weryfikacji antyspamowej. Odśwież stronę i spróbuj ponownie.','error')}
    });
  }catch(e){message(e?.message||'Nie udało się uruchomić ochrony antyspamowej.','error')}
}
function requireCaptcha(){
  const token=String(captchaToken||'');
  if(!token)throw new Error('Poczekaj na potwierdzenie ochrony antyspamowej i spróbuj ponownie.');
  return token;
}
function patchAuth(){
  const auth=account()?.client?.auth;
  if(!auth||auth.__tenisCaptchaPatched)return false;
  const signIn=auth.signInWithPassword.bind(auth);
  const signUp=auth.signUp.bind(auth);
  const reset=auth.resetPasswordForEmail.bind(auth);
  auth.signInWithPassword=async credentials=>{
    const token=requireCaptcha();
    try{return await signIn({...credentials,options:{...(credentials?.options||{}),captchaToken:token}})}
    finally{resetCaptcha()}
  };
  auth.signUp=async credentials=>{
    const token=requireCaptcha();
    try{return await signUp({...credentials,options:{...(credentials?.options||{}),captchaToken:token}})}
    finally{resetCaptcha()}
  };
  auth.resetPasswordForEmail=async(email,options={})=>{
    const token=requireCaptcha();
    try{return await reset(email,{...options,captchaToken:token})}
    finally{resetCaptcha()}
  };
  auth.__tenisCaptchaPatched=true;
  return true;
}
function setMode(next){
  if(recovery)return;
  mode=next==='register'?'register':'login';
  const f=form();if(!f)return;
  f.dataset.authMode=mode;
  const registering=mode==='register';
  const username=f.elements.username,password2=f.elements.password2,password=f.elements.password;
  const usernameLabel=username?.closest('label'),password2Label=password2?.closest('label');
  if(usernameLabel)usernameLabel.hidden=!registering;
  if(password2Label)password2Label.hidden=!registering;
  if(username)username.required=registering;
  if(password2)password2.required=registering;
  if(password){password.minLength=8;password.autocomplete=registering?'new-password':'current-password'}
  $('#reset-password').hidden=registering;
  const submit=f.querySelector('button[type="submit"]');
  if(submit)submit.innerHTML=registering?'Utwórz konto <span aria-hidden="true">→</span>':'Zaloguj się <span aria-hidden="true">→</span>';
  document.querySelectorAll('[data-auth-tab]').forEach(b=>{
    const active=b.dataset.authTab===mode;
    b.classList.toggle('active',active);
    b.setAttribute('aria-selected',String(active));
  });
  message(registering?'Utwórz konto, aby wejść do Tenis AI.':'Zaloguj się, aby wejść do aplikacji.');
  renderCaptcha();
}
function installUi(){
  const f=form();
  if(!f||f.dataset.authEnhanced)return;
  f.dataset.authEnhanced='1';
  const email=f.elements.email,password=f.elements.password,submit=f.querySelector('button[type="submit"]');
  if(!email||!password||!submit)return;

  const tabs=document.createElement('div');
  tabs.className='auth-tabs';
  tabs.setAttribute('role','tablist');
  tabs.innerHTML='<button type="button" data-auth-tab="login" class="active" role="tab" aria-selected="true">Logowanie</button><button type="button" data-auth-tab="register" role="tab" aria-selected="false">Rejestracja</button>';
  f.before(tabs);

  const usernameLabel=document.createElement('label');
  usernameLabel.hidden=true;
  usernameLabel.innerHTML='Nick<input name="username" type="text" minlength="3" maxlength="24" autocomplete="username" placeholder="Np. TenisFan87">';
  email.closest('label').before(usernameLabel);

  const password2Label=document.createElement('label');
  password2Label.hidden=true;
  password2Label.innerHTML='Powtórz hasło<input name="password2" type="password" minlength="8" autocomplete="new-password" placeholder="Powtórz hasło">';
  password.closest('label').after(password2Label);
  password.minLength=8;

  const captcha=document.createElement('div');
  captcha.id='auth-captcha-shell';
  captcha.className='auth-captcha-shell';
  captcha.dataset.verified='0';
  captcha.innerHTML='<div class="auth-captcha-label">🛡️ Ochrona antyspamowa</div><div id="auth-captcha"></div>';
  submit.before(captcha);

  tabs.addEventListener('click',e=>{
    const b=e.target.closest('[data-auth-tab]');
    if(b)setMode(b.dataset.authTab);
  });
  setMode('login');
}
async function register(f){
  if(busy)return;
  const A=account();
  if(!A?.client){message('Brak połączenia z Supabase.','error');return;}
  const fd=new FormData(f),username=String(fd.get('username')||'').trim(),email=String(fd.get('email')||'').trim(),password=String(fd.get('password')||''),password2=String(fd.get('password2')||'');
  if(username.length<3||username.length>24||!USER_RE.test(username)){message('Nick: 3–24 znaki, tylko litery, cyfry, _ . - i bez spacji/@.','error');return;}
  if(password.length<8){message('Hasło musi mieć minimum 8 znaków.','error');return;}
  if(password!==password2){message('Hasła nie są takie same.','error');return;}
  try{requireCaptcha()}catch(e){message(e.message,'error');return;}
  const button=f.querySelector('button[type="submit"]');
  busy=true;if(button)button.disabled=true;message('Tworzę konto…');
  try{
    const available=await A.client.rpc('username_available',{wanted_username:username});
    if(available.error)throw new Error('Nie udało się sprawdzić nicku.');
    if(available.data!==true)throw new Error('Ten nick jest już zajęty.');
    const cfg=window.TENIS_AI_SUPABASE||{};
    const {data,error}=await A.client.auth.signUp({email,password,options:{data:{username},emailRedirectTo:cfg.siteUrl||location.origin+location.pathname}});
    if(error)throw error;
    f.elements.password.value='';f.elements.password2.value='';
    message(data?.session?'Konto utworzone. Jesteś zalogowany ✅':'Konto utworzone. Sprawdź e-mail i potwierdź rejestrację ✅','ok');
  }catch(e){
    let text=String(e?.message||'Nie udało się utworzyć konta.');
    if(/already registered|user already registered/i.test(text))text='Ten e-mail jest już zarejestrowany.';
    if(/captcha/i.test(text)&&/token|protection|disallowed/i.test(text))text='Weryfikacja antyspamowa nie została potwierdzona. Spróbuj ponownie.';
    message(text,'error');
  }finally{busy=false;if(button)button.disabled=false}
}

function setRecovery(active){
  recovery=Boolean(active);
  const f=form(),tabs=$('.auth-tabs'),shell=$('#auth-captcha-shell');
  if(tabs)tabs.hidden=recovery;
  if(!f)return;
  const username=f.elements.username,password2=f.elements.password2;
  if(recovery){
    if(username){username.required=false;const l=username.closest('label');if(l)l.hidden=true}
    if(password2){password2.required=false;const l=password2.closest('label');if(l)l.hidden=true}
    if(shell)shell.hidden=true;
    ++captchaGeneration;removeCaptcha();
  }
}

document.addEventListener('submit',e=>{
  const f=e.target;
  if(!(f instanceof HTMLFormElement)||f.id!=='login-form'||mode!=='register'||recovery)return;
  e.preventDefault();e.stopImmediatePropagation();
  register(f);
},true);

function init(){installUi();patchAuth()}
init();
setTimeout(init,100);
setTimeout(init,500);
window.addEventListener('tenis-auth',e=>{
  setRecovery(Boolean(e.detail?.recovery));
  if(!recovery&&e.detail?.user==null)setMode('login');
});
try{
  account()?.client?.auth?.onAuthStateChange(event=>{
    if(event==='PASSWORD_RECOVERY'){
      setRecovery(true);
    }
    if(event==='SIGNED_OUT'){
      setRecovery(false);
      setTimeout(()=>setMode('login'),0);
    }
  });
}catch{}
})();
