/* Tenis AI v6.4 — Accounts + Community foundation */
(() => {
  const button=document.querySelector('#account-button');
  const overlay=document.querySelector('#account-overlay');
  const closeBtn=document.querySelector('#account-modal-close');
  const content=document.querySelector('#account-modal-content');
  const usersEl=document.querySelector('#community-users-count');
  const onlineEl=document.querySelector('#community-online-count');
  const couponsEl=document.querySelector('#community-coupons-count');
  const chip=document.querySelector('#community-connection-chip');
  if(!button||!overlay||!closeBtn||!content)return;
  const cfg=window.TENIS_AI_SUPABASE||{};
  const configured=Boolean(cfg.url&&cfg.publishableKey&&!String(cfg.url).includes('PASTE_')&&!String(cfg.publishableKey).includes('PASTE_')&&window.supabase?.createClient);
  const REGISTER_RATE_KEY='tenis-ai-register-rate-limit-until';
  const REGISTER_ATTEMPT_COOLDOWN_MS=90*1000;
  const REGISTER_LIMIT_COOLDOWN_MS=10*60*1000;
  let client=null,currentUser=null,currentProfile=null,authMode='login',heartbeat=null,signupBusy=false;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const initials=s=>String(s||'?').trim().split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()||'?';
  const fmtDate=x=>{const d=new Date(x||'');return Number.isFinite(d.getTime())?d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}):'—'};
  const setChip=(text,cls='')=>{chip.textContent=text;chip.className=cls};
  const notify=(name,detail={})=>window.dispatchEvent(new CustomEvent(name,{detail}));

  function registerRateUntil(){
    const t=Number(localStorage.getItem(REGISTER_RATE_KEY)||0);
    return Number.isFinite(t)?t:0;
  }
  function setRegisterRate(ms){
    localStorage.setItem(
      REGISTER_RATE_KEY,
      String(Date.now()+Math.max(0,Number(ms)||0))
    );
  }
  function clearRegisterRate(){
    localStorage.removeItem(REGISTER_RATE_KEY);
  }
  function registerWaitText(){
    const sec=Math.max(
      1,
      Math.ceil((registerRateUntil()-Date.now())/1000)
    );
    return `Odczekaj ${sec} s przed kolejną próbą rejestracji.`;
  }
  function isEmailRateLimitError(err){
    const text=[
      err?.message,
      err?.code,
      err?.status,
      err?.name
    ].filter(Boolean).join(' ').toLowerCase();

    return text.includes('rate limit')
      || text.includes('over_email_send_rate_limit')
      || text.includes('429');
  }
  if(configured){client=window.supabase.createClient(cfg.url,cfg.publishableKey,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});setChip('POŁĄCZONO','online')}else setChip('WYMAGA KONFIGURACJI','setup');
  window.tenisAIAccount={get client(){return client},get user(){return currentUser},get profile(){return currentProfile},refreshStats:refreshCommunityStats};
  function openModal(){overlay.hidden=false;document.body.style.overflow='hidden';renderModal()}
  function closeModal(){overlay.hidden=true;document.body.style.overflow=''}
  button.onclick=openModal;closeBtn.onclick=closeModal;overlay.addEventListener('click',e=>{if(e.target===overlay)closeModal()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!overlay.hidden)closeModal()});
  function updateAccountButton(){if(currentUser&&currentProfile){button.classList.add('logged-in');button.querySelector('.account-button-avatar').textContent=initials(currentProfile.username);button.querySelector('.account-button-copy b').textContent=currentProfile.username;button.querySelector('.account-button-copy small').textContent='Online'}else{button.classList.remove('logged-in');button.querySelector('.account-button-avatar').textContent='👤';button.querySelector('.account-button-copy b').textContent=configured?'Konto':'Konta';button.querySelector('.account-button-copy small').textContent=configured?'Zaloguj':'Konfiguracja'}}
  function setupHtml(){return `<div class="account-head"><h2 id="account-modal-title">👤 Konta Tenis AI</h2><p>Frontend v6.4 jest gotowy. Zostało podłączenie projektu Supabase.</p></div><div class="account-setup"><b>Jeszcze nie połączono bazy.</b><br><br>Po utworzeniu projektu w Supabase wklejamy <code>Project URL</code> oraz <code>Publishable key</code> do <code>frontend/supabase-config.js</code>, a potem uruchamiamy przygotowany plik <code>supabase/schema.sql</code>.<br><br><b>Nigdy nie wklejamy klucza service_role do aplikacji.</b></div>`}
  function authHtml(){const login=authMode==='login';return `<div class="account-head"><h2 id="account-modal-title">${login?'🔐 Zaloguj się':'✨ Załóż konto'}</h2><p>${login?'Wejdź na swój profil Tenis AI.':'Nick będzie widoczny przy kuponach, rankingach i komentarzach.'}</p></div><div class="account-auth-tabs"><button type="button" data-auth-mode="login" class="${login?'active':''}">Logowanie</button><button type="button" data-auth-mode="register" class="${!login?'active':''}">Rejestracja</button></div><form id="account-auth-form" class="account-form">${login?'':`<label>Nick<input name="username" minlength="3" maxlength="24" autocomplete="nickname" required placeholder="Np. TenisFan87"></label>`}<label>E-mail<input name="email" type="email" autocomplete="email" required placeholder="twoj@email.pl"></label><label>Hasło<input name="password" type="password" minlength="8" autocomplete="${login?'current-password':'new-password'}" required placeholder="Minimum 8 znaków"></label>${login?'':`<label>Powtórz hasło<input name="password2" type="password" minlength="8" autocomplete="new-password" required></label>`}<button class="account-primary" type="submit">${login?'Zaloguj':'Utwórz konto'}</button></form><div id="account-form-message"></div>`}
  function profileHtml(){return `<div class="account-head"><h2 id="account-modal-title">👤 Twój profil</h2><p>Konto jest połączone ze wspólną bazą Tenis AI.</p></div><div class="account-profile-card"><div class="account-profile-main"><div class="account-profile-avatar">${esc(initials(currentProfile?.username))}</div><div><h3>${esc(currentProfile?.username||'Użytkownik')}</h3><p>${esc(currentUser?.email||'')}</p></div></div><div class="account-profile-meta"><div><span>Dołączył</span><b>${esc(fmtDate(currentProfile?.created_at||currentUser?.created_at))}</b></div><div><span>Status</span><b style="color:var(--neon-lime)">● Online</b></div></div><div class="account-coming">Następny etap: publiczny profil, kupony z linków Superbet / Betclic / STS / Fortuna, obserwowanie użytkowników i ranking zweryfikowanych wyników.</div><button id="account-signout" class="account-secondary" type="button">Wyloguj się</button></div>`}
  function renderModal(){if(!configured){content.innerHTML=setupHtml();return}if(currentUser&&currentProfile){content.innerHTML=profileHtml();document.querySelector('#account-signout').onclick=signOut;return}content.innerHTML=authHtml();content.querySelectorAll('[data-auth-mode]').forEach(b=>b.onclick=()=>{authMode=b.dataset.authMode;renderModal()});document.querySelector('#account-auth-form').onsubmit=submitAuth}
  function showMessage(text,type='info'){const el=document.querySelector('#account-form-message');if(el)el.innerHTML=`<div class="account-message ${type}">${esc(text)}</div>`}
  async function usernameTaken(username){const {count,error}=await client.from('profiles').select('id',{count:'exact',head:true}).ilike('username',username);if(error)throw error;return Number(count||0)>0}
  async function submitAuth(e){
    e.preventDefault();

    const form=e.currentTarget;
    const fd=new FormData(form);
    const email=String(fd.get('email')||'').trim();
    const password=String(fd.get('password')||'');
    const submit=form.querySelector('button[type="submit"]');
    const registering=authMode==='register';

    if(registering){
      if(signupBusy){
        showMessage(
          'Rejestracja jest już wysyłana. Poczekaj na odpowiedź.',
          'info'
        );
        return;
      }

      if(Date.now()<registerRateUntil()){
        showMessage(registerWaitText(),'error');
        return;
      }

      signupBusy=true;
    }

    submit.disabled=true;
    submit.textContent='Chwila…';

    try{
      if(registering){
        const username=String(fd.get('username')||'').trim();
        const password2=String(fd.get('password2')||'');

        if(username.length<3||username.length>24)
          throw new Error('Nick musi mieć od 3 do 24 znaków.');

        if(password!==password2)
          throw new Error('Hasła nie są takie same.');

        if(await usernameTaken(username))
          throw new Error('Ten nick jest już zajęty.');

        setRegisterRate(REGISTER_ATTEMPT_COOLDOWN_MS);

        const {data,error}=await client.auth.signUp({
          email,
          password,
          options:{
            data:{username},
            emailRedirectTo:cfg.siteUrl||location.origin+location.pathname
          }
        });

        if(error)throw error;

        setRegisterRate(REGISTER_ATTEMPT_COOLDOWN_MS);

        showMessage(
          data.session
            ? 'Konto utworzone. Jesteś zalogowany ✅'
            : 'Konto utworzone. Sprawdź e-mail i potwierdź rejestrację ✅',
          'ok'
        );
      }else{
        const {error}=await client.auth.signInWithPassword({
          email,
          password
        });

        if(error)throw error;
        closeModal();
      }
    }catch(err){
      if(registering && isEmailRateLimitError(err)){
        setRegisterRate(REGISTER_LIMIT_COOLDOWN_MS);

        showMessage(
          'Wysłano zbyt wiele maili potwierdzających. Rejestracja jest chwilowo zablokowana — spróbuj ponownie za kilka minut.',
          'error'
        );
      }else{
        if(registering)clearRegisterRate();

        showMessage(
          err?.message||'Nie udało się wykonać operacji.',
          'error'
        );
      }
    }finally{
      if(registering)signupBusy=false;

      submit.disabled=false;
      submit.textContent=
        authMode==='register'?'Utwórz konto':'Zaloguj';
    }
  }

  async function signOut(){try{await client.auth.signOut()}finally{closeModal()}}
  async function loadProfile(user){if(!user){currentProfile=null;return}const {data,error}=await client.from('profiles').select('id,username,avatar_url,bio,last_seen_at,created_at').eq('id',user.id).maybeSingle();if(error){console.warn('Tenis AI profile:',error.message);currentProfile=null;return}currentProfile=data||null}
  async function touchPresence(){if(!client||!currentUser)return;try{await client.from('profiles').update({last_seen_at:new Date().toISOString()}).eq('id',currentUser.id)}catch{}}
  function startHeartbeat(){clearInterval(heartbeat);if(!currentUser)return;touchPresence();heartbeat=setInterval(()=>{touchPresence();refreshCommunityStats()},60000)}
  async function refreshCommunityStats(){
    if(!configured||!client){
      usersEl.textContent='—';onlineEl.textContent='—';couponsEl.textContent='—';
      return;
    }
    try{
      const {data,error}=await client.rpc('community_public_stats');
      if(error)throw error;
      const d=data||{};
      usersEl.textContent=d.registered??'—';
      onlineEl.textContent=d.online??'—';
      couponsEl.textContent=d.coupons_today??'—';
      setChip('LIVE','online');
    }catch(err){
      console.warn('Community stats:',err?.message||err);
      setChip('BŁĄD POŁĄCZENIA','setup');
    }
  }
  async function applySession(session){currentUser=session?.user||null;await loadProfile(currentUser);updateAccountButton();startHeartbeat();await refreshCommunityStats();notify('tenis-ai-auth-change',{user:currentUser,profile:currentProfile});if(!overlay.hidden)renderModal()}
  async function init(){updateAccountButton();if(!configured){refreshCommunityStats();return}const {data}=await client.auth.getSession();await applySession(data.session);client.auth.onAuthStateChange((_event,session)=>setTimeout(()=>applySession(session),0));setInterval(()=>{if(!currentUser)refreshCommunityStats()},60000)}
  init();
})();
