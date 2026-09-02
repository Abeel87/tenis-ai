/* Tenis AI v7.4 — Admin / Moderator panel */
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const acc = () => window.tenisAIAccount || {};
  const client = () => acc().client || null;
  const profile = () => window.tenisAICommunityHub?.profile || null;
  const fmt = x => {
    const d=new Date(x||'');
    return Number.isFinite(d.getTime()) ? d.toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : '—';
  };
  const online = x => {
    const t=new Date(x||'').getTime();
    return Number.isFinite(t) && Date.now()-t < 2*60*1000;
  };

  let rows=[];
  let filter='all';
  let search='';

  function isStaff(){
    return ['admin','moderator'].includes(profile()?.role);
  }
  function isAdmin(){
    return profile()?.role === 'admin';
  }

  function ensureButton(){
    const head=$('.community-hub-head');
    const close=$('#community-hub-close');
    if(!head || !close) return;
    let btn=$('#community-admin-open');
    if(!isStaff()){
      btn?.remove();
      return;
    }
    if(btn) return;
    btn=document.createElement('button');
    btn.id='community-admin-open';
    btn.type='button';
    btn.className='community-admin-open';
    btn.textContent=isAdmin()?'🛡️ Admin':'🛡️ Moderacja';
    btn.title=isAdmin()?'Panel administratora':'Panel moderatora';
    close.before(btn);
    btn.onclick=openAdmin;
  }

  async function openAdmin(){
    const overlay=$('#community-hub-overlay');
    const body=$('#community-hub-body');
    if(!overlay || !body || !isStaff()) return;
    overlay.hidden=false;
    document.body.style.overflow='hidden';
    body.innerHTML=`<section class="admin74">
      <div class="admin74-toolbar">
        <button id="admin74-back" type="button">← Społeczność</button>
        <div><b>${isAdmin()?'🛡️ Panel administratora':'🛡️ Panel moderatora'}</b><small>${isAdmin()?'Możesz nadawać moderatorów, zatwierdzać dostęp i blokować konta.':'Możesz zatwierdzać dostęp i moderować zwykłych użytkowników.'}</small></div>
        <button id="admin74-refresh" type="button">↻</button>
      </div>
      <div class="admin74-filters">
        <input id="admin74-search" type="search" placeholder="Szukaj użytkownika…">
        <button data-admin74-filter="all" class="active">Wszyscy</button>
        <button data-admin74-filter="pending">Prośby</button>
        <button data-admin74-filter="staff">Zespół</button>
        <button data-admin74-filter="banned">Blokady</button>
      </div>
      <div id="admin74-summary" class="admin74-summary">Ładowanie…</div>
      <div id="admin74-list" class="admin74-list"><div class="admin74-empty">Ładowanie użytkowników…</div></div>
    </section>`;
    $('#admin74-back').onclick=()=>window.tenisAICommunityHub?.open?.('people');
    $('#admin74-refresh').onclick=load;
    $('#admin74-search').oninput=e=>{search=e.target.value.trim().toLowerCase();renderList()};
    document.querySelectorAll('[data-admin74-filter]').forEach(b=>b.onclick=()=>{
      document.querySelectorAll('[data-admin74-filter]').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      filter=b.dataset.admin74Filter;
      renderList();
    });
    await load();
  }

  async function load(){
    const list=$('#admin74-list');
    if(!list) return;
    list.innerHTML='<div class="admin74-empty">Odświeżam…</div>';
    try{
      const c=client();
      if(!c) throw new Error('Brak połączenia z Supabase.');
      const {data,error}=await c.rpc('staff_member_list');
      if(error) throw error;
      rows=Array.isArray(data)?data:[];
      renderSummary();
      renderList();
    }catch(e){
      list.innerHTML=`<div class="admin74-error"><b>Nie udało się otworzyć panelu.</b><span>${esc(e?.message||e)}</span><small>Jeśli właśnie wdrażasz v7.4, uruchom najpierw plik supabase/v7.4-admin-moderator.sql w Supabase SQL Editor.</small></div>`;
    }
  }

  function renderSummary(){
    const el=$('#admin74-summary');
    if(!el) return;
    const pending=rows.filter(x=>x.request_status==='pending' && !x.community_access).length;
    const mods=rows.filter(x=>x.role==='moderator').length;
    const bans=rows.filter(x=>x.banned_at).length;
    const approved=rows.filter(x=>x.community_access && !x.banned_at).length;
    el.innerHTML=`<div><span>Użytkownicy</span><b>${rows.length}</b></div><div><span>Dostęp</span><b>${approved}</b></div><div><span>Prośby</span><b>${pending}</b></div><div><span>Moderatorzy</span><b>${mods}</b></div><div><span>Blokady</span><b>${bans}</b></div>`;
  }

  function roleBadge(r){
    if(r==='admin') return '<span class="admin74-role admin">ADMIN</span>';
    if(r==='moderator') return '<span class="admin74-role mod">MOD</span>';
    return '<span class="admin74-role user">USER</span>';
  }

  function filtered(){
    return rows.filter(x=>{
      if(search && !String(x.username||'').toLowerCase().includes(search)) return false;
      if(filter==='pending' && !(x.request_status==='pending' && !x.community_access)) return false;
      if(filter==='staff' && !['admin','moderator'].includes(x.role)) return false;
      if(filter==='banned' && !x.banned_at) return false;
      return true;
    });
  }

  function renderList(){
    const list=$('#admin74-list');
    if(!list) return;
    const data=filtered();
    if(!data.length){
      list.innerHTML='<div class="admin74-empty">Brak użytkowników dla tego filtra.</div>';
      return;
    }
    list.innerHTML=data.map(x=>{
      const self=x.id===profile()?.id;
      const canRole=isAdmin() && !self && x.role!=='admin';
      const canModerate=!self && x.role!=='admin' && (isAdmin() || x.role==='user');
      const accessText=x.banned_at?'ZABLOKOWANY':x.community_access?'DOSTĘP':'BRAK DOSTĘPU';
      const req=x.request_status==='pending'?'<span class="admin74-request">PROŚBA O DOSTĘP</span>':'';
      return `<article class="admin74-user ${x.banned_at?'banned':''}">
        <div class="admin74-user-main">
          <div class="admin74-avatar">${x.avatar_url?`<img src="${esc(x.avatar_url)}" alt="">`:'👤'}</div>
          <div class="admin74-copy">
            <div><b>${esc(x.username||'Użytkownik')}</b>${roleBadge(x.role)}${self?'<span class="admin74-self">TY</span>':''}</div>
            <small>${online(x.last_seen_at)?'🟢 online':'⚪ offline'} · konto ${fmt(x.created_at)}</small>
            <div class="admin74-state">${req}<span class="${x.community_access?'ok':'off'}">${accessText}</span>${x.age_confirmed_at?'<span>18+ ✓</span>':'<span>18+ —</span>'}</div>
          </div>
        </div>
        <div class="admin74-actions">
          ${!self && !x.community_access && !x.banned_at && canModerate?`<button data-a74="approve" data-id="${esc(x.id)}" class="good">✓ Dopuść</button>`:''}
          ${!self && x.community_access && canModerate?`<button data-a74="reject" data-id="${esc(x.id)}">Odbierz dostęp</button>`:''}
          ${canRole && x.role==='user'?`<button data-a74="promote" data-id="${esc(x.id)}" class="mod">★ Nadaj moderatora</button>`:''}
          ${canRole && x.role==='moderator'?`<button data-a74="demote" data-id="${esc(x.id)}">Usuń moderatora</button>`:''}
          ${canModerate && !x.banned_at?`<button data-a74="ban" data-id="${esc(x.id)}" class="danger">⛔ Zablokuj</button>`:''}
          ${canModerate && x.banned_at?`<button data-a74="unban" data-id="${esc(x.id)}" class="good">↩ Odblokuj</button>`:''}
        </div>
      </article>`;
    }).join('');
    list.querySelectorAll('[data-a74]').forEach(b=>b.onclick=()=>act(b));
  }

  async function act(btn){
    const action=btn.dataset.a74, id=btn.dataset.id;
    const row=rows.find(x=>String(x.id)===String(id));
    if(!row) return;
    const labels={
      approve:`Dopuścić ${row.username} do społeczności?`,
      reject:`Odebrać ${row.username} dostęp do społeczności?`,
      promote:`Nadać ${row.username} rolę MODERATOR?`,
      demote:`Usunąć rolę moderatora użytkownikowi ${row.username}?`,
      ban:`Zablokować konto ${row.username} w społeczności?`,
      unban:`Odblokować konto ${row.username}?`
    };
    if(!confirm(labels[action]||'Wykonać akcję?')) return;
    btn.disabled=true;
    try{
      const c=client();
      let result;
      if(action==='approve') result=await c.rpc('staff_review_access',{target_uid:id,decision:'approve'});
      if(action==='reject') result=await c.rpc('staff_review_access',{target_uid:id,decision:'reject'});
      if(action==='promote') result=await c.rpc('admin_set_role',{target_uid:id,next_role:'moderator'});
      if(action==='demote') result=await c.rpc('admin_set_role',{target_uid:id,next_role:'user'});
      if(action==='ban') result=await c.rpc('staff_set_ban',{target_uid:id,should_ban:true});
      if(action==='unban') result=await c.rpc('staff_set_ban',{target_uid:id,should_ban:false});
      if(result?.error) throw result.error;
      await window.tenisAICommunityHub?.refresh?.();
      await load();
    }catch(e){
      alert(e?.message||'Nie udało się wykonać akcji.');
      btn.disabled=false;
    }
  }

  // Bez MutationObserver: lekki check, żeby nie wejść w pętle renderowania.
  setInterval(ensureButton,1200);
  window.addEventListener('tenis-ai-auth-changed',()=>setTimeout(ensureButton,50));
  setTimeout(async()=>{
    try{ await window.tenisAICommunityHub?.refresh?.(); }catch{}
    ensureButton();
  },900);
})();
