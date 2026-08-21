/* Tenis AI v7.4.1 — registration fix */
(() => {
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const show=(text,type='info')=>{
    const el=document.querySelector('#account-form-message');
    if(el) el.innerHTML=`<div class="account-message ${type}">${esc(text)}</div>`;
  };

  document.addEventListener('submit', async e => {
    const form=e.target;
    if(!(form instanceof HTMLFormElement) || form.id!=='account-auth-form' || !form.elements?.username) return;
    e.preventDefault();
    e.stopImmediatePropagation();

    const client=window.tenisAIAccount?.client;
    const btn=form.querySelector('button[type="submit"]');
    if(!client){ show('Brak połączenia z bazą.','error'); return; }

    const fd=new FormData(form);
    const username=String(fd.get('username')||'').trim();
    const email=String(fd.get('email')||'').trim();
    const password=String(fd.get('password')||'');
    const password2=String(fd.get('password2')||'');

    if(btn){btn.disabled=true;btn.textContent='Chwila…';}
    try{
      if(username.length<3 || username.length>24) throw new Error('Nick musi mieć od 3 do 24 znaków.');
      if(password.length<8) throw new Error('Hasło musi mieć minimum 8 znaków.');
      if(password!==password2) throw new Error('Hasła nie są takie same.');

      const {data:available,error:checkError}=await client.rpc('username_available',{wanted_username:username});
      if(checkError) throw new Error('Nie udało się sprawdzić nicku. Uruchom poprawkę SQL v7.4.1.');
      if(!available) throw new Error('Ten nick jest już zajęty.');

      const cfg=window.TENIS_AI_SUPABASE||{};
      const {data,error}=await client.auth.signUp({
        email,password,
        options:{data:{username},emailRedirectTo:cfg.siteUrl||location.origin+location.pathname}
      });
      if(error) throw error;

      show(data?.session
        ? 'Konto utworzone. Jesteś zalogowany ✅'
        : 'Konto utworzone. Sprawdź e-mail i potwierdź rejestrację ✅','ok');
    }catch(err){
      let text=String(err?.message||'Nie udało się wykonać operacji.');
      if(/already registered|user already registered/i.test(text)) text='Ten e-mail jest już zarejestrowany.';
      if(/invalid email/i.test(text)) text='Nieprawidłowy adres e-mail.';
      show(text,'error');
    }finally{
      if(btn){btn.disabled=false;btn.textContent='Utwórz konto';}
    }
  }, true);
})();