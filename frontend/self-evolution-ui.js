/* Admin-only, read-only Self Evolution SHADOW status from public GitHub Actions metadata.
 * No model inference, no betting, and no claim of learning from a successful CI test.
 * GitHub artifact contents are NOT accessible without authorized credentials.
 */
(()=>{
'use strict';
const REPO='Abeel87/tenis-ai';
const API='https://api.github.com/repos/'+REPO;
const URL='https://github.com/'+REPO+'/actions/workflows/';
const RESEARCH='self-evolution-shadow.yml';
const QUOTES='superbet-market-refresh.yml';
const CACHE_MS=60000;
let cached=null,inflight=null,updated=0,error=null;

const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const admin=()=>window.TenisAccount?.authenticated===true&&window.TenisAccount.role==='admin';
const date=x=>{
  const d=new Date(x||'');
  return Number.isFinite(d.getTime())
    ?d.toLocaleString('pl-PL',{timeZone:'Europe/Warsaw',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})
    :'N/D';
};
function panel(){
  return '<section class="panel" id="self-evolution-admin"><h2>Self Evolution <span class="badge">SHADOW</span></h2><p class="muted">Sprawdzam rzeczywiste uruchomienia badawcze GitHuba…</p></section>';
}
function summary(run){
  if(!run)return {label:'Niepotwierdzony',note:'Brak uruchomienia na main',tone:'warn'};
  if(run.status!=='completed')return {label:'W trakcie / oczekuje',note:'Raport jeszcze niedostępny',tone:'warn'};
  if(run.conclusion!=='success')return {label:'Błąd lub anulowanie',note:'Nie ma potwierdzonego raportu',tone:'bad'};
  return {label:'Workflow zakończony',note:'Sprawdź odrębnie artefakt i wyniki eksperymentu',tone:'ok'};
}
function pick(runs){
  return (Array.isArray(runs)?runs:[]).find(
    r=>r&&r.head_branch==='main'&&['schedule','workflow_dispatch'].includes(r.event)
  )||null;
}
async function getJson(path){
  const response=await fetch(API+path,{headers:{Accept:'application/vnd.github+json'}});
  if(!response.ok)throw new Error('GitHub API HTTP '+response.status);
  return response.json();
}
async function getArtifactInfo(run,names){
  if(!run||run.status!=='completed'||run.conclusion!=='success')return [];
  const body=await getJson('/actions/runs/'+encodeURIComponent(run.id)+'/artifacts?per_page=40');
  return (Array.isArray(body.artifacts)?body.artifacts:[])
    .filter(a=>a&&!a.expired&&names.some(prefix=>String(a.name||'').startsWith(prefix)))
    .map(a=>({name:String(a.name),created:a.created_at||null}));
}
async function read(){
  const [training,market]=await Promise.all([
    getJson('/actions/workflows/'+RESEARCH+'/runs?branch=main&per_page=10'),
    getJson('/actions/workflows/'+QUOTES+'/runs?branch=main&per_page=10')
  ]);
  const research=pick(training.workflow_runs),quotes=pick(market.workflow_runs);
  const [researchArtifacts,quoteArtifacts]=await Promise.all([
    getArtifactInfo(research,['self-evolution-shadow-','self-evolution-memory']),
    getArtifactInfo(quotes,['superbet-quote-evidence-'])
  ]);
  return {research,quotes,researchArtifacts,quoteArtifacts};
}
function runPanel(label,run,artifactName,artifacts,workflow){
  const status=summary(run),hasArtifact=artifacts.some(a=>a.name.startsWith(artifactName));
  return '<div class="system-item"><b>'+esc(label)+'</b>'
    +'<p><span class="badge '+status.tone+'">'+esc(status.label)+'</span></p>'
    +'<small>'+esc(status.note)+'</small>'
    +'<small>Ostatnie uruchomienie: '+esc(date(run?.created_at))+'</small>'
    +'<small>Archiwum: '+(hasArtifact?'Zapisano artefakt uruchomienia':'Brak potwierdzonego artefaktu')+'</small>'
    +(run?.html_url?'<a target="_blank" rel="noopener noreferrer" href="'+esc(run.html_url)+'">Raport GitHub Actions ↗</a>':'<a target="_blank" rel="noopener noreferrer" href="'+URL+workflow+'">Historia uruchomień ↗</a>')
    +'</div>';
}
function paint(){
  const root=document.querySelector('#self-evolution-admin');
  if(!root||!admin())return;
  const data=cached;
  root.innerHTML='<div class="section-title"><h2>Self Evolution · SHADOW</h2><span class="badge">TYLKO BADANIA</span></div>'
    +'<p class="muted">Status czytany na żywo z GitHub Actions. Ukończony workflow i zapisany artefakt nie oznaczają, że strategia poprawiła skuteczność.</p>'
    +'<div class="toolbar"><button type="button" data-evolution-refresh>↻ Sprawdź ponownie</button>'
    +'<a class="button" href="'+URL+RESEARCH+'" target="_blank" rel="noopener noreferrer">Self Evolution w GitHub ↗</a></div>'
    +(error?'<p class="footer-note danger" role="alert">Status N/D — '+esc(error)+'. Poprzedni odczyt może być nieaktualny.</p>':'')
    +(data?'<div class="system-grid">'
      +runPanel('Trening / AI Memory',data.research,'self-evolution-memory',data.researchArtifacts,RESEARCH)
      +runPanel('Archiwum kursów Superbet',data.quotes,'superbet-quote-evidence-',data.quoteArtifacts,QUOTES)
      +'<div class="system-item"><b>Czy AI się poprawiło?</b><p class="badge warn">NIEPOTWIERDZONE</p><small>Nowy Champion: N/D</small><small>Wynik Brier: N/D</small><small>Liczba ukończonych testów prospektywnych: N/D</small><small>Weryfikacja wymaga odczytu właściwego raportu i wystarczających późniejszych meczów.</small></div>'
      +'</div>':'<p class="muted">Nie można potwierdzić treningu na podstawie danych dostępnych w tym panelu.</p>')
    +'<p class="footer-note">Dane eksperymentów pozostają w artefaktach Actions. Panel nie czyta prywatnych plików, nie wymaga tokena GitHub, nie ocenia ROI i nie steruje PROD, PLAYABLE ani Symfonią.</p>';
  root.querySelector('[data-evolution-refresh]').onclick=()=>load(true);
}
function load(force){
  if(!admin()||!document.querySelector('#self-evolution-admin'))return;
  if(inflight)return;
  if(!force&&cached&&Date.now()-updated<CACHE_MS){paint();return;}
  inflight=read().then(data=>{cached=data;error=null;updated=Date.now();})
    .catch(e=>{error=e.message||'Nieznany błąd odczytu GitHub';})
    .finally(()=>{inflight=null;paint();});
  if(!cached)paint();
}
window.TenisSelfEvolutionUI={panel,mount:()=>load(false)};
})();
