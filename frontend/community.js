/* Tenis AI v6.5 — shared coupon community + public profiles */
(() => {
  const $=s=>document.querySelector(s);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const initials=s=>String(s||'?').trim().split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()||'?';
  const fmtDate=x=>{const d=new Date(x||'');return Number.isFinite(d.getTime())?d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}):'—'};
  const fmtTime=x=>{const d=new Date(x||'');return Number.isFinite(d.getTime())?d.toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'—'};
  const acc=()=>window.tenisAIAccount||{};
  const client=()=>acc().client||null;
  const user=()=>acc().user||null;
  const profile=()=>acc().profile||null;
  let feedFilter='all';
  let feedBusy=false;

  const BOOKS={superbet:'Superbet',betclic:'Betclic',sts:'STS',fortuna:'Fortuna',other:'Inny'};
  const STATUS={pending:'⏳ Grany',won:'✅ Wygrany',lost:'❌ Przegrany',cashout:'💰 Cashout',void:'↩️ Zwrot'};
  function detectBook(url){const x=String(url||'').toLowerCase();if(x.includes('superbet')||x.includes('onelink.me/tegf'))return'superbet';if(x.includes('betclic'))return'betclic';if(x.includes('sts.pl')||x.includes('stsbet'))return'sts';if(x.includes('efortuna')||x.includes('fortuna'))return'fortuna';return'other'}
  const statusClass=s=>['won','lost','cashout'].includes(s)?s:'';
  function avatarHtml(p,cls='shared-avatar'){return `<span class="${cls}">${p?.avatar_url?`<img src="${esc(p.avatar_url)}" alt="">`:esc(initials(p?.username))}</span>`}

  function ensureProfileOverlay(){
    if($('#community-profile-overlay'))return;
    document.body.insertAdjacentHTML('beforeend',`<div id="community-profile-overlay" class="community-profile-overlay" hidden><section class="community-profile-modal"><button class="community-profile-close" type="button">✕</button><div id="community-profile-content"></div></section></div>`);
    const ov=$('#community-profile-overlay');ov.querySelector('.community-profile-close').onclick=()=>{ov.hidden=true;document.body.style.overflow=''};ov.onclick=e=>{if(e.target===ov){ov.hidden=true;document.body.style.overflow=''}};
  }

  async function openPublicProfile(id){
    const c=client();if(!c||!id)return;
    ensureProfileOverlay();const ov=$('#community-profile-overlay'),box=$('#community-profile-content');ov.hidden=false;document.body.style.overflow='hidden';box.innerHTML='<div class="shared-empty">Ładowanie profilu…</div>';
    try{
      const [{data:p,error:pe},{data:coupons,error:ce},{count:followers},{count:following}]=await Promise.all([
        c.from('profiles').select('id,username,avatar_url,bio,created_at').eq('id',id).single(),
        c.from('coupons').select('id,title,bookmaker,status,verified,created_at').eq('user_id',id).eq('is_public',true).order('created_at',{ascending:false}).limit(30),
        c.from('profile_follows').select('follower_id',{count:'exact',head:true}).eq('following_id',id),
        c.from('profile_follows').select('following_id',{count:'exact',head:true}).eq('follower_id',id)
      ]);
      if(pe||ce)throw pe||ce;
      const rows=coupons||[],verified=rows.filter(x=>x.verified),wins=verified.filter(x=>x.status==='won').length,losses=verified.filter(x=>x.status==='lost').length,settled=wins+losses,accuracy=settled?Math.round(100*wins/settled):null;
      let isFollowing=false;const me=user();if(me&&me.id!==id){const {count}=await c.from('profile_follows').select('following_id',{count:'exact',head:true}).eq('follower_id',me.id).eq('following_id',id);isFollowing=Number(count||0)>0}
      box.innerHTML=`<div class="public-profile-head">${avatarHtml(p,'public-profile-avatar')}<div><h2>${esc(p.username)}</h2><p>Dołączył ${esc(fmtDate(p.created_at))}</p></div></div>
        <div class="public-profile-bio">${esc(p.bio||'Ten użytkownik nie dodał jeszcze opisu.')}</div>
        <div class="public-profile-kpis"><div><span>Kupony</span><b>${rows.length}</b></div><div><span>Zweryfikowane</span><b>${settled}</b></div><div><span>Skuteczność</span><b>${accuracy==null?'—':accuracy+'%'}</b></div><div><span>Obserwujący</span><b>${followers||0}</b></div><div><span>Obserwuje</span><b>${following||0}</b></div><div><span>Bilans verified</span><b>${wins}–${losses}</b></div></div>
        ${me&&me.id!==id?`<button id="public-profile-follow" class="public-profile-follow ${isFollowing?'following':''}" type="button">${isFollowing?'✓ Obserwujesz':'＋ Obserwuj'}</button>`:''}
        <div class="public-profile-coupons">${rows.length?rows.slice(0,6).map(x=>`<div class="public-profile-mini"><b>${esc(x.title||('Kupon '+(BOOKS[x.bookmaker]||x.bookmaker||'')))}</b><span>${esc(STATUS[x.status]||x.status)} · ${esc(fmtDate(x.created_at))}${x.verified?' · VERIFIED':' · niezweryfikowany'}</span></div>`).join(''):'<div class="shared-empty">Brak publicznych kuponów.</div>'}</div>`;
      const fb=$('#public-profile-follow');if(fb)fb.onclick=async()=>{fb.disabled=true;try{if(isFollowing){await c.from('profile_follows').delete().eq('follower_id',me.id).eq('following_id',id);isFollowing=false}else{const {error}=await c.from('profile_follows').insert({follower_id:me.id,following_id:id});if(error)throw error;isFollowing=true}await openPublicProfile(id)}catch(e){alert(e.message||'Nie udało się zmienić obserwowania.')}finally{fb.disabled=false}};
    }catch(e){box.innerHTML=`<div class="shared-empty">Nie udało się wczytać profilu.<br>${esc(e?.message||'')}</div>`}
  }

  async function loadFeedData(){
    const c=client();if(!c)throw new Error('Brak połączenia z bazą.');
    let q=c.from('coupons').select('id,user_id,bookmaker,share_url,title,description,odds,status,verified,settlement_source,is_public,created_at,updated_at').eq('is_public',true).order('created_at',{ascending:false}).limit(40);
    if(feedFilter!=='all')q=q.eq('status',feedFilter);
    const {data:coupons,error}=await q;if(error)throw error;
    const rows=coupons||[],ids=[...new Set(rows.map(x=>x.user_id))],couponIds=rows.map(x=>x.id);
    let profiles=[],likes=[],comments=[];
    if(ids.length){const r=await c.from('profiles').select('id,username,avatar_url,bio').in('id',ids);if(!r.error)profiles=r.data||[]}
    if(couponIds.length){
      const [lr,cr]=await Promise.all([c.from('coupon_likes').select('coupon_id,user_id').in('coupon_id',couponIds),c.from('coupon_comments').select('id,coupon_id,user_id,body,created_at').in('coupon_id',couponIds).order('created_at',{ascending:true}).limit(250)]);
      if(!lr.error)likes=lr.data||[];if(!cr.error)comments=cr.data||[];
      const commentUsers=[...new Set(comments.map(x=>x.user_id).filter(x=>!ids.includes(x)))];if(commentUsers.length){const pr=await c.from('profiles').select('id,username,avatar_url').in('id',commentUsers);if(!pr.error)profiles=profiles.concat(pr.data||[])}
    }
    const pmap=new Map(profiles.map(x=>[x.id,x]));return {rows,likes,comments,pmap};
  }

  function addFormHtml(){
    const me=user();if(!me)return `<div class="shared-login-call">Zaloguj się, żeby wrzucić kupon do wspólnego feedu.<br><button id="shared-login-open" type="button">👤 Otwórz konto</button></div>`;
    return `<details class="shared-add"><summary>＋ Dodaj kupon z linku ▾</summary><form id="shared-coupon-form" class="shared-form">
      <label class="wide">Link udostępnionego kuponu<input name="share_url" type="url" required placeholder="https://superbet.onelink.me/..." inputmode="url"></label>
      <label>Bukmacher<select name="bookmaker"><option value="auto">Wykryj z linku</option><option value="superbet">Superbet</option><option value="betclic">Betclic</option><option value="sts">STS</option><option value="fortuna">Fortuna</option><option value="other">Inny</option></select></label>
      <label>Kurs<input name="odds" inputmode="decimal" placeholder="Np. 8.45"></label>
      <label class="wide">Tytuł<input name="title" maxlength="90" placeholder="Np. Tenis na wieczór"></label>
      <label class="wide">Opis<textarea name="description" maxlength="900" placeholder="Opcjonalnie: co jest na kuponie, dlaczego go grasz…"></textarea></label>
      <button class="primary-btn" type="submit">Opublikuj kupon</button></form></details>`;
  }

  function couponHtml(x,data){
    const p=data.pmap.get(x.user_id)||{username:'Użytkownik'},me=user(),own=me?.id===x.user_id,likes=data.likes.filter(l=>l.coupon_id===x.id),liked=Boolean(me&&likes.some(l=>l.user_id===me.id)),comments=data.comments.filter(c=>c.coupon_id===x.id),status=STATUS[x.status]||x.status||'⏳ Grany',book=BOOKS[x.bookmaker]||x.bookmaker||'Kupon';
    return `<article class="shared-card" data-coupon="${esc(x.id)}"><div class="shared-card-head"><button class="shared-author" type="button" data-profile-id="${esc(x.user_id)}">${avatarHtml(p)}<span><b>${esc(p.username)}</b><small>${esc(fmtTime(x.created_at))}</small></span></button><span class="shared-status ${statusClass(x.status)}">${esc(status)}</span></div>
      <div class="shared-card-body"><div class="shared-bookmaker">🎟️ ${esc(book)}</div><h3>${esc(x.title||('Kupon '+book))}</h3>${x.description?`<p>${esc(x.description)}</p>`:''}<div class="shared-meta">${x.odds?`<span>Kurs <b>${esc(x.odds)}</b></span>`:''}<span>${x.verified?'✅ VERIFIED':'🟡 USER STATUS'}</span></div>${x.share_url?`<a class="shared-open-link" href="${esc(x.share_url)}" target="_blank" rel="noopener noreferrer">Otwórz udostępniony kupon ↗</a>`:''}<div class="shared-verification ${x.verified?'verified':''}">${x.verified?'Wynik zweryfikowany — może liczyć się do rankingu.':'Wynik niezweryfikowany — nie liczy się do rankingu.'}</div></div>
      <div class="shared-actions"><button type="button" data-like="${esc(x.id)}" class="${liked?'liked':''}">❤️ ${likes.length}</button><button type="button" data-focus-comment="${esc(x.id)}">💬 ${comments.length}</button></div>
      ${own?`<div class="owner-status"><button data-status="pending" data-id="${esc(x.id)}" class="${x.status==='pending'?'active':''}">Grany</button><button data-status="won" data-id="${esc(x.id)}" class="${x.status==='won'?'active':''}">Wygrany</button><button data-status="lost" data-id="${esc(x.id)}" class="${x.status==='lost'?'active':''}">Przegrany</button><button data-status="cashout" data-id="${esc(x.id)}" class="${x.status==='cashout'?'active':''}">Cashout</button></div>`:''}
      <div class="shared-comments">${comments.slice(-4).map(cm=>{const cp=data.pmap.get(cm.user_id)||{username:'Użytkownik'};return `<div class="shared-comment"><b>${esc(cp.username)}:</b> ${esc(cm.body)}</div>`}).join('')}${me?`<form class="shared-comment-form" data-comment="${esc(x.id)}"><input maxlength="300" placeholder="Dodaj komentarz…"><button>Wyślij</button></form>`:''}</div></article>`;
  }

  async function renderSharedCoupons(){
    const app=$('#app');if(!app)return;if(feedBusy){app.innerHTML='<div class="shared-empty">Odświeżam społeczność…</div>';return}feedBusy=true;
    app.innerHTML=`<section class="shared-hero"><div class="shared-hero-top"><div><h2>🧾 Kupony społeczności</h2><p>Wspólny feed użytkowników Tenis AI. Linki: Superbet, Betclic, STS, Fortuna i inne.</p></div><span class="shared-live-badge">LIVE</span></div><div class="shared-note">Status ustawiony przez użytkownika jest oznaczony jako niezweryfikowany. Do przyszłego rankingu wejdą tylko wyniki rozliczone i oznaczone <b>VERIFIED</b>.</div></section>${addFormHtml()}<div class="shared-toolbar"><button data-feed-filter="all" class="${feedFilter==='all'?'active':''}">Wszystkie</button><button data-feed-filter="pending" class="${feedFilter==='pending'?'active':''}">⏳ Grane</button><button data-feed-filter="won" class="${feedFilter==='won'?'active':''}">✅ Wygrane</button><button data-feed-filter="lost" class="${feedFilter==='lost'?'active':''}">❌ Przegrane</button><button data-feed-filter="cashout" class="${feedFilter==='cashout'?'active':''}">💰 Cashout</button></div><div id="shared-feed" class="shared-feed"><div class="shared-empty">Ładowanie kuponów…</div></div>`;
    try{
      const data=await loadFeedData(),feed=$('#shared-feed');feed.innerHTML=data.rows.length?data.rows.map(x=>couponHtml(x,data)).join(''):'<div class="shared-empty">Nie ma jeszcze publicznych kuponów. Wrzuć pierwszy 😎</div>';bindFeed(data);
    }catch(e){$('#shared-feed').innerHTML=`<div class="shared-empty">Nie udało się pobrać feedu.<br>${esc(e?.message||'')}</div>`}finally{feedBusy=false}
    document.querySelectorAll('[data-feed-filter]').forEach(b=>b.onclick=()=>{feedFilter=b.dataset.feedFilter;renderSharedCoupons()});
    const login=$('#shared-login-open');if(login)login.onclick=()=>$('#account-button')?.click();
    const form=$('#shared-coupon-form');if(form)form.onsubmit=submitCoupon;
  }

  function bindFeed(data){
    const c=client(),me=user();document.querySelectorAll('[data-profile-id]').forEach(b=>b.onclick=()=>openPublicProfile(b.dataset.profileId));
    document.querySelectorAll('[data-like]').forEach(b=>b.onclick=async()=>{if(!me){$('#account-button')?.click();return}b.disabled=true;try{const id=b.dataset.like,liked=data.likes.some(l=>l.coupon_id===id&&l.user_id===me.id);const r=liked?await c.from('coupon_likes').delete().eq('coupon_id',id).eq('user_id',me.id):await c.from('coupon_likes').insert({coupon_id:id,user_id:me.id});if(r.error)throw r.error;await renderSharedCoupons()}catch(e){alert(e.message||'Nie udało się dodać reakcji.')}finally{b.disabled=false}});
    document.querySelectorAll('[data-focus-comment]').forEach(b=>b.onclick=()=>document.querySelector(`[data-comment="${CSS.escape(b.dataset.focusComment)}"] input`)?.focus());
    document.querySelectorAll('[data-comment]').forEach(f=>f.onsubmit=async e=>{e.preventDefault();if(!me)return;const inp=f.querySelector('input'),body=inp.value.trim();if(!body)return;const btn=f.querySelector('button');btn.disabled=true;try{const {error}=await c.from('coupon_comments').insert({coupon_id:f.dataset.comment,user_id:me.id,body});if(error)throw error;await renderSharedCoupons()}catch(err){alert(err.message||'Nie udało się wysłać komentarza.')}finally{btn.disabled=false}});
    document.querySelectorAll('[data-status]').forEach(b=>b.onclick=async()=>{if(!me)return;b.disabled=true;try{const {error}=await c.from('coupons').update({status:b.dataset.status,verified:false,settlement_source:'user',updated_at:new Date().toISOString(),settled_at:b.dataset.status==='pending'?null:new Date().toISOString()}).eq('id',b.dataset.id).eq('user_id',me.id);if(error)throw error;await renderSharedCoupons();acc().refreshStats?.()}catch(e){alert(e.message||'Nie udało się zmienić statusu.')}finally{b.disabled=false}});
  }

  async function submitCoupon(e){
    e.preventDefault();const c=client(),me=user();if(!c||!me)return;const f=e.currentTarget,fd=new FormData(f),url=String(fd.get('share_url')||'').trim(),manual=String(fd.get('bookmaker')||'auto'),book=manual==='auto'?detectBook(url):manual,title=String(fd.get('title')||'').trim(),description=String(fd.get('description')||'').trim(),rawOdds=String(fd.get('odds')||'').trim().replace(',','.');const odds=rawOdds&&Number.isFinite(Number(rawOdds))?Number(rawOdds):null,btn=f.querySelector('button[type=submit]');btn.disabled=true;btn.textContent='Publikuję…';
    try{const {error}=await c.from('coupons').insert({user_id:me.id,bookmaker:book,share_url:url,title:title||`Kupon ${BOOKS[book]||'użytkownika'}`,description:description||null,odds,status:'pending',verified:false,settlement_source:'user',is_public:true});if(error)throw error;f.reset();await renderSharedCoupons();acc().refreshStats?.()}catch(err){alert(err.message||'Nie udało się opublikować kuponu.')}finally{btn.disabled=false;btn.textContent='Opublikuj kupon'}
  }

  function enhanceOwnProfile(){
    setTimeout(()=>{const p=profile(),me=user(),c=client(),modal=$('#account-modal-content');if(!p||!me||!c||!modal||modal.querySelector('.profile-editor'))return;const signout=$('#account-signout');if(!signout)return;signout.insertAdjacentHTML('beforebegin',`<button id="account-public-profile" class="account-public-profile" type="button">🌐 Zobacz profil publiczny</button><section class="profile-editor"><h4>✏️ Edytuj profil</h4><label>Bio<textarea id="profile-bio" maxlength="300" placeholder="Kilka słów o sobie…">${esc(p.bio||'')}</textarea></label><label>Avatar<input id="profile-avatar-file" type="file" accept="image/*"></label><button id="profile-save" type="button">Zapisz profil</button><div id="profile-editor-msg" class="profile-editor-msg"></div></section>`);
      $('#account-public-profile').onclick=()=>openPublicProfile(me.id);$('#profile-save').onclick=async()=>{const btn=$('#profile-save'),msg=$('#profile-editor-msg'),bio=$('#profile-bio').value.trim(),file=$('#profile-avatar-file').files?.[0];btn.disabled=true;msg.textContent='Zapisuję…';try{let avatar=p.avatar_url||null;if(file){if(file.size>4*1024*1024)throw new Error('Avatar może mieć maks. 4 MB.');const ext=(file.name.split('.').pop()||'jpg').toLowerCase().replace(/[^a-z0-9]/g,'')||'jpg',path=`${me.id}/avatar.${ext}`,up=await c.storage.from('avatars').upload(path,file,{upsert:true,cacheControl:'3600'});if(up.error)throw up.error;const pub=c.storage.from('avatars').getPublicUrl(path);avatar=pub.data.publicUrl+'?v='+Date.now()}
        const {error}=await c.from('profiles').update({bio,avatar_url:avatar,last_seen_at:new Date().toISOString()}).eq('id',me.id);if(error)throw error;p.bio=bio;p.avatar_url=avatar;msg.textContent='Profil zapisany ✅';const a=modal.querySelector('.account-profile-avatar');if(a&&avatar)a.innerHTML=`<img src="${esc(avatar)}" alt="">`;const ab=$('#account-button .account-button-avatar');if(ab&&avatar)ab.innerHTML=`<img src="${esc(avatar)}" alt="">`;}catch(err){msg.textContent='Błąd: '+(err.message||'nie udało się zapisać')}finally{btn.disabled=false}};
    },60)
  }

  try{renderCoupons=renderSharedCoupons}catch{window.renderCoupons=renderSharedCoupons}
  ensureProfileOverlay();$('#account-button')?.addEventListener('click',enhanceOwnProfile);window.addEventListener('tenis-ai-auth-change',()=>{enhanceOwnProfile();if($('.main-tabs button.active')?.dataset.view==='coupons')renderSharedCoupons()});
  window.tenisAICommunity={render:renderSharedCoupons,openProfile:openPublicProfile};
})();
