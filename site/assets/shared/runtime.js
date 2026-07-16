(function(){
  'use strict';
  const mobileShell=new URLSearchParams(location.search).get('_mobile')==='1';
  if(mobileShell)document.documentElement.classList.add('mobileShellProject');
  const path=(location.pathname||'').split('/').filter(Boolean);
  const projectIndex=path.indexOf('_projects');
  const gameId=projectIndex>=0?(path[projectIndex+1]||''):'';
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
  if(!['wuwa','hsr','genshin','zzz'].includes(gameId))return;
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
