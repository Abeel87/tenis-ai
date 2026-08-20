/* Tenis AI v6.5.3 — persistent avatar without profile freeze */
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

  function setAvatar(el, profile){
    if(!el || !profile) return;

    if(profile.avatar_url){
      const img = el.querySelector('img');
      if(img && img.getAttribute('src') === profile.avatar_url) return;
      el.innerHTML = `<img src="${escAttr(profile.avatar_url)}" alt="">`;
      return;
    }

    const text = initials(profile.username);
    if(el.textContent !== text || el.querySelector('img')) el.textContent = text;
  }

  function applyAvatar(){
    const profile = window.tenisAIAccount?.profile;
    if(!profile) return;
    setAvatar($('#account-button .account-button-avatar'), profile);
    setAvatar($('#account-modal-content .account-profile-avatar'), profile);
  }

  window.addEventListener('tenis-ai-auth-change', () => {
    setTimeout(applyAvatar, 40);
    setTimeout(applyAvatar, 180);
  });

  document.addEventListener('click', e => {
    if(e.target.closest('#account-button')){
      setTimeout(applyAvatar, 40);
      setTimeout(applyAvatar, 140);
    }
  });

  // Modal content is recreated by account.js. Observe it, but only write when
  // the rendered avatar actually differs, so the observer cannot loop forever.
  const observer = new MutationObserver(() => {
    if($('#account-modal-content .account-profile-avatar')) applyAvatar();
  });
  observer.observe(document.body, {childList:true, subtree:true});

  setTimeout(applyAvatar, 300);
  setTimeout(applyAvatar, 1000);
})();
