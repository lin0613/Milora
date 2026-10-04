(function(){
  const api=window.MiloraI18n;if(!api)return;
  const rows=[
    ['title','訊息中心','Message center','メッセージセンター','消息中心'],
    ['all','全部','All','すべて','全部'],['notification','通知','Notifications','通知','通知'],
    ['announcement','公告','Announcements','お知らせ','公告'],
    ['readAll','目前分頁全部標為已讀','Mark this category as read','この分類をすべて既読にする','当前分类全部标为已读'],
    ['deleteAll','刪除全部通知','Delete all notifications','すべての通知を削除','删除全部通知'],
    ['close','關閉訊息中心','Close message center','メッセージセンターを閉じる','关闭消息中心'],
    ['list.all','全部訊息清單','All messages','すべてのメッセージ','全部消息列表'],
    ['list.notification','通知清單','Notifications list','通知一覧','通知列表'],
    ['list.announcement','公告清單','Announcements list','お知らせ一覧','公告列表'],
    ['empty.all','目前沒有訊息。','No messages.','メッセージはありません。','目前没有消息。'],
    ['empty.notification','目前沒有通知。','No notifications.','通知はありません。','目前没有通知。'],
    ['empty.announcement','目前沒有公告。','No announcements.','お知らせはありません。','目前没有公告。'],
    ['info','一般','General','一般','一般'],['success','成功','Success','成功','成功'],
    ['warning','提醒','Reminder','注意','提醒'],['danger','重要','Important','重要','重要'],
    ['update','更新','Update','更新','更新'],['pinned','置頂','Pinned','固定','置顶'],
    ['untitled','未命名公告','Untitled announcement','無題のお知らせ','未命名公告'],
    ['go','前往','Open','開く','前往'],['delete','刪除通知','Delete notification','通知を削除','删除通知'],
    ['confirmDelete','確定要刪除這則通知嗎？','Delete this notification?','この通知を削除しますか？','确定要删除这条通知吗？'],
    ['confirmDeleteAll','確定刪除目前帳號的全部 {count} 則通知？公告不會刪除。','Delete all {count} notifications for this account? Announcements will not be deleted.','このアカウントの通知 {count} 件をすべて削除しますか？お知らせは削除されません。','确定删除当前账号的全部 {count} 条通知？公告不会删除。']
  ];
  api.languages.forEach((language,index)=>api.register(language,Object.fromEntries(rows.map(row=>['messages.'+row[0],row[index+1]]))));
  for(const [selector,key] of [['#notificationHubTitle','title'],['#markAllNotificationHubBtn','readAll'],['#deleteAllNotificationHubBtn','deleteAll']]){
    const el=document.querySelector(selector);if(el)el.dataset.i18n='messages.'+key;
  }
  document.querySelectorAll('[data-message-type]').forEach(el=>el.dataset.i18n='messages.'+el.dataset.messageType);
  document.getElementById('closeNotificationHubBtn')?.setAttribute('data-i18n-aria-label','messages.close');
  api.apply();window.dispatchEvent(new Event('milora:messages-language-ready'));
})();
