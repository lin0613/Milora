(function(){
  'use strict';
  const mobileShell=new URLSearchParams(location.search).get('_mobile')==='1';
  if(mobileShell)document.documentElement.classList.add('mobileShellProject');
  const path=(location.pathname||'').split('/').filter(Boolean);
  const projectIndex=path.indexOf('_projects');
  const gameId=document.documentElement.dataset.gameId||(projectIndex>=0?(path[projectIndex+1]||''):'');
  const gameAliases={'wuthering-waves':'wuwa'};
  const canonicalGameId=value=>gameAliases[value]||value;
  const hydrateSharedGameUi=async()=>{
    try{
      const response=await fetch('/game-manifest.json',{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const registry=await response.json();
      const projects=new Map((Array.isArray(registry.projects)?registry.projects:[]).map(project=>[project.id,project]));
      document.querySelectorAll('.gameNavItem[data-game]').forEach(item=>{
        const project=projects.get(canonicalGameId(item.dataset.game||''));
        const frame=item.querySelector('.gameNavIcon');
        if(!project||!frame||!project.iconEndpoint)return;
        const image=document.createElement('img');
        image.src=project.iconEndpoint;
        image.alt='';
        image.width=38;
        image.height=38;
        image.decoding='async';
        image.loading='eager';
        image.referrerPolicy='no-referrer';
        image.style.cssText='display:block;width:100%;height:100%;object-fit:cover;border-radius:inherit';
        frame.replaceChildren(image);
        frame.hidden=false;
        const title=item.querySelector('.gameNavText strong');
        const subtitle=item.querySelector('.gameNavText small');
        if(title)title.textContent=project.name||title.textContent;
        if(subtitle)subtitle.textContent=project.subtitle||subtitle.textContent;
      });
      const accountNote=document.querySelector('[data-shared-account-note]');
      const sharedNote=String(registry.sharedUi?.accountNote||'').trim();
      if(accountNote&&sharedNote)accountNote.textContent=sharedNote;
    }catch(error){
      console.warn('Shared game UI hydration failed',error);
    }
    if(['wuwa','hsr','genshin','zzz','nte'].includes(gameId))try{
      const response=await fetch(`/api/games/${encodeURIComponent(gameId)}/live-state`,{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const payload=await response.json();
      const version=String(payload.catalog_version||'').trim();
      const label=document.getElementById('gameCatalogVersion');
      if(label&&version)label.textContent=`目前更新到${version}版本｜有bug請回報`;
    }catch(error){
      console.warn('Game catalog version hydration failed',error);
    }
  };
  hydrateSharedGameUi();
  const hub={
    gameId,
    embedded:window.parent!==window,
    openAdminSync:function(){
      if(window.parent!==window){
        window.parent.postMessage({type:'achievement-hub:navigate',page:'admin',tab:'sync',gameId},location.origin);
        return true;
      }
      location.href='/#admin';
      return false;
    }
  };
  window.AchievementHub=Object.freeze(hub);
  const hideLegacyMessageEntries=()=>{
    for(const id of ['announcementBtn','notificationBtn']){
      const node=document.getElementById(id);
      if(node){node.hidden=true;node.style.display='none';node.setAttribute('aria-hidden','true')}
    }
  };
  hideLegacyMessageEntries();
  document.addEventListener('DOMContentLoaded',hideLegacyMessageEntries,{once:true});
  if(!['wuwa','hsr','genshin','zzz','nte'].includes(gameId))return;
  const button=document.getElementById('syncBtn');
  if(!button)return;
  const replacement=button.cloneNode(true);
  button.replaceWith(replacement);
  replacement.addEventListener('click',async()=>{
    replacement.disabled=true;
    const original=replacement.textContent;
    replacement.textContent='建立預覽中…';
    try{
      const response=await fetch(`/api/games/${encodeURIComponent(gameId)}/admin/official-achievements/preview`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:'{}',credentials:'same-origin',cache:'no-store'
      });
      const payload=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(payload.detail?.message||payload.detail||payload.message||`HTTP ${response.status}`);
      const summary=payload.summary||{};
      alert(`差異預覽已建立。\n新增：${Number(summary.added||0)}\n修改：${Number(summary.modified||0)}\n疑似刪除：${Number(summary.removed||0)}\n待確認：${Number(summary.needs_review||0)}\n\n正式資料尚未變更，請到管理後台的「同步官方列表」逐項確認。`);
      hub.openAdminSync();
    }catch(error){
      alert(`建立同步預覽失敗：${error.message}`);
    }finally{
      replacement.disabled=false;
      replacement.textContent=original;
    }
  });
})();
