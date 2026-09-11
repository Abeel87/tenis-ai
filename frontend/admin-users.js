/* Tenis AI — staff account management on top of the canonical UI. */
(()=>{
'use strict';
if(typeof document==='undefined'||typeof document.createElement!=='function')return;
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const A=()=>window.TenisAccount;
let rows=[],query='',generation=0,loading=false;
function isAdmin(){return A()?.authenticated&&A()?.role==='admin'}
function isModerator(){return A()?.authenticated&&A()?.role==='moderator'}
function currentRoute(){return (isAdmin()&&location.hash==='#admin/users')||(isModerator()&&location.hash==='#moderator')}
function fmt(x){const d=new Date(x||'');return Number.isFinite(d.getTime())?d.toLocaleString('pl-PL',{timeZone:'Europe/Warsaw',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'—'}
function badge(role){return `<span class="admin-user-role ${esc(role)}">${esc(String(role||'user').toUpperCase())}</span>`}
function ensureHost(){
  if(isAdmin())return $('#users-list');
  if(!isModerator())return null;
  let host=$('[data-staff-users-host]');
  if(host)return host;
  const matchList=$('#moderator-list');
  if(!matchList)return null;
  const panel=document.createElement('section');
  panel.className='panel';
  panel.dataset.moderatorUsersPanel='1';
  panel.innerHTML='<h2>Użytkownicy</h2><p class="muted">Moderator może zatwierdzać dostęp i blokować zwykłych użytkowników. Role oraz trwałe usuwanie kont pozostają wyłącznie dla administratora.</p><div data-staff-users-host></div>';
  matchList.before(panel);
  return panel.querySelector('[data-staff-users-host]');
}
function mount(){
  if(!currentRoute())return;
  const host=ensureHost();
  if(!host||host.querySelector('[data-admin-users-root]'))return;
  host.innerHTML='<div data-admin-users-root><div class="admin-users-toolbar"><label>Szukaj użytkownika<input type="search" data-admin-user-search placeholder="Nick"></label><button type="button" data-admin-users-reload>↻ Odśwież</button></div><div data-admin-users-summary class="admin-users-summary"></div><div data-admin-users-list class="admin-users-list"><div class="empty">Ładowanie użytkowników…</div></div></div>';
  host.querySelector('[data-admin-user-search]').value=query;
  if(!host.dataset.adminUsersBound){
    host.dataset.adminUsersBound='1';
    host.addEventListener('input',e=>{if(e.target.matches('[data-admin-user-search]')){query=e.target.value.trim().toLowerCase();render()}});
    host.addEventListener('click',e=>{
      const reload=e.target.closest('[data-admin-users-reload]');if(reload){load();return}
      const button=e.target.closest('[data-admin-user-action]');if(button)act(button);
    });
  }
  load();
}
async function load(){
  if(!currentRoute()||loading)return;
  const root=$('[data-admin-users-root]');if(!root)return;
  const list=root.querySelector('[data-admin-users-list]');if(list)list.innerHTML='<div class="empty">Odświeżam użytkowników…</div>';
  const myGeneration=++generation;loading=true;
  try{
    const {data,error}=await A().client.rpc('staff_member_list');
    if(error)throw error;
    if(myGeneration!==generation||!currentRoute())return;
    rows=Array.isArray(data)?data:[];render();
  }catch(e){
    if(list)list.innerHTML=`<div class="empty danger">Nie udało się pobrać użytkowników: ${esc(e?.message||e)}</div>`;
  }finally{loading=false}
}
function canStaffManage(row){
  if(!row)return false;
  const self=String(row.id)===String(A().profile?.id);
  if(self||row.role==='admin')return false;
  return isAdmin()||row.role==='user';
}
function render(){
  const root=$('[data-admin-users-root]');if(!root||!currentRoute())return;
  const me=A().profile?.id;
  const filtered=rows.filter(u=>!query||String(u.username||'').toLowerCase().includes(query));
  const summary=root.querySelector('[data-admin-users-summary]');
  if(summary)summary.innerHTML=`<span>Wszyscy <b>${rows.length}</b></span><span>Moderatorzy <b>${rows.filter(x=>x.role==='moderator').length}</b></span><span>Zablokowani <b>${rows.filter(x=>x.banned_at).length}</b></span>`;
  const list=root.querySelector('[data-admin-users-list]');if(!list)return;
  if(!filtered.length){list.innerHTML='<div class="empty">Brak użytkowników dla tego wyszukiwania.</div>';return}
  list.innerHTML=filtered.map(u=>{
    const self=String(u.id)===String(me),actions=[];
    if(canStaffManage(u)){
      if(u.community_access)actions.push(`<button type="button" data-admin-user-action="reject" data-id="${esc(u.id)}">Odbierz dostęp</button>`);
      else if(!u.banned_at)actions.push(`<button type="button" data-admin-user-action="approve" data-id="${esc(u.id)}">✓ Dopuść</button>`);
      if(isAdmin()&&u.role==='user')actions.push(`<button type="button" data-admin-user-action="promote" data-id="${esc(u.id)}">★ Nadaj moderatora</button>`);
      if(isAdmin()&&u.role==='moderator')actions.push(`<button type="button" data-admin-user-action="demote" data-id="${esc(u.id)}">Usuń moderatora</button>`);
      if(u.banned_at)actions.push(`<button type="button" data-admin-user-action="unban" data-id="${esc(u.id)}">↩ Odblokuj</button>`);
      else actions.push(`<button type="button" class="danger-button" data-admin-user-action="ban" data-id="${esc(u.id)}">⛔ Zablokuj</button>`);
      if(isAdmin()&&u.role==='user')actions.push(`<button type="button" class="danger-button" data-admin-user-action="delete" data-id="${esc(u.id)}">🗑 Usuń konto</button>`);
    }
    return `<article class="admin-user-card ${u.banned_at?'is-banned':''}"><div class="admin-user-main"><div><b>${esc(u.username||'Użytkownik')}</b> ${badge(u.role)} ${self?'<span class="admin-user-self">TY</span>':''}</div><small>Konto: ${esc(fmt(u.created_at))}</small><div class="admin-user-state"><span>${u.community_access?'Dostęp: TAK':'Dostęp: NIE'}</span>${u.banned_at?'<span class="danger">ZABLOKOWANY</span>':''}</div></div>${actions.length?`<div class="admin-user-actions">${actions.join('')}</div>`:'<small>Brak dostępnych akcji.</small>'}</article>`;
  }).join('');
}
async function act(button){
  if(!currentRoute())return;
  const id=button.dataset.id,action=button.dataset.adminUserAction,row=rows.find(x=>String(x.id)===String(id));
  if(!row||!canStaffManage(row))return;
  if(['promote','demote','delete'].includes(action)&&!isAdmin())return;
  const confirmations={
    approve:`Dopuścić ${row.username} do aplikacji?`,
    reject:`Odebrać ${row.username} dostęp?`,
    promote:`Nadać ${row.username} rolę MODERATOR?`,
    demote:`Odebrać ${row.username} rolę moderatora?`,
    ban:`Zablokować konto ${row.username}?`,
    unban:`Odblokować konto ${row.username}?`
  };
  if(action==='delete'){
    if(row.role!=='user')return alert('Moderator musi najpierw zostać zdegradowany do USER.');
    if(!confirm(`TRWAŁE USUNIĘCIE KONTA\n\nUżytkownik: ${row.username}\n\nOperacji nie da się cofnąć. Kontynuować?`))return;
    if(prompt(`Aby potwierdzić trwałe usunięcie konta ${row.username}, wpisz dokładnie:\n\nUSUŃ NA STAŁE`)!=='USUŃ NA STAŁE')return alert('Usuwanie anulowane.');
  }else if(!confirm(confirmations[action]||'Wykonać akcję?'))return;
  button.disabled=true;
  try{
    let result;
    if(action==='approve')result=await A().client.rpc('staff_review_access',{target_uid:id,decision:'approve'});
    if(action==='reject')result=await A().client.rpc('staff_review_access',{target_uid:id,decision:'reject'});
    if(action==='promote')result=await A().client.rpc('admin_set_role',{target_uid:id,next_role:'moderator'});
    if(action==='demote')result=await A().client.rpc('admin_set_role',{target_uid:id,next_role:'user'});
    if(action==='ban')result=await A().client.rpc('staff_set_ban',{target_uid:id,should_ban:true});
    if(action==='unban')result=await A().client.rpc('staff_set_ban',{target_uid:id,should_ban:false});
    if(action==='delete')result=await A().client.rpc('admin_delete_user',{target_uid:id});
    if(result?.error)throw result.error;
    if(action==='delete'&&result?.data!==true)throw new Error('Serwer nie potwierdził usunięcia konta.');
    await load();
  }catch(e){alert(e?.message||'Nie udało się wykonać operacji.');button.disabled=false}
}
let scheduled=false;
function scheduleMount(){if(scheduled)return;scheduled=true;setTimeout(()=>{scheduled=false;mount()},40)}
const observer=new MutationObserver(scheduleMount);
const app=$('#app');if(app)observer.observe(app,{childList:true,subtree:true});
window.addEventListener('hashchange',scheduleMount);
window.addEventListener('tenis-auth',scheduleMount);
scheduleMount();
})();