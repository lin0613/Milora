(function () {
  const api = window.MiloraI18n;
  if (!api) return;
  const rows = [
    ['title','兌換碼','Redemption codes','シリアルコード','兑换码',"교환 코드"],
    ['intro','各遊戲目前收錄的兌換碼與服務器適用範圍。','Available game codes and applicable servers.','収録済みのゲームコードと対象サーバー。','各游戏当前收录的兑换码与适用服务器。',"게임별로 등록된 교환 코드와 적용 서버를 확인할 수 있습니다."],
    ['choose','選擇遊戲','Choose a game','ゲームを選択','选择游戏',"게임 선택"],
    ['loading','正在載入……','Loading…','読み込み中…','正在加载……',"불러오는 중…"],
    ['loadingCodes','正在載入兌換碼……','Loading codes…','コードを読み込み中…','正在加载兑换码……',"교환 코드를 불러오는 중…"],
    ['source','來源','Source','出典','来源',"출처"],['reward','獎勵','Rewards','報酬','奖励',"보상"],
    ['time','時間','Dates','期間','时间',"기간"],['server','服務器','Server','サーバー','服务器',"서버"],
    ['serverName','服務器名稱','Server name','サーバー名','服务器名称',"서버 이름"],
    ['status','狀態','Status','状態','状态',"상태"],['actions','操作','Actions','操作','操作',"작업"],
    ['open','開放中','Available','有効','开放中',"사용 가능"],['expired','已過期','Expired','期限切れ','已过期',"만료됨"],
    ['unknown','未知','Unknown','不明','未知',"알 수 없음"],['unset','未設定','Not set','未設定','未设置',"미설정"],
    ['copy','複製','Copy','コピー','复制',"복사"],['go','前往','Open','開く','前往',"열기"],
    ['chooseFirst','請先選擇遊戲','Choose a game first','先にゲームを選択してください','请先选择游戏',"먼저 게임을 선택하세요"],
    ['chooseEmpty','請先選擇遊戲。','Choose a game first.','先にゲームを選択してください。','请先选择游戏。',"먼저 게임을 선택하세요."],
    ['noGames','目前沒有可選擇的遊戲。','No games available.','選択できるゲームはありません。','目前没有可选择的游戏。',"선택할 수 있는 게임이 없습니다."],
    ['noCodes','目前沒有可顯示的兌換碼。','No codes to display.','表示できるコードはありません。','目前没有可显示的兑换码。',"표시할 교환 코드가 없습니다."],
    ['failed','載入失敗','Loading failed','読み込みに失敗しました','加载失败',"불러오기 실패"],
    ['prev','上一頁','Previous','前へ','上一页',"이전"],['next','下一頁','Next','次へ','下一页',"다음"],
    ['page','第 {page} / {pages} 頁','Page {page} / {pages}','{page} / {pages} ページ','第 {page} / {pages} 页',"{page} / {pages}페이지"],
    ['jump','跳至','Go to','移動','跳至',"이동"],['pageUnit','頁','Page','ページ','页',"페이지"],
    ['choosePage','選擇頁碼','Choose page','ページを選択','选择页码',"페이지 선택"],
    ['count','{game}：共 {count} 筆','{game}: {count} codes','{game}：{count} 件','{game}：共 {count} 条',"{game}: 교환 코드 {count}개"],
    ['copied','兌換碼已複製成功','Code copied','コードをコピーしました','兑换码已复制成功',"교환 코드를 복사했습니다."],
    ['copyFailed','複製失敗，請手動選取兌換碼。','Copy failed. Select the code manually.','コピーできませんでした。コードを手動で選択してください。','复制失败，请手动选择兑换码。',"복사하지 못했습니다. 교환 코드를 직접 선택하세요."],
    ['notifications','兌換碼通知','Code notifications','コード通知','兑换码通知',"교환 코드 알림"],
    ['notifyHint','新增兌換碼時通知','Notify me when codes are added','コード追加時に通知する','新增兑换码时通知',"새 교환 코드가 추가되면 알림 받기"],
    ['close','關閉','Close','閉じる','关闭',"닫기"],['cancel','取消','Cancel','キャンセル','取消',"취소"],
    ['save','儲存設定','Save settings','設定を保存','保存设置',"설정 저장"],
    ['loadingSettings','正在載入設定……','Loading settings…','設定を読み込み中…','正在加载设置……',"설정을 불러오는 중…"],
    ['saving','正在儲存……','Saving…','保存中…','正在保存……',"저장 중…"],
    ['saved','通知設定已儲存。','Notification settings saved.','通知設定を保存しました。','通知设置已保存。',"알림 설정을 저장했습니다."],
    ['savedToast','兌換碼通知已儲存','Code notifications saved','コード通知を保存しました','兑换码通知已保存',"교환 코드 알림을 저장했습니다."],
    ['noSubscriptions','目前沒有可訂閱的遊戲。','No games to subscribe to.','通知を設定できるゲームはありません。','目前没有可订阅的游戏。',"구독할 수 있는 게임이 없습니다."],
    ['filterLabel','兌換碼篩選','Code filters','コードの絞り込み','兑换码筛选',"교환 코드 필터"],
    ['pagerLabel','兌換碼分頁','Code pagination','コードのページ切り替え','兑换码分页',"교환 코드 페이지 이동"]
  ];
  api.languages.forEach((language,index)=>api.register(language,Object.fromEntries(rows.map(row=>['redeem.'+row[0],row[index+1]]))));
  const keys=new Map(rows.map(row=>[row[1], 'redeem.'+row[0]]));
  window.MiloraRedeemUI=Object.freeze({keyFor:value=>keys.get(value)});
  // Bind only static interface elements. Never scan code/reward/server/source data.
  const bindings = {'h1':'title','.top p':'intro','.filtersLabel':'choose',
    '.notificationSettingsBtn':'notifications','#notificationSettingsTitle':'notifications',
    '.settingsHead p':'notifyHint','#cancelNotificationSettingsBtn':'cancel','#saveNotificationSettingsBtn':'save'};
  for(const [selector,key] of Object.entries(bindings)) document.querySelectorAll(selector).forEach(el=>el.dataset.i18n='redeem.'+key);
  ['title','source','reward','time','serverName','status','actions'].forEach((key,index)=>{
    const el=document.querySelectorAll('thead th')[index];if(el)el.dataset.i18n='redeem.'+key;
  });
  for(const [selector,key] of [['.filters','filterLabel'],['#pager','pagerLabel'],['#mobileGameMenu','choose'],['#closeNotificationSettingsBtn','close']]) {
    const el=document.querySelector(selector);if(el)el.setAttribute('data-i18n-aria-label','redeem.'+key);
  }
  api.apply();
  window.dispatchEvent(new Event('milora:redeem-language-ready'));
})();
