/* Tenis AI v6.5.3 — persistent avatar without profile freeze
   v8.8.23 runtime cleanup: account/auth events replace body observer and retries.
*/
(() => {
  const RUNTIME_FIX='v8.8.23';
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

  function scheduleAvatar(){
    requestAnimationFrame(applyAvatar);
  }

  window.addEventListener('tenis-ai-auth-change', scheduleAvatar);
  document.addEventListener('click', e => {
    if(e.target.closest('#account-button')) scheduleAvatar();
  });

  scheduleAvatar();
  window.TENIS_AI_AVATAR_FIX=Object.freeze({runtimeFix:RUNTIME_FIX,apply:applyAvatar});
})();