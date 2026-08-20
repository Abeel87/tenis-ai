
/* Tenis AI v6.6 — security-first Community Hub */
(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const initials = s => String(s || '?').trim().split(/\s+/).filter(Boolean).slice(0,2).map(x => x[0]).join('').toUpperCase() || '?';
  const fmtTime = x => {
    const d = new Date(x || '');
    return Number.isFinite(d.getTime()) ? d.toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : '—';
  };
  const fmtDate = x => {
    const d = new Date(x || '');
    return Number.isFinite(d.getTime()) ? d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}) : '—';
  };
  const online = x => {
    const t = new Date(x || '').getTime();
    return Number.isFinite(t) && Date.now() - t < 2 * 60 * 1000;
  };
  const acc = () => window.tenisAIAccount || {};
  const client = () => acc().client || null;
  const authUser = () => acc().user || null;

  const overlay = $('#community-hub-overlay');
  const body = $('#community-hub-body');
  const closeBtn = $('#community-hub-close');
  const openBtn = $('#community-hub-open');
  const preview = $('#community-hub-preview');

  let own = null;
  let hubTab = 'chat';
  let chatChannel = null;
  let chatRefreshTimer = null;
  let peopleCache = [];
  let followCache = [];
  let hubOpen = false;

  function hasAccess(){
    return Boolean(authUser() && own?.age_confirmed_at && own?.community_access && !own?.banned_at);
  }

  function avatar(p, cls='hub-avatar'){
    return `<span class="${cls}">${p?.avatar_url ? `<img src="${esc(p.avatar_url)}" alt="">` : esc(initials(p?.username))}</span>`;
  }

  async function refreshOwn(){
    const c = client(), u = authUser();
    if(!c || !u){ own = null; return null; }
    const {data,error} = await c.from('profiles')
      .select('id,username,avatar_url,bio,last_seen_at,created_at,age_confirmed_at,community_access,role,banned_at')
      .eq('id',u.id).maybeSingle();
    if(error){ console.warn('Community own profile:', error.message); own = null; return null; }
    own = data || null;
    window.tenisAICommunityHub = {
      get profile(){ return own; },
      get hasAccess(){ return hasAccess(); },
      open: openHub,
      refresh: async () => { await refreshOwn(); await refreshPublicStats(); updatePreview(); }
    };
    return own;
  }

  async function refreshPublicStats(){
    const c = client();
    if(!c) return;
    try{
      const {data,error} = await c.rpc('community_public_stats');
      if(error) throw error;
      const d = data || {};
      const ue = $('#community-users-count'), oe = $('#community-online-count'), ce = $('#community-coupons-count');
      if(ue) ue.textContent = d.registered ?? '—';
      if(oe) oe.textContent = d.online ?? '—';
      if(ce) ce.textContent = d.coupons_today ?? '—';
      const chip = $('#community-connection-chip');
      if(chip){ chip.textContent = 'LIVE'; chip.className = 'online'; }
    }catch(e){
      console.warn('Community stats:', e?.message || e);
    }
  }

  async function updatePreview(){
    if(!preview) return;
    const u = authUser();
    if(!u){
      preview.innerHTML = `<span>🔒 Zaloguj się, potwierdź 18+ i uzyskaj dostęp do społeczności.</span><button id="community-hub-open" type="button">Wejdź do społeczności →</button>`;
      bindPreviewButton(); return;
    }
    if(own?.banned_at){
      preview.innerHTML = `<span>⛔ Dostęp do społeczności jest zablokowany na tym koncie.</span><button id="community-hub-open" type="button">Szczegóły →</button>`;
      bindPreviewButton(); return;
    }
    if(!own?.age_confirmed_at){
      preview.innerHTML = `<span>🔞 Potwierdź, że masz ukończone 18 lat, aby przejść dalej.</span><button id="community-hub-open" type="button">Potwierdź 18+ →</button>`;
      bindPreviewButton(); return;
    }
    if(!own?.community_access){
      preview.innerHTML = `<span>🛡️ 18+ potwierdzone. Konto nie ma jeszcze dostępu do zamkniętych testów społeczności.</span><button id="community-hub-open" type="button">Sprawdź dostęp →</button>`;
      bindPreviewButton(); return;
    }
    try{
      const c = client();
      const {data} = await c.from('community_messages').select('body,created_at,user_id').order('created_at',{ascending:false}).limit(1);
      let text = '💬 Chat LIVE jest gotowy.';
      if(data?.[0]){
        const {data:p} = await c.from('profiles').select('username').eq('id',data[0].user_id).maybeSingle();
        text = `💬 ${p?.username || 'Użytkownik'}: ${data[0].body}`;
      }
      preview.innerHTML = `<span class="hub-preview-msg">${esc(text)}</span><button id="community-hub-open" type="button">Otwórz społeczność →</button>`;
    }catch{
      preview.innerHTML = `<span>✅ Masz dostęp do społeczności.</span><button id="community-hub-open" type="button">Otwórz społeczność →</button>`;
    }
    bindPreviewButton();
  }

  function bindPreviewButton(){
    $('#community-hub-open')?.addEventListener('click', e => { e.stopPropagation(); openHub('chat'); }, {once:true});
  }

  function openHub(tab='chat'){
    hubTab = ['chat','people','activity'].includes(tab) ? tab : 'chat';
    if(!overlay || !body) return;
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    hubOpen = true;
    renderHub();
  }

  function closeHub(){
    if(!overlay) return;
    overlay.hidden = true;
    document.body.style.overflow = '';
    hubOpen = false;
    stopChatRealtime();
  }

  function navHtml(){
    return `<nav class="hub-nav">
      <button data-hub-tab="chat" class="${hubTab==='chat'?'active':''}">💬 Chat</button>
      <button data-hub-tab="people" class="${hubTab==='people'?'active':''}">👥 Ludzie</button>
      <button data-hub-tab="activity" class="${hubTab==='activity'?'active':''}">🔥 Aktywność</button>
    </nav>`;
  }

  function bindNav(){
    $$('[data-hub-tab]').forEach(b => b.onclick = () => {
      hubTab = b.dataset.hubTab;
      stopChatRealtime();
      renderHub();
    });
  }

  async function renderHub(){
    if(!body) return;
    await refreshOwn();
    const u = authUser();

    if(!u){
      body.innerHTML = `<div class="hub-gate"><div class="hub-gate-icon">🔐</div><h3>Zaloguj się do Tenis AI</h3>
        <p>Społeczność, chat i publiczne kupony są oddzielone od części analitycznej aplikacji.</p>
        <button id="hub-open-account" class="hub-primary" type="button">👤 Zaloguj / załóż konto</button></div>`;
      $('#hub-open-account').onclick = () => { closeHub(); $('#account-button')?.click(); };
      return;
    }

    if(own?.banned_at){
      body.innerHTML = `<div class="hub-gate"><div class="hub-gate-icon">⛔</div><h3>Dostęp zablokowany</h3>
        <p>To konto nie ma dostępu do zamkniętej części społeczności.</p></div>`;
      return;
    }

    if(!own?.age_confirmed_at){
      body.innerHTML = `<div class="hub-gate"><div class="hub-gate-icon">🔞</div><h3>Potwierdzenie pełnoletności</h3>
        <p>Chat, profile społeczności i kupony są przeznaczone wyłącznie dla pełnoletnich użytkowników.</p>
        <div class="hub-warning">To jest oświadczenie użytkownika, a nie weryfikacja dokumentu. Nie zapisujemy PESEL-u, zdjęcia dowodu ani daty urodzenia.</div>
        <label class="hub-age-check"><input id="hub-age-checkbox" type="checkbox"><span>Oświadczam, że mam ukończone 18 lat i chcę uzyskać dostęp do części społecznościowej Tenis AI.</span></label>
        <button id="hub-age-confirm" class="hub-primary" type="button" disabled>Potwierdzam 18+</button>
        <p>Tenis AI pomaga analizować mecze tenisowe. Analizy i oceny modeli nie gwarantują wygranej.</p></div>`;
      const cb = $('#hub-age-checkbox'), btn = $('#hub-age-confirm');
      cb.onchange = () => btn.disabled = !cb.checked;
      btn.onclick = async () => {
        btn.disabled = true; btn.textContent = 'Zapisuję…';
        try{
          const {error} = await client().rpc('confirm_age_18');
          if(error) throw error;
          await refreshOwn(); await refreshPublicStats(); await updatePreview(); renderHub();
        }catch(e){
          btn.disabled = false; btn.textContent = 'Potwierdzam 18+';
          alert(e?.message || 'Nie udało się zapisać potwierdzenia 18+.');
        }
      };
      return;
    }

    if(!own?.community_access){
      const c = client();
      let request = null;
      try{
        const {data} = await c.from('community_access_requests').select('status,requested_at').eq('user_id',u.id).maybeSingle();
        request = data || null;
      }catch{}
      body.innerHTML = `<div class="hub-gate"><div class="hub-gate-icon">🛡️</div><h3>18+ potwierdzone</h3>
        <p>To konto nie ma jeszcze dostępu do zamkniętych testów społeczności. Nowe konta nie są wpuszczane automatycznie.</p>
        ${request ? `<div class="hub-request-status">Prośba o dostęp: <b>${esc(request.status)}</b> · ${esc(fmtTime(request.requested_at))}</div>` :
          `<button id="hub-request-access" class="hub-request-btn" type="button">Wyślij prośbę o dostęp</button>`}
        <p>W następnej wersji administrator będzie mógł zatwierdzać konta i nadawać moderatorów.</p></div>`;
      const rb = $('#hub-request-access');
      if(rb) rb.onclick = async () => {
        rb.disabled = true; rb.textContent = 'Wysyłam…';
        const {error} = await c.from('community_access_requests').insert({user_id:u.id});
        if(error && !String(error.message||'').toLowerCase().includes('duplicate')) alert(error.message);
        renderHub();
      };
      return;
    }

    body.innerHTML = navHtml() + `<div id="hub-panel"><div class="hub-empty">Ładowanie…</div></div>`;
    bindNav();
    if(hubTab === 'chat') await renderChat();
    if(hubTab === 'people') await renderPeople();
    if(hubTab === 'activity') await renderActivity();
  }

  async function loadProfiles(ids){
    const c = client();
    const unique = [...new Set((ids || []).filter(Boolean))];
    if(!unique.length) return new Map();
    const {data,error} = await c.from('profiles')
      .select('id,username,avatar_url,bio,last_seen_at,created_at,role')
      .in('id',unique);
    if(error) throw error;
    return new Map((data || []).map(p => [p.id,p]));
  }

  async function renderChat(){
    const panel = $('#hub-panel');
    if(!panel) return;
    panel.innerHTML = `<div class="hub-chat"><div class="hub-panel-title"><h3>💬 Chat LIVE</h3><small>maks. 500 znaków · antyspam</small></div>
      <div id="hub-chat-list" class="hub-chat-list"><div class="hub-empty">Ładowanie wiadomości…</div></div>
      <form id="hub-chat-form" class="hub-chat-form"><textarea maxlength="500" required placeholder="Napisz wiadomość…"></textarea><button type="submit">Wyślij</button></form></div>`;
    await loadChatMessages();
    const form = $('#hub-chat-form');
    form.onsubmit = async e => {
      e.preventDefault();
      const ta = form.querySelector('textarea'), btn = form.querySelector('button');
      const text = ta.value.trim();
      if(!text) return;
      btn.disabled = true;
      try{
        const {error} = await client().from('community_messages').insert({user_id:authUser().id,body:text});
        if(error) throw error;
        ta.value = '';
        await loadChatMessages(true);
      }catch(err){
        alert(err?.message || 'Nie udało się wysłać wiadomości.');
      }finally{ btn.disabled = false; }
    };
    startChatRealtime();
  }

  async function loadChatMessages(scroll=true){
    const list = $('#hub-chat-list');
    if(!list || !hasAccess()) return;
    try{
      const {data,error} = await client().from('community_messages')
        .select('id,user_id,body,created_at').order('created_at',{ascending:false}).limit(80);
      if(error) throw error;
      const rows = [...(data || [])].reverse();
      const pmap = await loadProfiles(rows.map(x => x.user_id));
      list.innerHTML = rows.length ? rows.map(m => {
        const p = pmap.get(m.user_id) || {username:'Użytkownik'};
        const mine = m.user_id === authUser()?.id;
        return `<article class="hub-message ${mine?'mine':''}">
          ${avatar(p)}
          <div class="hub-message-body">
            <div class="hub-message-meta"><button type="button" data-hub-profile="${esc(m.user_id)}">${esc(p.username)}</button><time>${esc(fmtTime(m.created_at))}</time></div>
            <div class="hub-message-text">${esc(m.body)}</div>
          </div>
        </article>`;
      }).join('') : `<div class="hub-empty">Jeszcze nikt nic nie napisał. Możesz zacząć 👋</div>`;
      $$('[data-hub-profile]').forEach(b => b.onclick = () => showProfile(b.dataset.hubProfile));
      if(scroll) list.scrollTop = list.scrollHeight;
    }catch(e){
      list.innerHTML = `<div class="hub-error">${esc(e?.message || 'Nie udało się pobrać chatu.')}</div>`;
    }
  }

  function startChatRealtime(){
    stopChatRealtime();
    const c = client();
    if(!c || !hasAccess()) return;
    try{
      chatChannel = c.channel('tenis-ai-community-chat-v66')
        .on('postgres_changes',{event:'INSERT',schema:'public',table:'community_messages'},() => {
          clearTimeout(chatRefreshTimer);
          chatRefreshTimer = setTimeout(() => loadChatMessages(true), 120);
        }).subscribe();
    }catch(e){ console.warn('Realtime:', e?.message || e); }
  }

  function stopChatRealtime(){
    clearTimeout(chatRefreshTimer);
    chatRefreshTimer = null;
    if(chatChannel && client()){
      try{ client().removeChannel(chatChannel); }catch{}
    }
    chatChannel = null;
  }

  async function fetchPeople(){
    const c = client();
    const [{data:people,error:pe},{data:follows,error:fe}] = await Promise.all([
      c.from('profiles').select('id,username,avatar_url,bio,last_seen_at,created_at,role,age_confirmed_at,community_access,banned_at')
        .eq('community_access',true).not('age_confirmed_at','is',null).is('banned_at',null).order('username'),
      c.from('profile_follows').select('follower_id,following_id,created_at')
    ]);
    if(pe) throw pe;
    peopleCache = people || [];
    followCache = fe ? [] : (follows || []);
    return peopleCache;
  }

  function renderPeopleRows(query=''){
    const box = $('#hub-people-list');
    if(!box) return;
    const q = String(query || '').trim().toLocaleLowerCase('pl');
    const me = authUser()?.id;
    const rows = peopleCache.filter(p => !q || `${p.username} ${p.bio||''}`.toLocaleLowerCase('pl').includes(q));
    box.innerHTML = rows.length ? rows.map(p => {
      const follows = followCache.filter(f => f.follower_id === p.id).length;
      const following = followCache.some(f => f.follower_id === me && f.following_id === p.id);
      const bio = p.bio || `${follows} obserwujących`;
      return `<article class="hub-person">
        <button class="hub-person-main" type="button" data-person="${esc(p.id)}">
          ${avatar(p)}
          <span class="hub-person-copy"><b>${online(p.last_seen_at)?'<span class="hub-online-dot">●</span>':'<span class="hub-offline-dot">●</span>'} ${esc(p.username)}${p.role && p.role!=='user'?` <span class="hub-role-badge">${esc(p.role)}</span>`:''}</b><small>${esc(bio)}</small></span>
        </button>
        ${p.id !== me ? `<button class="hub-follow ${following?'following':''}" type="button" data-follow="${esc(p.id)}">${following?'✓':'＋'}</button>` : ''}
      </article>`;
    }).join('') : `<div class="hub-empty">Nie znaleziono użytkownika.</div>`;
    $$('[data-person]').forEach(b => b.onclick = () => showProfile(b.dataset.person));
    $$('[data-follow]').forEach(b => b.onclick = () => toggleFollow(b.dataset.follow));
  }

  async function renderPeople(){
    const panel = $('#hub-panel');
    if(!panel) return;
    panel.innerHTML = `<div class="hub-panel-title"><h3>👥 Użytkownicy</h3><small id="hub-people-count">…</small></div>
      <input id="hub-user-search" class="hub-search" type="search" placeholder="Szukaj po nicku lub bio…">
      <div id="hub-people-list" class="hub-people-list"><div class="hub-empty">Ładowanie użytkowników…</div></div>`;
    try{
      await fetchPeople();
      $('#hub-people-count').textContent = `${peopleCache.length} osób`;
      renderPeopleRows('');
      $('#hub-user-search').oninput = e => renderPeopleRows(e.target.value);
    }catch(e){
      $('#hub-people-list').innerHTML = `<div class="hub-error">${esc(e?.message || 'Nie udało się pobrać użytkowników.')}</div>`;
    }
  }

  async function toggleFollow(id){
    const me = authUser()?.id;
    if(!me || !id || me === id) return;
    const existing = followCache.some(f => f.follower_id === me && f.following_id === id);
    try{
      if(existing){
        const {error} = await client().from('profile_follows').delete().eq('follower_id',me).eq('following_id',id);
        if(error) throw error;
      }else{
        const {error} = await client().from('profile_follows').insert({follower_id:me,following_id:id});
        if(error) throw error;
      }
      await fetchPeople();
      if(hubTab === 'people') renderPeopleRows($('#hub-user-search')?.value || '');
    }catch(e){ alert(e?.message || 'Nie udało się zmienić obserwowania.'); }
  }

  async function showProfile(id){
    const panel = $('#hub-panel');
    if(!panel || !id) return;
    stopChatRealtime();
    panel.innerHTML = `<div class="hub-empty">Ładowanie profilu…</div>`;
    try{
      const c = client();
      const [{data:p,error:pe},{data:coupons,error:ce},{data:follows,error:fe}] = await Promise.all([
        c.from('profiles').select('id,username,avatar_url,bio,last_seen_at,created_at,role').eq('id',id).single(),
        c.from('coupons').select('id,title,bookmaker,status,odds,share_url,verified,created_at').eq('user_id',id).eq('is_public',true).order('created_at',{ascending:false}).limit(30),
        c.from('profile_follows').select('follower_id,following_id')
      ]);
      if(pe || ce) throw pe || ce;
      const fs = fe ? [] : (follows || []);
      const followers = fs.filter(f => f.following_id === id).length;
      const followsCount = fs.filter(f => f.follower_id === id).length;
      const me = authUser()?.id;
      const following = fs.some(f => f.follower_id === me && f.following_id === id);
      const rows = coupons || [];
      panel.innerHTML = `<button id="hub-profile-back" class="hub-profile-back" type="button">← Wróć</button>
        <section class="hub-profile-card">
          <div class="hub-profile-top">${avatar(p)}<div><h3>${esc(p.username)}${p.role && p.role!=='user'?` <span class="hub-role-badge">${esc(p.role)}</span>`:''}</h3><p>${online(p.last_seen_at)?'🟢 Online':'⚫ Offline'} · dołączył ${esc(fmtDate(p.created_at))}</p></div></div>
          <div class="hub-profile-bio">${esc(p.bio || 'Ten użytkownik nie dodał jeszcze opisu.')}</div>
          <div class="hub-profile-kpis"><div><span>Kupony</span><b>${rows.length}</b></div><div><span>Obserwujący</span><b>${followers}</b></div><div><span>Obserwuje</span><b>${followsCount}</b></div></div>
          ${id !== me ? `<button id="hub-profile-follow" class="hub-follow ${following?'following':''}" type="button">${following?'✓ Obserwujesz':'＋ Obserwuj'}</button>` : ''}
        </section>
        <div class="hub-panel-title" style="margin-top:16px"><h3>🧾 Publiczne kupony</h3><small>${rows.length}</small></div>
        <div>${rows.length ? rows.slice(0,12).map(x => `<article class="hub-coupon-mini"><b>${esc(x.title || 'Kupon')}</b><small>${esc(x.bookmaker || 'inne')} · ${esc(x.status || 'pending')} · ${esc(fmtTime(x.created_at))}${x.verified?' · VERIFIED':''}</small>${x.share_url?`<a href="${esc(x.share_url)}" target="_blank" rel="noopener noreferrer">Otwórz kupon ↗</a>`:''}</article>`).join('') : '<div class="hub-empty">Brak publicznych kuponów.</div>'}</div>`;
      $('#hub-profile-back').onclick = () => { hubTab='people'; renderHub(); };
      const fbtn = $('#hub-profile-follow');
      if(fbtn) fbtn.onclick = async () => { await toggleFollow(id); showProfile(id); };
    }catch(e){
      panel.innerHTML = `<button id="hub-profile-back" class="hub-profile-back" type="button">← Wróć</button><div class="hub-error">${esc(e?.message || 'Nie udało się wczytać profilu.')}</div>`;
      $('#hub-profile-back').onclick = () => { hubTab='people'; renderHub(); };
    }
  }

  async function renderActivity(){
    const panel = $('#hub-panel');
    if(!panel) return;
    panel.innerHTML = `<div class="hub-panel-title"><h3>🔥 Aktywność społeczności</h3><small>najnowsze</small></div><div id="hub-activity-list"><div class="hub-empty">Ładowanie…</div></div>`;
    try{
      if(!peopleCache.length) await fetchPeople();
      const c = client();
      const [{data:coupons},{data:follows}] = await Promise.all([
        c.from('coupons').select('id,user_id,title,status,verified,created_at').eq('is_public',true).order('created_at',{ascending:false}).limit(30),
        c.from('profile_follows').select('follower_id,following_id,created_at').order('created_at',{ascending:false}).limit(30)
      ]);
      const pmap = new Map(peopleCache.map(p => [p.id,p]));
      const events = [];
      peopleCache.forEach(p => events.push({t:p.created_at,html:`👋 <b>${esc(p.username)}</b> dołączył do społeczności`}));
      (coupons || []).forEach(x => {
        const p = pmap.get(x.user_id);
        if(p) events.push({t:x.created_at,html:`🧾 <b>${esc(p.username)}</b> dodał kupon „${esc(x.title || 'Kupon')}”${x.verified?' · ✅ VERIFIED':''}`});
      });
      (follows || []).forEach(f => {
        const a=pmap.get(f.follower_id), b=pmap.get(f.following_id);
        if(a&&b) events.push({t:f.created_at,html:`👥 <b>${esc(a.username)}</b> zaczął obserwować <b>${esc(b.username)}</b>`});
      });
      events.sort((a,b)=>new Date(b.t)-new Date(a.t));
      const box = $('#hub-activity-list');
      box.innerHTML = events.length ? events.slice(0,40).map(e => `<article class="hub-activity">${e.html}<small>${esc(fmtTime(e.t))}</small></article>`).join('') : `<div class="hub-empty">Brak aktywności.</div>`;
    }catch(e){
      $('#hub-activity-list').innerHTML = `<div class="hub-error">${esc(e?.message || 'Nie udało się pobrać aktywności.')}</div>`;
    }
  }

  function renderLockedCoupons(){
    const app = $('#app');
    if(!app) return;
    $('#match-controls')?.setAttribute('style','display:none');
    $$('.main-tabs [data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === 'coupons'));
    let title='🔒 Kupony społeczności 18+';
    let text='Zaloguj się, potwierdź 18+ i uzyskaj dostęp do społeczności.';
    if(authUser() && own?.age_confirmed_at && !own?.community_access) text='18+ jest potwierdzone, ale konto nie ma jeszcze dostępu do zamkniętych testów.';
    if(own?.banned_at) text='Dostęp do społeczności jest zablokowany.';
    app.innerHTML = `<section class="hub-locked-view"><h2>${title}</h2><p>${esc(text)}</p><button id="hub-locked-open" class="hub-primary" type="button">Otwórz społeczność</button></section>`;
    $('#hub-locked-open').onclick = () => openHub('chat');
  }

  // Capture "Kupony" before the old renderer: UI gate is convenience, RLS in Supabase is the real protection.
  document.addEventListener('click', e => {
    const couponTab = e.target.closest('.main-tabs [data-view="coupons"]');
    if(couponTab && !hasAccess()){
      e.preventDefault();
      e.stopImmediatePropagation();
      renderLockedCoupons();
      return;
    }
    const stat = e.target.closest('[data-community-open]');
    if(stat){
      const target = stat.dataset.communityOpen;
      if(target === 'coupons'){
        if(hasAccess()) $('.main-tabs [data-view="coupons"]')?.click();
        else openHub('chat');
      }else openHub(target);
    }
  }, true);

  $('#community-live-stats')?.addEventListener('click', e => {
    if(e.target.closest('[data-community-open]') || e.target.closest('#community-hub-open')) return;
    openHub('chat');
  });
  openBtn?.addEventListener('click', e => { e.stopPropagation(); openHub('chat'); });
  closeBtn?.addEventListener('click', closeHub);
  overlay?.addEventListener('click', e => { if(e.target === overlay) closeHub(); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape' && hubOpen) closeHub(); });

  async function sync(){
    await refreshOwn();
    await refreshPublicStats();
    await updatePreview();
    if(hubOpen) renderHub();
  }

  window.addEventListener('tenis-ai-auth-change', () => setTimeout(sync, 70));
  setTimeout(sync, 350);
  setTimeout(sync, 1200);
  setInterval(refreshPublicStats, 15000);
})();
