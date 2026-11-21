(function(){
 'use strict';
 const api=window.MiloraI18n;if(!api||!document.body.classList.contains('gameProjectPage'))return;
 const rows=[
 ['total','成就總數','Total achievements','実績総数','成就总数',"전체 업적"],
 ['done','已完成','Completed','達成済み','已完成',"완료"],['todo','未完成','Incomplete','未達成','未完成',"미완료"],
 ['visible','目前顯示','Currently shown','表示中','当前显示',"현재 표시"],['rate','完成率','Completion rate','達成率','完成率',"달성률"],
 ['astrite','已獲得星聲','Astrite earned','獲得した星声','已获得星声',"획득한 별의 소리"],
 ['jade','已獲得星瓊','Stellar Jade earned','獲得した星玉','已获得星琼',"획득한 성옥"],
 ['primo','已獲得原石','Primogems earned','獲得した原石','已获得原石',"획득한 원석"],
 ['poly','已獲得菲林','Polychrome earned','獲得したポリクローム','已获得菲林',"획득한 폴리크롬"],
 ['nteReward','已獲得環石','Rewards earned','獲得報酬','已获得环石',"획득한 보상"],
 ['versions','全部版本','All versions','すべてのバージョン','全部版本',"모든 버전"],
 ['categories','全部分類','All categories','すべての分類','全部分类',"모든 분류"],
 ['states','完成狀態：全部','Completion: all','達成状態：すべて','完成状态：全部',"달성 상태: 전체"],
 ['hiddenAll','是否隱藏：全部','Visibility: all','表示区分：すべて','隐藏状态：全部',"공개 여부: 전체"],
 ['hidden','隱藏成就','Hidden achievements','隠し実績','隐藏成就',"숨겨진 업적"],
 ['arcade','街機成就','Arcade achievement','アーケード実績','街机成就',"아케이드 업적"],
 ['notHidden','非隱藏成就','Non-hidden achievements','通常実績','非隐藏成就',"일반 업적"],
 ['tools','資料與進度','Data and progress','データと進捗','数据与进度',"데이터 및 진행 상황"],
 ['guest','訪客可以直接查看與勾選成就；請至帳號設定登入後使用個人進度。','Guests can view and mark achievements. Sign in through account settings to use personal progress.','ゲストでも実績の閲覧とチェックができます。個人の進捗を使うにはアカウント設定からログインしてください。','访客可以直接查看和勾选成就；请前往账号设置登录后使用个人进度。',"게스트도 업적을 보고 체크할 수 있습니다. 개인 진행 상황을 사용하려면 계정 설정에서 로그인하세요."],
 ['export','匯出進度','Export progress','進捗をエクスポート','导出进度',"진행 상황 내보내기"],
 ['guestAccount','訪客可以直接查看成就；登入、註冊與登出統一由帳號設定管理。','Guests can view achievements. Sign-in, registration and sign-out are managed in account settings.','ゲストでも実績を閲覧できます。ログイン・登録・ログアウトはアカウント設定から行ってください。','访客可以直接查看成就；登录、注册和退出统一由账号设置管理。',"게스트도 업적을 볼 수 있습니다. 로그인, 가입 및 로그아웃은 계정 설정에서 할 수 있습니다."],
 ['import','匯入進度','Import progress','進捗をインポート','导入进度',"진행 상황 가져오기"],
 ['mark','標註篩選結果','Mark filtered results','絞り込み結果を達成済みにする','标记筛选结果',"필터 결과를 완료로 표시"],
 ['clear','清除篩選結果','Clear filtered progress','絞り込み結果の進捗を消去','清除筛选结果',"필터 결과의 진행 상황 지우기"],
 ['empty','沒有符合目前條件的成就。','No achievements match these filters.','条件に一致する実績はありません。','没有符合当前条件的成就。',"현재 조건에 맞는 업적이 없습니다."],
 ['prev','上一頁','Previous','前へ','上一页',"이전"],['next','下一頁','Next','次へ','下一页',"다음"],
 ['jump','跳至','Go to','移動先','跳至',"이동"],['page','頁','page','ページ','页',"페이지"],
 ['pageLabel','選擇頁碼','Choose page','ページを選択','选择页码',"페이지 선택"],
 ['search','搜尋成就名稱、達成條件或分類','Search achievement names, conditions or categories','実績名・達成条件・分類を検索','搜索成就名称、达成条件或分类',"업적 이름, 달성 조건 또는 분류 검색"],
 ['size','每頁數量：{count}','Per page: {count}','表示件数：{count}','每页数量：{count}',"페이지당 {count}개"],
 ['info','第 {current} / {pages} 頁，共 {count} 項成就','Page {current} / {pages} · {count} achievements','{current} / {pages} ページ・実績 {count} 件','第 {current} / {pages} 页，共 {count} 项成就',"{current} / {pages}페이지 · 업적 {count}개"]
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
