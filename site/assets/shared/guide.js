(function(){
 'use strict';

 const $=id=>document.getElementById(id);
 const query=new URLSearchParams(location.search);
 const pathParts=location.pathname.split('/').filter(Boolean);
 const gameIds=['wuwa','hsr','genshin','zzz','nte'];
 const pathGame=gameIds.includes(pathParts[0])?pathParts[0]:'';
 const pathAchievement=pathGame?(pathParts[1]||''):'';
 const gameId=String(query.get('game')||pathGame||'').trim().toLowerCase();
 const achievementId=String(query.get('achievement')||pathAchievement||'').trim();
 const state={payload:null,user:null,editingSubmissionId:'',activePendingId:'',savedRange:null,busy:false,editorOpen:false};
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
  if(!response.ok){const detail=value?.detail;throw new Error(typeof detail==='string'?detail:(detail?.message||value?.message||`請求失敗（${response.status}）`))}
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
 function providerText(submission){return submission?.provider?`提供者：${submission.provider}`:''}
 function setEditorContent(html,provider=''){
  $('guideEditor').innerHTML=html||'<p><br></p>';
  hydrateVideos($('guideEditor'));
  $('guideEditorProvider').textContent=provider;
 }
 function hydrateSpoilers(root){
  root.querySelectorAll('.guideSpoiler').forEach(node=>{
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
  setEditorContent(contentForEditing(),state.user?.username?`投稿者：${state.user.username}`:'');
  $('guideEditorPanel').hidden=false;$('guideEditorSection').hidden=false;$('guideReviewDetail').hidden=true;renderPendingList();
  requestAnimationFrame(()=>$('guideEditor').focus());
 }
 function closeEditor(){state.editorOpen=false;state.editingSubmissionId='';state.activePendingId='';$('guideEditorPanel').hidden=true;$('guideReviewDetail').hidden=true;renderPendingList()}
 function saveSelection(){
  const selection=window.getSelection();if(!selection?.rangeCount)return;
  const range=selection.getRangeAt(0);if($('guideEditor').contains(range.commonAncestorContainer))state.savedRange=range.cloneRange();
 }
 function restoreSelection(){
  if(!state.savedRange)return false;const selection=window.getSelection();selection.removeAllRanges();selection.addRange(state.savedRange);return true;
 }
 function exec(command,value=null){$('guideEditor').focus();document.execCommand(command,false,value);saveSelection()}
 function alignSelection(alignment){
  restoreSelection();const selection=window.getSelection();if(!selection?.rangeCount)return;
  let range=selection.getRangeAt(0);if(!$('guideEditor').contains(range.commonAncestorContainer))return;
  let blocks=[...$('guideEditor').querySelectorAll('p,h2,h3,blockquote')].filter(node=>{try{return range.intersectsNode(node)}catch{return false}});
  if(!blocks.length){document.execCommand('formatBlock',false,'<p>');saveSelection();restoreSelection();range=window.getSelection().getRangeAt(0);const node=range.commonAncestorContainer.nodeType===Node.ELEMENT_NODE?range.commonAncestorContainer:range.commonAncestorContainer.parentElement;const block=node?.closest?.('p,h2,h3,blockquote');if(block&&$('guideEditor').contains(block))blocks=[block]}
  blocks.forEach(block=>{block.style.textAlign=alignment});saveSelection();
 }
 function wrapSelection(styleOrClass,value){
  restoreSelection();const selection=window.getSelection();if(!selection?.rangeCount||selection.isCollapsed){alert('請先選取要套用的文字。');return}
  const range=selection.getRangeAt(0);if(!$('guideEditor').contains(range.commonAncestorContainer))return;
  const span=document.createElement('span');if(styleOrClass==='class')span.className=value;else span.style[styleOrClass]=value;
  span.append(range.extractContents());range.insertNode(span);range.selectNodeContents(span);selection.removeAllRanges();selection.addRange(range);saveSelection();
 }
 function editorHtml(){
  const clone=$('guideEditor').cloneNode(true);clone.querySelectorAll('.guideVideoEmbed').forEach(node=>node.remove());
  clone.querySelectorAll('.guideSpoiler.revealed').forEach(node=>node.classList.remove('revealed'));
  return clone.innerHTML;
 }
 async function saveSubmission(){
  if(state.busy)return;state.busy=true;$('guideSubmitButton').disabled=true;
  try{
   const content_html=editorHtml();
   if(state.editingSubmissionId){
    await apiJson(`/api/admin/guide-submissions/${encodeURIComponent(state.editingSubmissionId)}`,{method:'PUT',body:JSON.stringify({content_html})});
    setNotice('審查修訂已儲存。','success');
   }else{
    await apiJson(`/api/games/${encodeURIComponent(gameId)}/achievements/${encodeURIComponent(achievementId)}/guide/submissions`,{method:'POST',body:JSON.stringify({content_html})});
    setNotice('攻略已送出，投稿狀態為「等待審查」。','success');closeEditor();
   }
   await loadGuide();
  }catch(error){setNotice(error.message,'error')}
  finally{state.busy=false;$('guideSubmitButton').disabled=false}
 }
 function selectAdminSubmission(id){
  const item=(state.payload?.admin_pending||[]).find(value=>value.id===id);if(!item)return;
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
 function insertHtml(html){restoreSelection();$('guideEditor').focus();document.execCommand('insertHTML',false,html);saveSelection();hydrateVideos($('guideEditor'))}
 function fileAsBase64(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||'').split(',',2)[1]||'');reader.onerror=()=>reject(new Error('無法讀取圖片。'));reader.readAsDataURL(file)})}

 $('guideEditButton').addEventListener('click',openEditor);$('guideEmptyEditButton').addEventListener('click',openEditor);
 $('guideCloseEditorButton').addEventListener('click',closeEditor);$('guideCancelEditorButton').addEventListener('click',closeEditor);
 $('guideSubmitButton').addEventListener('click',saveSubmission);
 $('guideEditor').addEventListener('mouseup',saveSelection);$('guideEditor').addEventListener('keyup',saveSelection);$('guideEditor').addEventListener('focus',saveSelection);
 $('guideToolbar').addEventListener('mousedown',event=>{if(event.target.closest('button'))event.preventDefault()});
 $('guideToolbar').addEventListener('click',event=>{const button=event.target.closest('[data-command]');if(!button)return;const command=button.dataset.command;if(command==='justifyLeft')alignSelection('left');else if(command==='justifyCenter')alignSelection('center');else if(command==='justifyRight')alignSelection('right');else exec(command)});
 $('guideBlockFormat').addEventListener('change',event=>exec('formatBlock',`<${event.target.value}>`));
 $('guideTextColor').addEventListener('change',event=>wrapSelection('color',event.target.value));
 $('guideFontSize').addEventListener('change',event=>wrapSelection('fontSize',event.target.value));
 $('guideSpoilerButton').addEventListener('click',()=>wrapSelection('class','guideSpoiler'));
 $('guideLinkButton').addEventListener('click',()=>{saveSelection();$('guideLinkUrl').value='';$('guideLinkText').value=window.getSelection()?.toString()||'';$('guideLinkDialog').showModal()});
 $('guideImageButton').addEventListener('click',()=>{saveSelection();$('guideImageForm').reset();$('guideImageDialog').showModal()});
 $('guideVideoButton').addEventListener('click',()=>{saveSelection();$('guideVideoForm').reset();$('guideVideoDialog').showModal()});
 $('guideLinkForm').addEventListener('submit',event=>{
  if(event.submitter?.value!=='confirm')return;event.preventDefault();const url=$('guideLinkUrl').value.trim(),text=$('guideLinkText').value.trim();
  try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol))throw new Error();insertHtml(`<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">${esc(text||parsed.href)}</a>`);$('guideLinkDialog').close()}catch{alert('請輸入有效的 http 或 https 網址。')}
 });
 $('guideImageForm').addEventListener('submit',async event=>{
  if(event.submitter?.value!=='confirm')return;event.preventDefault();const file=$('guideImageFile').files?.[0];if(!file)return;
  if(file.size>5*1024*1024)return alert('單張圖片上限為 5 MB。');const button=$('guideImageUploadButton');button.disabled=true;
  try{const result=await apiJson('/api/guide-media',{method:'POST',body:JSON.stringify({filename:file.name,content_base64:await fileAsBase64(file)})});const alt=$('guideImageAlt').value.trim(),caption=$('guideImageCaption').value.trim();insertHtml(`<figure class="guideImage"><img src="${esc(result.url)}" alt="${esc(alt)}">${caption?`<figcaption>${esc(caption)}</figcaption>`:''}</figure><p><br></p>`);$('guideImageDialog').close()}
  catch(error){alert(error.message)}finally{button.disabled=false}
 });
 $('guideVideoForm').addEventListener('submit',async event=>{
  if(event.submitter?.value!=='confirm')return;event.preventDefault();const button=$('guideVideoInsertButton');button.disabled=true;
  try{const result=await apiJson('/api/guide-video/validate',{method:'POST',body:JSON.stringify({url:$('guideVideoUrl').value.trim()})});const caption=$('guideVideoCaption').value.trim();insertHtml(`<figure class="guideVideo" data-guide-video-url="${esc(result.url)}">${caption?`<figcaption>${esc(caption)}</figcaption>`:''}</figure><p><br></p>`);$('guideVideoDialog').close()}
  catch(error){alert(error.message)}finally{button.disabled=false}
 });
 $('guidePendingList').addEventListener('click',event=>{const button=event.target.closest('[data-submission-id]');if(button)selectAdminSubmission(button.dataset.submissionId)});
 $('guideApproveButton').addEventListener('click',()=>reviewSubmission('approve'));$('guideRejectButton').addEventListener('click',()=>reviewSubmission('reject'));
 $('guidePublishedContent').addEventListener('click',event=>{const spoiler=event.target.closest('.guideSpoiler');if(spoiler){spoiler.classList.toggle('revealed');spoiler.setAttribute('aria-pressed',String(spoiler.classList.contains('revealed')))}});
 $('guidePublishedContent').addEventListener('keydown',event=>{if(!['Enter',' '].includes(event.key))return;const spoiler=event.target.closest('.guideSpoiler');if(spoiler){event.preventDefault();spoiler.click()}});
 window.addEventListener('message',event=>{if(event.origin===location.origin&&event.data?.type==='achievement-hub-auth-changed')loadGuide()});
 loadGuide();
})();
