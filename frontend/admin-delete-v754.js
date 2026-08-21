/* Tenis AI v7.5.4 — permanent delete for admin only */
(() => {
  const $ = s => document.querySelector(s);
  const profile = () => window.tenisAICommunityHub?.profile || null;
  const client = () => window.tenisAIAccount?.client || null;

  function isAdmin(){
    return profile()?.role === 'admin';
  }

  function usernameFromArticle(article){
    return article?.querySelector('.admin74-copy b')?.textContent?.trim() || 'użytkownik';
  }

  function targetIdFromArticle(article){
    const btn = article?.querySelector('[data-a74][data-id]');
    return btn?.dataset?.id || null;
  }

  async function removeAccount(article, button){
    if(!isAdmin()) return;

    const id = targetIdFromArticle(article);
    const username = usernameFromArticle(article);
    if(!id){
      alert('Nie udało się odczytać ID użytkownika.');
      return;
    }

    const first = confirm(
      `TRWAŁE USUNIĘCIE KONTA\n\n` +
      `Użytkownik: ${username}\n\n` +
      `Ta operacja usuwa konto logowania i dane użytkownika. ` +
      `Nie da się jej cofnąć.\n\nKontynuować?`
    );
    if(!first) return;

    const phrase = prompt(
      `Aby potwierdzić trwałe usunięcie konta ${username}, wpisz dokładnie:\n\nUSUŃ NA STAŁE`
    );
    if(phrase !== 'USUŃ NA STAŁE'){
      alert('Usuwanie anulowane — tekst potwierdzenia był nieprawidłowy.');
      return;
    }

    button.disabled = true;
    button.textContent = 'Usuwam…';

    try{
      const c = client();
      if(!c) throw new Error('Brak połączenia z Supabase.');

      const {data,error} = await c.rpc('admin_delete_user',{target_uid:id});
      if(error) throw error;
      if(data !== true) throw new Error('Serwer nie potwierdził usunięcia konta.');

      alert(`Konto ${username} zostało trwale usunięte.`);
      try{ await window.tenisAICommunityHub?.refresh?.(); }catch{}
      $('#admin74-refresh')?.click();
    }catch(e){
      alert(e?.message || 'Nie udało się usunąć konta.');
      button.disabled = false;
      button.textContent = '🗑 Usuń konto';
    }
  }

  function decorate(){
    if(!isAdmin()) return;

    document.querySelectorAll('.admin74-user').forEach(article => {
      if(article.querySelector('[data-a754="delete"]')) return;

      const role = article.querySelector('.admin74-role')?.textContent?.trim();
      const self = Boolean(article.querySelector('.admin74-self'));
      const actions = article.querySelector('.admin74-actions');

      // Twarde kasowanie pokazujemy tylko dla zwykłego USER-a.
      // Moderator musi najpierw zostać zdegradowany.
      if(!actions || self || role !== 'USER') return;

      const id = targetIdFromArticle(article);
      if(!id) return;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.dataset.a754 = 'delete';
      btn.className = 'danger admin754-delete';
      btn.textContent = '🗑 Usuń konto';
      btn.title = 'Trwale usuń konto i dane użytkownika';
      btn.onclick = () => removeAccount(article,btn);
      actions.appendChild(btn);
    });
  }

  // Panel v7.4 renderuje listę dynamicznie, więc lekko dopinamy przycisk po renderze.
  setInterval(decorate,900);
  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(decorate,50));
  window.addEventListener('tenis-ai-auth-changed',()=>setTimeout(decorate,50));
  document.addEventListener('click',()=>setTimeout(decorate,80));
  setTimeout(decorate,700);
})();