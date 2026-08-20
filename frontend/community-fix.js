/* Tenis AI v6.5.1 — make profile editing and adding coupons obvious on mobile */
(() => {
  const $=s=>document.querySelector(s);

  function closeAccount(){
    const close=$('#account-modal-close');
    if(close) close.click();
    else {
      const ov=$('#account-overlay');
      if(ov) ov.hidden=true;
      document.body.style.overflow='';
    }
  }

  function openCouponComposer(){
    closeAccount();
    const tab=$('.main-tabs button[data-view="coupons"]');
    if(tab) tab.click();
    setTimeout(()=>{
      const add=$('.shared-add');
      if(add){
        add.open=true;
        add.classList.add('v651-highlight');
        add.scrollIntoView({behavior:'smooth',block:'start'});
        setTimeout(()=>add.classList.remove('v651-highlight'),1800);
      }
    },220);
  }

  window.tenisAICommunityUX={openCouponComposer};

  function improveProfileEditor(){
    const editor=$('.profile-editor');
    if(!editor || editor.dataset.v651==='1') return;
    editor.dataset.v651='1';

    const bio=$('#profile-bio');
    const save=$('#profile-save');
    const msg=$('#profile-editor-msg');
    if(bio){
      const counter=document.createElement('div');
      counter.className='profile-char-counter';
      const updateCounter=()=>counter.textContent=`${bio.value.length}/300 znaków`;
      updateCounter();
      bio.closest('label')?.insertAdjacentElement('afterend',counter);
      bio.addEventListener('input',updateCounter);
    }

    if(save){
      save.textContent='💾 Zapisz profil';
      const bioLabel=bio?.closest('label');
      const counter=editor.querySelector('.profile-char-counter');
      if(counter) counter.insertAdjacentElement('afterend',save);
      else if(bioLabel) bioLabel.insertAdjacentElement('afterend',save);
      if(msg) save.insertAdjacentElement('afterend',msg);
    }

    const publicBtn=$('#account-public-profile');
    if(publicBtn && !$('#account-add-coupon')){
      const add=document.createElement('button');
      add.id='account-add-coupon';
      add.className='account-add-coupon';
      add.type='button';
      add.textContent='🧾 Dodaj kupon';
      add.onclick=openCouponComposer;
      publicBtn.insertAdjacentElement('beforebegin',add);
    }
  }

  function autoOpenCouponForm(){
    const active=$('.main-tabs button.active');
    if(active?.dataset.view!=='coupons') return;
    setTimeout(()=>{
      const add=$('.shared-add');
      const cards=document.querySelectorAll('.shared-card');
      if(add && cards.length===0) add.open=true;
    },250);
  }

  document.addEventListener('click',e=>{
    if(e.target.closest('#account-button')) setTimeout(improveProfileEditor,100);
    if(e.target.closest('.main-tabs button[data-view="coupons"]')) autoOpenCouponForm();
  });

  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(improveProfileEditor,120));

  const observer=new MutationObserver(()=>{
    if($('.profile-editor')) improveProfileEditor();
  });
  observer.observe(document.body,{childList:true,subtree:true});
})();
