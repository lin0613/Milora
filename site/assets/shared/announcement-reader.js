(()=>{
 'use strict';
 const layoutParams=new URLSearchParams(location.search);
 const mobileViewport=matchMedia('(max-width:760px)');
 const isTopLevel=window.parent===window;
 function syncLayoutMode(){
  const mobile=layoutParams.get('_mobile')==='1'||(isTopLevel&&mobileViewport.matches);
  document.documentElement.classList.toggle('hubMobileLayout',mobile);
 }
 syncLayoutMode();
 if(isTopLevel)mobileViewport.addEventListener?.('change',syncLayoutMode);
 const states=new WeakMap();
 const levelLabels={info:'一般',success:'成功',warning:'提醒',danger:'重要',update:'更新'};
 const safe=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
 const itemId=item=>String(item?.id??'');
 const itemLevel=item=>String(item?.level||item?.kind||'info');
 const itemStamp=item=>Number(item?.updated_at||item?.created_at||0);
 function defaultDate(value){if(!value)return '—';const date=new Date(Number(value)*1000);return Number.isNaN(date.getTime())?'—':date.toLocaleString('zh-TW',{hour12:false})}
 function detailHtml(item,options,dateFor){
  const actions=typeof options.actions==='function'?String(options.actions(item)||''):'';
  return `<div class="announcementReaderDetailHeader"><h3>${safe(item.title||'未命名公告')}</h3><div class="announcementReaderDetailMeta"><span class="announcementReaderLevel ${safe(itemLevel(item))}">${safe(levelLabels[itemLevel(item)]||'一般')}</span><time>${safe(dateFor(item))}</time></div></div><div class="announcementReaderBody"><p>${safe(item.body||'')}</p></div>${actions?`<div class="announcementReaderActions">${actions}</div>`:''}`;
 }
 function select(root,id){
  const state=states.get(root);
  if(!state)return '';
  const selected=state.items.find(item=>itemId(item)===String(id))||state.items[0]||null;
  if(!selected)return '';
  const selectedId=itemId(selected);
  if(state.selectedId===selectedId)return selectedId;
  const previousButton=state.buttons.get(state.selectedId);
  if(previousButton){previousButton.classList.remove('active');previousButton.setAttribute('aria-pressed','false')}
  const selectedButton=state.buttons.get(selectedId);
  if(selectedButton){selectedButton.classList.add('active');selectedButton.setAttribute('aria-pressed','true')}
  state.selectedId=selectedId;
  root.dataset.selectedAnnouncementId=selectedId;
  if(state.detail){state.detail.innerHTML=detailHtml(selected,state.options,state.dateFor);state.detail.scrollTop=0}
  return selectedId;
 }
 function selectFromEvent(root,event,activate=false){
  const button=event.target.closest?.('[data-announcement-reader-id]');
  if(!button||!root.contains(button))return;
  const selectedId=select(root,button.dataset.announcementReaderId||'');
  if(activate&&selectedId){const state=states.get(root),selected=state?.items.find(item=>itemId(item)===selectedId);if(selected&&typeof state.options.onSelect==='function')state.options.onSelect(selected,event)}
 }
 function render(root,rows,options={}){
  if(!root)return '';
  const items=Array.isArray(rows)?rows:[];
  const preferred=String(options.selectedId??root.dataset.selectedAnnouncementId??'');
  const selected=items.find(item=>itemId(item)===preferred)||items[0]||null;
  const formatDate=typeof options.formatDate==='function'?options.formatDate:defaultDate;
  const dateFor=item=>formatDate(itemStamp(item),item);
  const state={items,options,dateFor,buttons:new Map(),detail:null,selectedId:selected?itemId(selected):''};
  states.set(root,state);
  root.dataset.selectedAnnouncementId=selected?itemId(selected):'';
  if(!items.length){root.innerHTML=`<div class="announcementReaderEmpty">${safe(options.emptyText||'目前沒有公告。')}</div>`;return ''}
  root.innerHTML=`<div class="announcementReader"><nav class="announcementReaderList" aria-label="公告清單">${items.map(item=>{const id=itemId(item),level=itemLevel(item),pinned=Boolean(Number(item.pinned||0)),active=id===itemId(selected),unread=options.showUnread&&!item.is_read;return `<button class="announcementReaderItem ${active?'active':''} ${unread?'unread':''}" type="button" data-announcement-reader-id="${safe(id)}" aria-pressed="${active?'true':'false'}"><span class="announcementReaderItemTitle">${pinned?'<span class="announcementReaderPinIcon" aria-label="置頂" title="置頂">&#128204;</span>':''}<span>${safe(item.title||'未命名公告')}</span></span><span class="announcementReaderItemMeta"><span class="announcementReaderItemLevel ${safe(level)}">${safe(levelLabels[level]||'一般')}</span><time>${safe(dateFor(item))}</time></span></button>`}).join('')}</nav><article class="announcementReaderDetail">${detailHtml(selected,options,dateFor)}</article></div>`;
  state.detail=root.querySelector('.announcementReaderDetail');
  root.querySelectorAll('[data-announcement-reader-id]').forEach(button=>state.buttons.set(button.dataset.announcementReaderId||'',button));
  if(root.dataset.announcementReaderBound!=='1'){
   root.dataset.announcementReaderBound='1';
   root.addEventListener('pointerdown',event=>{if(event.button===0&&(!event.pointerType||event.pointerType==='mouse'))selectFromEvent(root,event,false)});
   root.addEventListener('click',event=>selectFromEvent(root,event,true));
  }
  return itemId(selected);
 }
 window.AnnouncementReader={render,select,selectedId:root=>String(root?.dataset?.selectedAnnouncementId||'')};
})();
