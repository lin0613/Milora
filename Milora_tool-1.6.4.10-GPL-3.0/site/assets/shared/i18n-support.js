(function(){
 const api=window.MiloraI18n;if(!api)return;
 const rows=[
 ['title','問題回報與客服單','Reports and support tickets','問題報告・サポート','问题反馈与客服单',"문제 신고 및 고객 지원"],
 ['close','關閉','Close','閉じる','关闭',"닫기"],['create','建立新客服單','Create a support ticket','問い合わせを作成','创建新客服单',"새 문의 작성"],
 ['subject','主旨','Subject','件名','主题',"제목"],['message','問題說明','Description','お問い合わせ内容','问题说明',"문제 설명"],
 ['send','送出','Submit','送信','提交',"제출"],['mine','我的客服單','My support tickets','自分の問い合わせ','我的客服单',"내 문의"],
 ['loading','正在載入客服單……','Loading support tickets…','問い合わせを読み込み中…','正在加载客服单……',"문의 내역을 불러오는 중…"],
 ['loginRequired','請先登入後再使用問題回報。','Sign in to submit a report.','問題を報告するにはログインしてください。','请先登录后再使用问题反馈。',"문제를 신고하려면 로그인하세요."],
 ['empty','尚未建立客服單。','No support tickets yet.','問い合わせはまだありません。','尚未创建客服单。',"문의 내역이 없습니다."],
 ['pending','等待處理','Pending','対応待ち','等待处理',"처리 대기 중"],['open','處理中','In progress','対応中','处理中',"처리 중"],
 ['resolved','已解決','Resolved','解決済み','已解决',"해결됨"],['closed','已結案','Closed','終了','已结案',"종료됨"],
 ['unknown','未知','Unknown','不明','未知',"알 수 없음"],['admin','管理員','Administrator','管理者','管理员',"관리자"],
 ['user','使用者','User','ユーザー','用户',"사용자"],['replyPlaceholder','補充說明','Additional details','補足説明','补充说明',"추가 설명"],
 ['reply','送出回覆','Send reply','返信を送信','发送回复',"답변 보내기"],['delete','刪除客服單','Delete ticket','問い合わせを削除','删除客服单',"문의 삭제"],
 ['confirmDelete','確定永久刪除此客服單及全部對話嗎？','Permanently delete this ticket and all conversations?','この問い合わせとすべての会話を完全に削除しますか？','确定永久删除此客服单及全部对话吗？',"이 문의와 모든 대화를 영구 삭제할까요?"],
 ['loadFailed','客服單載入失敗，請稍後再試。','Could not load tickets. Please try again later.','問い合わせを読み込めませんでした。後でもう一度お試しください。','客服单加载失败，请稍后再试。',"문의 내역을 불러오지 못했습니다. 잠시 후 다시 시도하세요."],
 ['missing','找不到這筆客服單；可能已被刪除或不屬於目前帳號。','Ticket not found. It may have been deleted or belong to another account.','問い合わせが見つかりません。削除済み、または別のアカウントのものかもしれません。','找不到这条客服单；可能已删除或不属于当前账号。',"문의를 찾을 수 없습니다. 삭제되었거나 다른 계정의 문의일 수 있습니다."],
 ['sending','正在送出客服單……','Submitting ticket…','問い合わせを送信中…','正在提交客服单……',"문의를 보내는 중…"],
 ['sent','客服單已送出。','Ticket submitted.','問い合わせを送信しました。','客服单已提交。',"문의를 보냈습니다."],
 ['updated','客服單有新內容，請先保存或送出目前草稿，再重新開啟客服單查看。','This ticket has updates. Save or send your draft, then reopen the ticket to view them.','問い合わせが更新されました。下書きを保存または送信してから、問い合わせを開き直してください。','客服单有新内容，请先保存或提交当前草稿，再重新打开客服单查看。',"문의에 새 내용이 있습니다. 작성 중인 내용을 저장하거나 보낸 뒤 문의를 다시 열어 확인하세요."]
 ];
 api.languages.forEach((language,index)=>api.register(language,Object.fromEntries(rows.map(row=>['support.'+row[0],row[index+1]]))));
 const keys=new Map(rows.map(row=>[row[1],'support.'+row[0]]));window.MiloraSupportUI=Object.freeze({keyFor:value=>keys.get(value)});
 api.apply();
})();
