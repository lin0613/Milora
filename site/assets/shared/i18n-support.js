(function(){
 const api=window.MiloraI18n;if(!api)return;
 const rows=[
 ['title','問題回報與客服單','Reports and support tickets','問題報告・サポート','问题反馈与客服单'],
 ['close','關閉','Close','閉じる','关闭'],['create','建立新客服單','Create a support ticket','問い合わせを作成','创建新客服单'],
 ['subject','主旨','Subject','件名','主题'],['message','問題說明','Description','お問い合わせ内容','问题说明'],
 ['send','送出','Submit','送信','提交'],['mine','我的客服單','My support tickets','自分の問い合わせ','我的客服单'],
 ['loading','正在載入客服單……','Loading support tickets…','問い合わせを読み込み中…','正在加载客服单……'],
 ['loginRequired','請先登入後再使用問題回報。','Sign in to submit a report.','問題を報告するにはログインしてください。','请先登录后再使用问题反馈。'],
 ['empty','尚未建立客服單。','No support tickets yet.','問い合わせはまだありません。','尚未创建客服单。'],
 ['pending','等待處理','Pending','対応待ち','等待处理'],['open','處理中','In progress','対応中','处理中'],
 ['resolved','已解決','Resolved','解決済み','已解决'],['closed','已結案','Closed','終了','已结案'],
 ['unknown','未知','Unknown','不明','未知'],['admin','管理員','Administrator','管理者','管理员'],
 ['user','使用者','User','ユーザー','用户'],['replyPlaceholder','補充說明','Additional details','補足説明','补充说明'],
 ['reply','送出回覆','Send reply','返信を送信','发送回复'],['delete','刪除客服單','Delete ticket','問い合わせを削除','删除客服单'],
 ['confirmDelete','確定永久刪除此客服單及全部對話嗎？','Permanently delete this ticket and all conversations?','この問い合わせとすべての会話を完全に削除しますか？','确定永久删除此客服单及全部对话吗？'],
 ['loadFailed','客服單載入失敗，請稍後再試。','Could not load tickets. Please try again later.','問い合わせを読み込めませんでした。後でもう一度お試しください。','客服单加载失败，请稍后再试。'],
 ['missing','找不到這筆客服單；可能已被刪除或不屬於目前帳號。','Ticket not found. It may have been deleted or belong to another account.','問い合わせが見つかりません。削除済み、または別のアカウントのものかもしれません。','找不到这条客服单；可能已删除或不属于当前账号。'],
 ['sending','正在送出客服單……','Submitting ticket…','問い合わせを送信中…','正在提交客服单……'],
 ['sent','客服單已送出。','Ticket submitted.','問い合わせを送信しました。','客服单已提交。'],
 ['updated','客服單有新內容，請先保存或送出目前草稿，再重新開啟客服單查看。','This ticket has updates. Save or send your draft, then reopen the ticket to view them.','問い合わせが更新されました。下書きを保存または送信してから、問い合わせを開き直してください。','客服单有新内容，请先保存或提交当前草稿，再重新打开客服单查看。']
 ];
 api.languages.forEach((language,index)=>api.register(language,Object.fromEntries(rows.map(row=>['support.'+row[0],row[index+1]]))));
 const keys=new Map(rows.map(row=>[row[1],'support.'+row[0]]));window.MiloraSupportUI=Object.freeze({keyFor:value=>keys.get(value)});
 api.apply();
})();
