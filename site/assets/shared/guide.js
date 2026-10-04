(function(){
 'use strict';

 const $=id=>document.getElementById(id);
 const guideUi=value=>window.MiloraGuideUI?.translate(value)||value;
 const query=new URLSearchParams(location.search);
 const pathParts=location.pathname.split('/').filter(Boolean);
 const gameIds=['wuwa','hsr','genshin','zzz','nte'];
 const pathGame=gameIds.includes(pathParts[0])?pathParts[0]:'';
 const pathAchievement=pathGame?(pathParts[1]||''):'';
 const gameId=String(query.get('game')||pathGame||'').trim().toLowerCase();
 const achievementId=String(query.get('achievement')||pathAchievement||'').trim();
 const state={payload:null,user:null,editingSubmissionId:'',activePendingId:'',savedRange:null,busy:false,editorOpen:false,draftTimer:null,draftQueue:Promise.resolve(),draftLastSavedHtml:'',pendingUploads:0};
 let guideEditor;
 const editorSurface=()=>document.querySelector('#guideEditorPanel .sun-editor-editable');
 const statusCopy={
  pending:['等待審查','投稿已送出，管理員核准前不會公開。'],
  approved:['已通過審查','這個版本已通過審查。'],
  rejected:['需要修改','管理員已退回這份投稿，你可以修改後再次送出。']
 };

 function esc(value){return String(value??'').replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]))}
 function formatTime(stamp){if(!Number(stamp))return '';return new Intl.DateTimeFormat('zh-TW',{dateStyle:'medium',timeStyle:'short'}).format(new Date(Number(stamp)*1000))}
 async function apiJson(path,options={}){
  const config={credentials:'same-origin',cache:'no-store',...options};
  config.headers={'Content-Type':'application/json',...(options.headers||{})};
  const response=await fetch(path,config);
  let value=null;try{value=await response.json()}catch{}
  if(!response.ok){const detail=value?.detail;const validation=Array.isArray(detail)?detail.map(item=>item.msg).filter(Boolean).join('；'):'';throw new Error(typeof detail==='string'?detail:(validation||detail?.message||value?.message||`請求失敗（${response.status}）`))}
  return value||{};
 }
 function setNotice(message,type=''){$('guideNotice').textContent=message;$('guideNotice').className=`guideNotice${type?` ${type}`:''}`;$('guideNotice').hidden=!message}
 function openAccount(){
  if(window.parent!==window){window.parent.postMessage({type:'achievement-hub-open-account',message:'請先登入後再投稿攻略。',returnUrl:`/${gameId}/${achievementId}`},location.origin);return}
  location.href=`/?return=${encodeURIComponent(`/${gameId}/${achievementId}`)}#account`;
 }
 function contentForEditing(){
  const own=state.payload?.my_submission;
  if(own&&['pending','rejected'].includes(own.status))return own.content_html||'';
  return state.payload?.published?.content_html||'<p><br></p>';
 }
 const draftUrl=()=>`/api/games/${encodeURIComponent(gameId)}/achievements/${encodeURIComponent(achievementId)}/guide/draft`;
 function draftEnabled(){return state.editorOpen&&!state.editingSubmissionId&&Boolean(state.user)}
 function draftStatus(message){$('guideDraftStatus').textContent=message}
 function updateWordCount(){
  const content=editorSurface()?.textContent||'';
  $('guideWordCount').textContent=`字數：${Array.from(content.replace(/[\s\u200b-\u200d\ufeff]/g,'')).length}`;
 }
 function scheduleDraftSave(){
  if(!draftEnabled())return;
  clearTimeout(state.draftTimer);draftStatus('草稿尚未儲存');
  state.draftTimer=setTimeout(()=>{saveDraftNow().catch(error=>{draftStatus('草稿儲存失敗');setNotice(`草稿儲存失敗：${error.message}`,'error')})},800);
 }
 function saveDraftNow(){
  clearTimeout(state.draftTimer);state.draftTimer=null;
  if(!draftEnabled())return state.draftQueue;
  const content_html=editorHtml();
  if(content_html===state.draftLastSavedHtml)return state.draftQueue;
  draftStatus('正在儲存草稿…');
  state.draftQueue=state.draftQueue.catch(()=>{}).then(async()=>{
   const result=await apiJson(draftUrl(),{method:'PUT',body:JSON.stringify({content_html})});
   if(state.payload)state.payload.guide_draft=result.guide_draft;
   state.draftLastSavedHtml=content_html;
   if(state.editorOpen&&editorHtml()===content_html)draftStatus('草稿已儲存');
  });
  return state.draftQueue;
 }
 function providerText(submission){return submission?.provider?`提供者：${submission.provider}`:''}
 function setEditorContent(html,provider=''){
  state.savedRange=null;
  guideEditor.$.html.set(html||'<p><br></p>');
  hydrateVideos(editorSurface());
  guideEditor.$.history.reset();guideEditor.$.history.push(false);
  updateWordCount();
  $('guideEditorProvider').textContent=provider;
 }
 function hydrateSpoilers(root){
  root.querySelectorAll('.spoiler,.guideSpoiler').forEach(node=>{
   node.classList.remove('guideSpoiler');node.classList.add('spoiler');
   node.classList.remove('revealed');
   node.setAttribute('tabindex','0');node.setAttribute('role','button');
   node.setAttribute('aria-label','點擊顯示或隱藏反黑內容');node.setAttribute('aria-pressed','false');
  });
 }
 function videoEmbedUrl(value){
  try{
   const url=new URL(value,location.origin),host=url.hostname.toLowerCase();
   if(host==='youtu.be')return `https://www.youtube-nocookie.com/embed/${url.pathname.split('/').filter(Boolean)[0]||''}`;
   if(host.endsWith('youtube.com')){
    let id=url.searchParams.get('v')||'';
    const match=url.pathname.match(/\/(?:embed|shorts)\/([^/]+)/);if(!id&&match)id=match[1];
    return id?`https://www.youtube-nocookie.com/embed/${id}`:'';
   }
   const match=url.pathname.match(/\/video\/(BV[A-Za-z0-9]+)/i);
   if(host.endsWith('bilibili.com')&&match)return `https://player.bilibili.com/player.html?bvid=${match[1]}&page=1`;
  }catch{}
  return '';
 }
 function canonicalVideoUrl(value){
  try{
   const url=new URL(value,location.origin),host=url.hostname.toLowerCase();
   if(['youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be'].includes(host)){
    const id=host==='youtu.be'?url.pathname.split('/').filter(Boolean)[0]:(url.searchParams.get('v')||url.pathname.match(/^\/(?:embed|shorts)\/([^/]+)/)?.[1]);
    if(/^[A-Za-z0-9_-]{6,20}$/.test(id||''))return `https://www.youtube.com/watch?v=${id}`;
   }
   if(['bilibili.com','www.bilibili.com','m.bilibili.com','player.bilibili.com'].includes(host)){
    const id=url.pathname.match(/^\/video\/(BV[A-Za-z0-9]{8,20})/i)?.[1]||url.searchParams.get('bvid');
    if(/^BV[A-Za-z0-9]{8,20}$/i.test(id||''))return `https://www.bilibili.com/video/${id}`;
   }
  }catch{}
  return '';
 }
 function hydrateVideos(root){
  root.querySelectorAll('figure.guideVideo').forEach(figure=>{
   figure.querySelector('.guideVideoEmbed')?.remove();
   const src=videoEmbedUrl(figure.dataset.guideVideoUrl||'');if(!src)return;
   const wrap=document.createElement('div');wrap.className='guideVideoEmbed';wrap.contentEditable='false';
   const frame=document.createElement('iframe');frame.src=src;frame.title='攻略影片';frame.loading='lazy';frame.allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';frame.allowFullscreen=true;
   wrap.append(frame);figure.insertBefore(wrap,figure.firstChild);
  });
 }
 function renderPublished(){
  const published=state.payload?.published;
  $('guideReadingSurface').hidden=!published;$('guideEmptyState').hidden=Boolean(published);
  if(!published)return;
  $('guideProviderLine').textContent=providerText(published);
  $('guidePublishedAt').textContent=published.reviewed_at?`發布於 ${formatTime(published.reviewed_at)}`:'';
  $('guidePublishedContent').innerHTML=published.content_html||'';
  hydrateSpoilers($('guidePublishedContent'));hydrateVideos($('guidePublishedContent'));
 }
 function renderOwnSubmission(){
  const submission=state.payload?.my_submission;
  $('guideSubmissionState').hidden=!submission;
  if(!submission)return;
  const copy=statusCopy[submission.status]||[submission.status_label||submission.status,''];
  $('guideSubmissionStateTitle').textContent=copy[0];
  $('guideSubmissionStateMessage').textContent=submission.status==='rejected'&&submission.review_note?`審查備註：${submission.review_note}`:copy[1];
  $('guideSubmissionStateBadge').textContent=copy[0];$('guideSubmissionStateBadge').className=`guideStatusBadge ${submission.status}`;
 }
 function renderPendingList(){
  const isAdmin=state.user?.role==='admin',pending=state.payload?.admin_pending||[];
  $('guideAdminReview').hidden=!isAdmin;
  if(!isAdmin){if(!state.editorOpen)$('guideEditorSection').hidden=true;return}
  $('guidePendingList').innerHTML=pending.length?pending.map(item=>`<button class="guidePendingButton${item.id===state.activePendingId?' active':''}" data-submission-id="${esc(item.id)}" type="button"><strong>${esc(item.provider||'未命名使用者')}</strong><span>${esc(formatTime(item.updated_at))}</span></button>`).join(''):'<p class="guideFieldHint">目前沒有等待審查的投稿。</p>';
  if(!pending.some(item=>item.id===state.activePendingId)){$('guideReviewDetail').hidden=true;state.activePendingId=''}
  $('guideEditorPanel').hidden=!state.editorOpen;
  $('guideEditorWorkspace').classList.toggle('queueOnly',!state.editorOpen);
  $('guideEditorSection').hidden=!state.editorOpen&&!pending.length;
 }
 function renderPage(){
  const achievement=state.payload.achievement;
  document.title=`${achievement.name}攻略｜遊戲成就紀錄器`;
  $('guideAchievementName').textContent=achievement.name;
  $('guideAchievementCondition').textContent=achievement.condition||'未提供成就說明';
  if(achievement.condition)delete $('guideAchievementCondition').dataset.guideEmpty;else $('guideAchievementCondition').dataset.guideEmpty='true';
  const meta=[achievement.game_name,achievement.category,achievement.version?`版本 ${achievement.version}`:'',`成就 ID ${achievement.id}`].filter(Boolean);
  $('guideAchievementMeta').innerHTML=meta.map(value=>`<span>${esc(value)}</span>`).join('');
  if(window.parent!==window)window.parent.postMessage({type:'achievement-hub-guide-meta',title:`${achievement.name}攻略｜遊戲成就紀錄器`,description:`${achievement.game_name}成就「${achievement.name}」的攻略與投稿內容。`},location.origin);
  $('guideAchievementHeader').hidden=false;state.user=state.payload.user||null;
  $('guideEditButton').textContent=state.user?'編輯攻略':'登入後編輯攻略';
  $('guideEmptyEditButton').textContent=state.user?'編輯攻略':'登入後編輯攻略';
  renderPublished();renderOwnSubmission();renderPendingList();setNotice('');
  $('guidePage').setAttribute('aria-busy','false');
 }
 async function loadGuide(){
  if(!gameIds.includes(gameId)||!/^[A-Za-z0-9_-]+$/.test(achievementId)){setNotice('攻略網址不正確。','error');return}
  setNotice('正在載入攻略……');
  try{state.payload=await apiJson(`/api/games/${encodeURIComponent(gameId)}/achievements/${encodeURIComponent(achievementId)}/guide`);renderPage()}
  catch(error){setNotice(error.message,'error');$('guidePage').setAttribute('aria-busy','false')}
 }
 function openEditor(){
  if(!state.payload?.authenticated)return openAccount();
  state.editingSubmissionId='';state.activePendingId='';state.editorOpen=true;
  $('guideEditorTitle').textContent='編輯攻略';$('guideSubmitButton').textContent='送出審查';
  const original=contentForEditing(),draft=state.payload?.guide_draft;
  let content=original;
  if(draft?.content_html&&draft.content_html!==original){
   if(window.confirm(guideUi('找到上次未送出的攻略草稿。要恢復草稿嗎？\n按「取消」會捨棄舊草稿，使用目前已儲存的內容。')))content=draft.content_html;
   else{
    state.draftQueue=state.draftQueue.catch(()=>{}).then(()=>apiJson(draftUrl(),{method:'DELETE'}));
    state.draftQueue.then(()=>{if(state.payload)state.payload.guide_draft=null}).catch(error=>setNotice(`無法捨棄舊草稿：${error.message}`,'error'));
   }
  }
  setEditorContent(content,state.user?.username?`投稿者：${state.user.username}`:'');
  state.draftLastSavedHtml=editorHtml();draftStatus(draft&&content===draft.content_html?'已恢復上次草稿':'編輯內容會自動儲存為草稿');
  $('guideEditorPanel').hidden=false;$('guideEditorSection').hidden=false;$('guideReviewDetail').hidden=true;renderPendingList();
  requestAnimationFrame(()=>guideEditor.$.focusManager.focus());
 }
 async function closeEditor(skipSave=false){
  if(state.pendingUploads){setNotice('請等待圖片上傳完成，再關閉編輯器。','error');return}
  if(!skipSave&&draftEnabled()){
   try{await saveDraftNow()}catch(error){draftStatus('草稿儲存失敗');setNotice(`草稿儲存失敗，編輯器會保持開啟：${error.message}`,'error');return}
  }
  state.editorOpen=false;state.editingSubmissionId='';state.activePendingId='';$('guideEditorPanel').hidden=true;$('guideReviewDetail').hidden=true;renderPendingList();
 }
 function saveSelection(){
  const selection=window.getSelection();if(!selection?.rangeCount)return;
  const range=selection.getRangeAt(0);if(editorSurface()?.contains(range.commonAncestorContainer))state.savedRange=range.cloneRange();
  requestAnimationFrame(syncFontSizeLabel);
 }
 function syncFontSizeLabel(){
  const selection=window.getSelection(),node=selection?.anchorNode;
  if(!node||!editorSurface()?.contains(node))return;
  const element=node.nodeType===Node.ELEMENT_NODE?node:node.parentElement;
  const label=$('guideEditorPanel').querySelector('button.se-btn-tool-font-size .se-txt');
  if(element&&label)label.textContent=getComputedStyle(element).fontSize;
 }
 function restoreSelection(){
  if(!state.savedRange||!editorSurface()?.contains(state.savedRange.commonAncestorContainer))return false;
  const selection=window.getSelection();selection.removeAllRanges();selection.addRange(state.savedRange);return true;
 }
 function wrapSelection(styleOrClass,value){
  restoreSelection();const selection=window.getSelection();if(!selection?.rangeCount||selection.isCollapsed){alert(guideUi('請先選取要套用的文字。'));return}
  const range=selection.getRangeAt(0);if(!editorSurface()?.contains(range.commonAncestorContainer))return;
  const span=document.createElement('span');if(styleOrClass==='class')span.className=value;else span.style[styleOrClass]=value;
  span.append(range.extractContents());range.insertNode(span);range.selectNodeContents(span);selection.removeAllRanges();selection.addRange(range);saveSelection();guideEditor.$.history.push(false);scheduleDraftSave();
 }
 function toggleSpoiler(){
  restoreSelection();const selection=window.getSelection();if(!selection?.rangeCount){alert(guideUi('請先選取要套用暴雷的文字。'));return}
  const range=selection.getRangeAt(0),node=range.commonAncestorContainer,element=node.nodeType===Node.ELEMENT_NODE?node:node.parentElement;
  const spoiler=element?.closest?.('.spoiler,.guideSpoiler');
  if(spoiler&&editorSurface()?.contains(spoiler)){
   const children=[...spoiler.childNodes],first=children[0],last=children[children.length-1];
   spoiler.replaceWith(...children);
   if(first&&last){const unwrapped=document.createRange();unwrapped.setStartBefore(first);unwrapped.setEndAfter(last);selection.removeAllRanges();selection.addRange(unwrapped)}
   saveSelection();guideEditor.$.history.push(false);scheduleDraftSave();return;
  }
  if(selection.isCollapsed){alert(guideUi('請先選取要套用暴雷的文字。'));return}
  wrapSelection('class','spoiler');
 }
 function editorHtml(){
  const clone=editorSurface().cloneNode(true);clone.querySelectorAll('.guideVideoEmbed').forEach(node=>node.remove());
  clone.querySelectorAll('iframe[src],video[src]').forEach(node=>{
   const source=canonicalVideoUrl(node.getAttribute('src'));
   const wrapper=node.closest('.se-component')||node.closest('figure')||node;
   if(!source){wrapper.remove();return}
   const figure=document.createElement('figure');figure.className='guideVideo';figure.dataset.guideVideoUrl=source;
   const caption=wrapper.querySelector('figcaption')?.textContent?.trim();
   if(caption){const label=document.createElement('figcaption');label.textContent=caption;figure.append(label)}
   wrapper.replaceWith(figure);
  });
  clone.querySelectorAll('.guideUploadPending').forEach(node=>node.remove());
  clone.querySelectorAll('.spoiler,.guideSpoiler').forEach(node=>{node.classList.remove('guideSpoiler','revealed');node.classList.add('spoiler')});
  return clone.innerHTML;
 }
 async function saveSubmission(){
  if(state.pendingUploads){setNotice('請等待圖片上傳完成，再送出攻略。','error');return}
  if(state.busy)return;state.busy=true;$('guideSubmitButton').disabled=true;
  try{
   clearTimeout(state.draftTimer);await state.draftQueue.catch(()=>{});
   const content_html=editorHtml();
   if(state.editingSubmissionId){
    await apiJson(`/api/admin/guide-submissions/${encodeURIComponent(state.editingSubmissionId)}`,{method:'PUT',body:JSON.stringify({content_html})});
    setNotice('審查修訂已儲存。','success');
   }else{
    await apiJson(`/api/games/${encodeURIComponent(gameId)}/achievements/${encodeURIComponent(achievementId)}/guide/submissions`,{method:'POST',body:JSON.stringify({content_html})});
    setNotice('攻略已送出，投稿狀態為「等待審查」。','success');state.draftLastSavedHtml='';await closeEditor(true);
   }
   await loadGuide();
  }catch(error){setNotice(error.message,'error')}
  finally{state.busy=false;$('guideSubmitButton').disabled=false}
 }
 async function selectAdminSubmission(id){
  const item=(state.payload?.admin_pending||[]).find(value=>value.id===id);if(!item)return;
  if(draftEnabled()){
   try{await saveDraftNow()}catch(error){setNotice(`草稿儲存失敗，無法切換投稿：${error.message}`,'error');return}
  }
  state.activePendingId=id;state.editingSubmissionId=id;state.editorOpen=true;
  $('guideEditorPanel').hidden=false;$('guideEditorSection').hidden=false;$('guideEditorTitle').textContent='審查投稿內容';$('guideSubmitButton').textContent='儲存審查修訂';
  setEditorContent(item.content_html||'',providerText(item));
  $('guideReviewProvider').textContent=`投稿者：${item.provider||'未命名使用者'} · 投稿時間：${formatTime(item.updated_at)}`;
  $('guideReviewNote').value=item.review_note||'';$('guideReviewDetail').hidden=false;renderPendingList();
 }
 async function reviewSubmission(action){
  if(!state.editingSubmissionId||state.busy)return;state.busy=true;
  const button=action==='approve'?$('guideApproveButton'):$('guideRejectButton');button.disabled=true;
  try{
   await apiJson(`/api/admin/guide-submissions/${encodeURIComponent(state.editingSubmissionId)}`,{method:'PUT',body:JSON.stringify({content_html:editorHtml()})});
   await apiJson(`/api/admin/guide-submissions/${encodeURIComponent(state.editingSubmissionId)}/review`,{method:'POST',body:JSON.stringify({action,review_note:$('guideReviewNote').value})});
   setNotice(action==='approve'?'攻略已核准發布。':'攻略已退回投稿者修改。','success');closeEditor();await loadGuide();
  }catch(error){setNotice(error.message,'error')}
  finally{state.busy=false;button.disabled=false}
 }
 function insertHtml(html){
  restoreSelection();guideEditor.$.focusManager.focus();
  guideEditor.$.html.insert(html,{skipCleaning:true});
  saveSelection();hydrateVideos(editorSurface());guideEditor.$.history.push(false);scheduleDraftSave();updateWordCount();
 }
 async function uploadGuideImage(file){
  if(!['image/jpeg','image/png','image/webp','image/gif'].includes(file.type))throw new Error('只支援 JPG、PNG、WebP 或 GIF 圖片。');
  if(file.size>20*1024*1024)throw new Error('單張圖片上限為 20 MB。');
  const form=new FormData();form.append('file-0',file,file.name||'貼圖');
  const response=await fetch('/api/guide-media-upload',{method:'POST',credentials:'same-origin',body:form});
  let payload={};try{payload=await response.json()}catch{}
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:`請求失敗（${response.status}）`);
  return payload.result?.[0]||{};
 }
 function imageHtml(result,alt='',caption=''){return `<figure class="guideImage"><img src="${esc(result.url)}" alt="${esc(alt)}" loading="lazy" decoding="async">${caption?`<figcaption>${esc(caption)}</figcaption>`:''}</figure><p><br></p>`}
 const stickerStorageKey=()=>`milora-guide-stickers-${state.user?.id||state.user?.username||'local'}`;
 function savedStickers(){
  try{return JSON.parse(localStorage.getItem(stickerStorageKey())||'[]').filter(url=>typeof url==='string'&&url.startsWith('/api/guide-media/')).slice(0,48)}catch{return []}
 }
 function renderStickers(){
  const grid=$('guideStickerGrid');grid.replaceChildren();
  for(const url of savedStickers()){
   const button=document.createElement('button');button.type='button';button.title='加入這張貼圖';
   const image=document.createElement('img');image.src=url;image.alt='已上傳貼圖';image.loading='lazy';button.append(image);
   button.addEventListener('click',()=>{insertHtml(imageHtml({url}));$('guideStickerDialog').close()});grid.append(button);
  }
  if(!grid.childElementCount){const empty=document.createElement('p');empty.textContent='目前沒有已儲存的貼圖。';grid.append(empty)}
 }
 $('guideEditButton').addEventListener('click',openEditor);$('guideEmptyEditButton').addEventListener('click',openEditor);
 $('guideCloseEditorButton').addEventListener('click',()=>closeEditor());$('guideCancelEditorButton').addEventListener('click',()=>closeEditor());
 $('guideSubmitButton').addEventListener('click',saveSubmission);
 if(!window.SUNEDITOR){
  $('guideEditButton').disabled=true;$('guideEmptyEditButton').disabled=true;
  loadGuide().then(()=>setNotice('攻略內容仍可閱讀，但編輯器載入失敗；請重新整理頁面。','error'));
  return;
 }
 const SunEditorCommand=Object.getPrototypeOf(SUNEDITOR.plugins.blockquote);
 class GuideSpoilerPlugin extends SunEditorCommand{
  static key='guideSpoiler';static className='guidePluginSpoiler';
  constructor(kernel){super(kernel);this.title=window.MiloraGuideEditorI18n?.pluginTitle('spoiler')||'暴雷／反黑';this.icon='blockquote'}
  action(){toggleSpoiler()}
 }
 class GuideEmojiPlugin extends SunEditorCommand{
  static key='guideEmoji';static className='guidePluginEmoji';
  constructor(kernel){super(kernel);this.title='Emoji';this.icon='blockquote'}
  action(){saveSelection();$('guideEmojiDialog').showModal()}
 }
 class GuideStickerPlugin extends SunEditorCommand{
  static key='guideSticker';static className='guidePluginSticker';
  constructor(kernel){super(kernel);this.title=window.MiloraGuideEditorI18n?.pluginTitle('sticker')||'貼圖／GIF';this.icon='blockquote'}
  action(){saveSelection();renderStickers();$('guideStickerStatus').textContent='';$('guideStickerDialog').showModal()}
 }
 guideEditor=SUNEDITOR.create('#guideEditor',{
  plugins:{...SUNEDITOR.plugins,guideSpoiler:GuideSpoilerPlugin,guideEmoji:GuideEmojiPlugin,guideSticker:GuideStickerPlugin},
  buttonList:[['undo','redo'],['blockStyle','font','fontSize'],['bold','italic','underline','strike','fontColor','backgroundColor','removeFormat','guideSpoiler'],['align','outdent','indent','list_bulleted','list_numbered','blockquote','lineHeight'],['link','image','video','table','codeBlock','guideEmoji','guideSticker'],['codeView','fullScreen']],
  lang:window.MiloraGuideEditorI18n?.nativeLanguage()||window.SUNEDITOR_LANG.zh_tw,
  blockStyle:{items:['p','h1','h2','h3','h4','h5','h6']},
  font:{items:['微軟正黑體','微軟正黑體 UI','思源黑體','思源宋體','蘋方繁','新細明體','細明體','標楷體','Arial','Georgia','Times New Roman','Tahoma','Verdana','Consolas','Courier New']},
  image:{uploadUrl:'/api/guide-media-upload',uploadSingleSizeLimit:20*1024*1024,acceptedFormats:'image/png,image/jpeg,image/webp,image/gif',allowMultiple:false,createUrlInput:false},
  video:{createFileInput:false,createUrlInput:true,embedQuery:{bilibili:{pattern:/^https:\/\/(?:www\.|m\.)?bilibili\.com\/video\/BV[A-Za-z0-9]{8,20}/i,action:url=>{
   const id=new URL(url).pathname.match(/^\/video\/(BV[A-Za-z0-9]{8,20})/i)?.[1];
   return `https://player.bilibili.com/player.html?bvid=${id}&page=1`;
  },tag:'iframe'}}},
  autocomplete:{delayTime:180,limitSize:8,triggers:{'@':{apiUrl:'/api/guide-members?q={key}&limit={limitSize}',searchStartLength:2,useCachingData:false,transformResponse:response=>(response.users||[]).map(user=>({key:user.username}))}}},
  fontSize:{sizeUnit:'px',disableInput:true,unitMap:{px:{default:16,inc:1,min:12,max:40,list:[12,13,14,15,16,17,18,20,22,24,26,28,32,36,40]}}},
  lineHeight:{items:[{text:'1.2',value:'1.2'},{text:'1.3',value:'1.3'},{text:'1.4',value:'1.4'},{text:'1.5',value:'1.5'},{text:'1.6',value:'1.6'},{text:'1.7',value:'1.7'},{text:'1.8',value:'1.8'},{text:'1.9',value:'1.9'},{text:'2.0',value:'2'},{text:'2.2',value:'2.2'}]},
  allowedClassName:'spoiler|guideSpoiler|guideVideo|guideImage',
  attributeWhitelist:{figure:'data-guide-video-url'},
  events:{onChange:()=>{scheduleDraftSave();updateWordCount();requestAnimationFrame(syncFontSizeLabel)},onVideoUploadBefore:async ({info})=>{
   if(!info.url)return false;
   try{await apiJson('/api/guide-video/validate',{method:'POST',body:JSON.stringify({url:info.url})});return true}
   catch(error){setNotice(`不支援的影片連結：${error.message}`,'error');return false}
  }}
 });
 window.MiloraGuideEditorI18n?.bind(guideEditor);
 $('guidePreviewButton').hidden=false;
 const surface=editorSurface();
 surface.classList.add('guideDocument');
 surface.setAttribute('aria-label','攻略內容');
 surface.addEventListener('input',()=>{scheduleDraftSave();updateWordCount()});
 window.addEventListener('beforeunload',event=>{
  if(!draftEnabled())return;
  if(state.pendingUploads||editorHtml()!==state.draftLastSavedHtml){event.preventDefault();event.returnValue=''}
 });
 surface.addEventListener('mouseup',saveSelection);surface.addEventListener('keyup',saveSelection);surface.addEventListener('focus',saveSelection);
 document.addEventListener('selectionchange',()=>requestAnimationFrame(syncFontSizeLabel));
 const emojiCharacters='😀 😄 😆 😂 🥹 😊 😍 🥰 😎 😢 😭 😡 🤔 😮 🫡 👍 👎 👏 🙏 💪 ❤️ 🧡 💛 💚 💙 💜 ✨ 🎉 🔥 ⭐ 💯 👀 🎮 📚'.split(' ');
 for(const symbol of emojiCharacters){
  const button=document.createElement('button');button.type='button';button.textContent=symbol;button.setAttribute('aria-label',`加入 ${symbol}`);
  button.addEventListener('click',()=>{insertHtml(esc(symbol));$('guideEmojiDialog').close()});$('guideEmojiGrid').append(button);
 }
 $('guideCloseEmojiButton').addEventListener('click',()=>$('guideEmojiDialog').close());
 $('guideCloseStickerButton').addEventListener('click',()=>$('guideStickerDialog').close());
 $('guideStickerFile').addEventListener('change',async event=>{
  const file=event.target.files?.[0];if(!file)return;
  state.pendingUploads++;$('guideStickerStatus').textContent='正在上傳貼圖…';
  try{
   const result=await uploadGuideImage(file),url=String(result.url||'');
   if(!url.startsWith('/api/guide-media/'))throw new Error('圖片網址格式不正確。');
   localStorage.setItem(stickerStorageKey(),JSON.stringify([url,...savedStickers().filter(item=>item!==url)].slice(0,48)));
   renderStickers();$('guideStickerStatus').textContent='上傳完成，可點選貼圖加入文章。';
  }catch(error){$('guideStickerStatus').textContent=`上傳失敗：${error.message}`}
  finally{state.pendingUploads--;event.target.value=''}
 });
 $('guidePreviewButton').addEventListener('click',async()=>{
  if(state.pendingUploads){setNotice('請先等待圖片上傳完成，再預覽文章。','error');return}
  const button=$('guidePreviewButton');button.disabled=true;
  try{
   const result=await apiJson('/api/guide-preview',{method:'POST',body:JSON.stringify({content_html:editorHtml()})});
   const content=$('guidePreviewContent');content.innerHTML=result.content_html||'<p data-guide-empty="true">目前沒有內容。</p>';
   hydrateSpoilers(content);hydrateVideos(content);$('guidePreviewDialog').showModal();
  }catch(error){setNotice(`文章預覽失敗：${error.message}`,'error')}
  finally{button.disabled=false}
 });
 $('guideClosePreviewButton').addEventListener('click',()=>$('guidePreviewDialog').close());
 $('guidePendingList').addEventListener('click',event=>{const button=event.target.closest('[data-submission-id]');if(button)selectAdminSubmission(button.dataset.submissionId)});
 $('guideApproveButton').addEventListener('click',()=>reviewSubmission('approve'));$('guideRejectButton').addEventListener('click',()=>reviewSubmission('reject'));
 $('guidePublishedContent').addEventListener('click',event=>{const spoiler=event.target.closest('.spoiler');if(spoiler){spoiler.classList.toggle('revealed');spoiler.setAttribute('aria-pressed',String(spoiler.classList.contains('revealed')))}});
 $('guidePublishedContent').addEventListener('keydown',event=>{if(!['Enter',' '].includes(event.key))return;const spoiler=event.target.closest('.spoiler');if(spoiler){event.preventDefault();spoiler.click()}});
 $('guidePreviewContent').addEventListener('click',event=>{const spoiler=event.target.closest('.spoiler');if(spoiler){spoiler.classList.toggle('revealed');spoiler.setAttribute('aria-pressed',String(spoiler.classList.contains('revealed')))}});
 $('guidePreviewContent').addEventListener('keydown',event=>{if(!['Enter',' '].includes(event.key))return;const spoiler=event.target.closest('.spoiler');if(spoiler){event.preventDefault();spoiler.click()}});
 window.addEventListener('message',event=>{if(event.origin===location.origin&&event.data?.type==='achievement-hub-auth-changed')loadGuide()});
 window.addEventListener('milora:data-changed',()=>{if(!state.editorOpen&&!state.busy)void loadGuide()});
 loadGuide();
})();
