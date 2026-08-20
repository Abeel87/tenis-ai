/* Tenis AI v6.5.2 — persist avatar display after reload */
(() => {
  const $ = s => document.querySelector(s);

  function escAttr(s){
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  function initials(name){
    return String(name || '?').trim().split(/\s+/).filter(Boolean).slice(0,2)
      .map(x => x[0]).join('').toUpperCase() || '?';
  }

  function applyAvatar(){
    const acc = window.tenisAIAccount;
    const p = acc?.profile;
    if(!p) return;

    const buttonAvatar = $('#account-button .account-button-avatar');
    if(buttonAvatar){
      if(p.avatar_url){
        buttonAvatar.innerHTML = `<img src="${escAttr(p.avatar_url)}" alt="">`;
      } else {
        buttonAvatar.textContent = initials(p.username);
      }
    }

    const modalAvatar = $('#account-modal-content .account-profile-avatar');
    if(modalAvatar){
      if(p.avatar_url){
        modalAvatar.innerHTML = `<img src="${escAttr(p.avatar_url)}" alt="">`;
      } else {
        modalAvatar.textContent = initials(p.username);
      }
    }
  }

  window.addEventListener('tenis-ai-auth-change', () => {
    setTimeout(applyAvatar, 40);
    setTimeout(applyAvatar, 180);
  });

  document.addEventListener('click', e => {
    if(e.target.closest('#account-button')){
      setTimeout(applyAvatar, 80);
      setTimeout(applyAvatar, 220);
    }
  });

  const observer = new MutationObserver(() => {
    if($('#account-modal-content .account-profile-avatar')) applyAvatar();
  });
  observer.observe(document.body, {childList:true, subtree:true});

  setTimeout(applyAvatar, 300);
  setTimeout(applyAvatar, 1000);
})();
