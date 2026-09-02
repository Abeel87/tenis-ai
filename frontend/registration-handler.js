/* Tenis AI v7.8E3 — hardened registration capture handler */
(() => {
  const USER_RE=/^[\p{L}\p{N}_.-]+$/u;
  const EMAIL_RE=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const RATE_KEY='tenis-ai-register-rate-limit-until';
  const ATTEMPT_COOLDOWN_MS=90*1000;
  const LIMIT_COOLDOWN_MS=10*60*1000;
  let busy=false;

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));

  const show=(text,type='info')=>{
    const el=document.querySelector('#account-form-message');
    if(el)el.innerHTML=`<div class="account-message ${type}">${esc(text)}</div>`;
  };

  const rateUntil=()=>{
    const t=Number(localStorage.getItem(RATE_KEY)||0);
    return Number.isFinite(t)?t:0;
  };
  const setRate=ms=>localStorage.setItem(RATE_KEY,String(Date.now()+Math.max(0,Number(ms)||0)));
  const clearRate=()=>localStorage.removeItem(RATE_KEY);

  const isRateError=err=>{
    const text=[err?.message,err?.code,err?.status,err?.name].filter(Boolean).join(' ').toLowerCase();
    return text.includes('rate limit')||text.includes('over_email_send_rate_limit')||text.includes('429');
  };

  document.addEventListener('submit',async e=>{
    const form=e.target;
    if(!(form instanceof HTMLFormElement)||form.id!=='account-auth-form'||!form.elements?.username)return;

    e.preventDefault();
    e.stopImmediatePropagation();

    if(busy){
      show('Rejestracja jest już wysyłana. Poczekaj na odpowiedź.','info');
      return;
    }

    if(Date.now()<rateUntil()){
      const sec=Math.max(1,Math.ceil((rateUntil()-Date.now())/1000));
      show(`Odczekaj ${sec} s przed kolejną próbą rejestracji.`,'error');
      return;
    }

    const client=window.tenisAIAccount?.client;
    const btn=form.querySelector('button[type="submit"]');
    if(!client){show('Brak połączenia z bazą.','error');return;}

    const fd=new FormData(form);
    const username=String(fd.get('username')||'').trim();
    const email=String(fd.get('email')||'').trim();
    const password=String(fd.get('password')||'');
    const password2=String(fd.get('password2')||'');

    if(username.length<3||username.length>24||!USER_RE.test(username)){
      show('Nick: 3–24 znaki, tylko litery, cyfry, _ . - i bez spacji/@.','error');return;
    }
    if(!EMAIL_RE.test(email)){show('Nieprawidłowy adres e-mail.','error');return;}
    if(password.length<8){show('Hasło musi mieć minimum 8 znaków.','error');return;}
    if(password!==password2){show('Hasła nie są takie same.','error');return;}

    busy=true;
    if(btn){btn.disabled=true;btn.textContent='Chwila…';}

    try{
      const {data:available,error:checkError}=await client.rpc('username_available',{wanted_username:username});
      if(checkError)throw new Error('Nie udało się sprawdzić nicku.');
      if(!available)throw new Error('Ten nick jest już zajęty.');

      setRate(ATTEMPT_COOLDOWN_MS);

      const cfg=window.TENIS_AI_SUPABASE||{};
      const {data,error}=await client.auth.signUp({
        email,password,
        options:{
          data:{username},
          emailRedirectTo:cfg.siteUrl||location.origin+location.pathname
        }
      });
      if(error)throw error;

      setRate(ATTEMPT_COOLDOWN_MS);
      show(data?.session
        ? 'Konto utworzone. Jesteś zalogowany ✅'
        : 'Konto utworzone. Sprawdź e-mail i potwierdź rejestrację ✅','ok');
    }catch(err){
      if(isRateError(err)){
        setRate(LIMIT_COOLDOWN_MS);
        show('Wysłano zbyt wiele maili potwierdzających. Rejestracja jest chwilowo zablokowana — spróbuj ponownie za kilka minut.','error');
      }else{
        clearRate();
        let text=String(err?.message||'Nie udało się wykonać operacji.');
        if(/already registered|user already registered/i.test(text))text='Ten e-mail jest już zarejestrowany.';
        if(/invalid email/i.test(text))text='Nieprawidłowy adres e-mail.';
        show(text,'error');
      }
    }finally{
      busy=false;
      if(btn){btn.disabled=false;btn.textContent='Utwórz konto';}
    }
  },true);
})();
