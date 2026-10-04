(function(){
 'use strict';
 const api=window.MiloraI18n;if(!api||!document.body.classList.contains('gameProjectPage'))return;
 const rows=[
 ['total','成就總數','Total achievements','実績総数','成就总数'],
 ['done','已完成','Completed','達成済み','已完成'],['todo','未完成','Incomplete','未達成','未完成'],
 ['visible','目前顯示','Currently shown','表示中','当前显示'],['rate','完成率','Completion rate','達成率','完成率'],
 ['astrite','已獲得星聲','Astrite earned','獲得した星声','已获得星声'],
 ['jade','已獲得星瓊','Stellar Jade earned','獲得した星玉','已获得星琼'],
 ['primo','已獲得原石','Primogems earned','獲得した原石','已获得原石'],
 ['poly','已獲得菲林','Polychrome earned','獲得したポリクローム','已获得菲林'],
 ['nteReward','已獲得環石','Rewards earned','獲得報酬','已获得环石'],
 ['versions','全部版本','All versions','すべてのバージョン','全部版本'],
 ['categories','全部分類','All categories','すべての分類','全部分类'],
 ['states','完成狀態：全部','Completion: all','達成状態：すべて','完成状态：全部'],
 ['hiddenAll','是否隱藏：全部','Visibility: all','表示区分：すべて','隐藏状态：全部'],
 ['hidden','隱藏成就','Hidden achievements','隠し実績','隐藏成就'],
 ['arcade','街機成就','Arcade achievement','アーケード実績','街机成就'],
 ['notHidden','非隱藏成就','Non-hidden achievements','通常実績','非隐藏成就'],
 ['tools','資料與進度','Data and progress','データと進捗','数据与进度'],
 ['guest','訪客可以直接查看與勾選成就；請至帳號設定登入後使用個人進度。','Guests can view and mark achievements. Sign in through account settings to use personal progress.','ゲストでも実績の閲覧とチェックができます。個人の進捗を使うにはアカウント設定からログインしてください。','访客可以直接查看和勾选成就；请前往账号设置登录后使用个人进度。'],
 ['export','匯出進度','Export progress','進捗をエクスポート','导出进度'],
 ['guestAccount','訪客可以直接查看成就；登入、註冊與登出統一由帳號設定管理。','Guests can view achievements. Sign-in, registration and sign-out are managed in account settings.','ゲストでも実績を閲覧できます。ログイン・登録・ログアウトはアカウント設定から行ってください。','访客可以直接查看成就；登录、注册和退出统一由账号设置管理。'],
 ['import','匯入進度','Import progress','進捗をインポート','导入进度'],
 ['mark','標註篩選結果','Mark filtered results','絞り込み結果を達成済みにする','标记筛选结果'],
 ['clear','清除篩選結果','Clear filtered progress','絞り込み結果の進捗を消去','清除筛选结果'],
 ['empty','沒有符合目前條件的成就。','No achievements match these filters.','条件に一致する実績はありません。','没有符合当前条件的成就。'],
 ['prev','上一頁','Previous','前へ','上一页'],['next','下一頁','Next','次へ','下一页'],
 ['jump','跳至','Go to','移動先','跳至'],['page','頁','page','ページ','页'],
 ['pageLabel','選擇頁碼','Choose page','ページを選択','选择页码'],
 ['search','搜尋成就名稱、達成條件或分類','Search achievement names, conditions or categories','実績名・達成条件・分類を検索','搜索成就名称、达成条件或分类'],
 ['size','每頁數量：{count}','Per page: {count}','表示件数：{count}','每页数量：{count}'],
 ['info','第 {current} / {pages} 頁，共 {count} 項成就','Page {current} / {pages} · {count} achievements','{current} / {pages} ページ・実績 {count} 件','第 {current} / {pages} 页，共 {count} 项成就']
 ];
 const keys=new Map(rows.map(row=>[row[1],row[0]]));
 for(const [index,code] of api.languages.entries())api.register(code,Object.fromEntries(rows.map(row=>['gameUi.'+row[0],row[index+1]])));
 const originals=new WeakMap();
 function translate(value){const key=keys.get(value);if(key)return api.t('gameUi.'+key);
  let match=value.match(/^每頁數量：(\d+)$/);if(match)return api.t('gameUi.size',{count:match[1]});
  match=value.match(/^第 (\d+) \/ (\d+) 頁，共 (\d+) 項成就$/);if(match)return api.t('gameUi.info',{current:match[1],pages:match[2],count:match[3]});return value}
 function update(node,attribute){const value=attribute?node.getAttribute(attribute):node.nodeValue;if(!value)return;
  let state=originals.get(node);if(!state){state={};originals.set(node,state)}const slot=attribute||'text',previous=state[slot];
  const source=previous&&previous.output===value?previous.source:value,trimmed=source.trim(),output=source.replace(trimmed,translate(trimmed));
  state[slot]={source,output};if(output!==value){if(attribute)node.setAttribute(attribute,output);else node.nodeValue=output}}
 const selectors=['.stats .label','#version > option[value=""]','#category > option[value=""]','#state > option','#hidden > option','#pageSize > option',
  '#dataProgressSection h3','#dataProgressSection .compactPanelText > p','#exportBtn','#importBtn','#markFilteredBtn','#resetBtn','#empty','#prevBtn','#nextBtn','#pageInfo','.pageJumpLabel','#list .hiddenTag','#list .arcadeTag'];
 function apply(){document.querySelectorAll(selectors.join(',')).forEach(el=>el.childNodes.forEach(node=>{if(node.nodeType===Node.TEXT_NODE)update(node)}));
  const search=document.getElementById('achievementSearch'),jump=document.getElementById('pageJump');if(search)update(search,'placeholder');if(jump)update(jump,'aria-label')}
 apply();window.addEventListener('milora-language-change',apply);
 // UI-only text updates: no rerender, API request, input value or progress change.
 new MutationObserver(apply).observe(document.body,{subtree:true,childList:true,characterData:true});
})();
