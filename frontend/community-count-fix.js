/* Tenis AI v7.0.2 — community count clarity */
(() => {
  const $ = s => document.querySelector(s);

  async function syncCommunityMemberCount(){
    const hub = window.tenisAICommunityHub;
    const acc = window.tenisAIAccount || {};
    const client = acc.client;
    const label = $('#community-live-stats [data-community-open="people"] span');
    const countEl = $('#community-users-count');

    if(!label || !countEl) return;

    if(!hub?.hasAccess || !client){
      label.textContent = '👥 Konta';
      return;
    }

    label.textContent = '👥 Członkowie';
    try{
      const {count,error} = await client.from('profiles')
        .select('id',{count:'exact',head:true})
        .eq('community_access',true)
        .not('age_confirmed_at','is',null)
        .is('banned_at',null);
      if(error) throw error;
      if(Number.isFinite(count)) countEl.textContent = String(count);
      countEl.title = 'Konta dopuszczone do społeczności: 18+ + dostęp + brak blokady';
    }catch(e){
      console.warn('Community member count:', e?.message || e);
    }
  }

  window.addEventListener('tenis-ai-auth-change', () => setTimeout(syncCommunityMemberCount, 250));
  document.addEventListener('click', e => {
    if(e.target.closest('#refresh') || e.target.closest('#community-hub-open') || e.target.closest('[data-community-open="people"]')){
      setTimeout(syncCommunityMemberCount, 450);
    }
  });

  setTimeout(syncCommunityMemberCount, 900);
  setTimeout(syncCommunityMemberCount, 2200);
})();