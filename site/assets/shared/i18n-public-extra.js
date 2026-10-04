(function(){
 'use strict';
 const api=window.MiloraI18n;if(!api)return;
 const rows=[
 ['pullRefresh','下拉更新','Pull to refresh','引っ張って更新','下拉刷新'],
 ['releaseRefresh','放開即可更新','Release to refresh','離して更新','松开即可刷新'],
 ['refreshDraft','目前有未儲存的文字，仍要重新整理並放棄內容嗎？','You have unsaved text. Refresh and discard it?','未保存の文章があります。内容を破棄して更新しますか？','当前有未保存的文字，仍要刷新并放弃内容吗？'],
 ['accountTitle','帳號設定','Account settings','アカウント設定','账号设置'],
 ['redeemTitle','兌換碼','Redemption codes','交換コード','兑换码'],
 ['redeemPageTitle','遊戲兌換碼','Game redemption codes','ゲーム交換コード','游戏兑换码'],
 ['guideTitle','成就攻略','Achievement guide','実績攻略','成就攻略'],
 ['ticketAdmin','管理員','Administrator','管理者','管理员'],
 ['ticketUser','使用者','User','ユーザー','用户'],
 ['homeTitle','milora｜鳴潮、崩壞：星穹鐵道、原神、絕區零、異環','milora | Wuthering Waves, Honkai: Star Rail, Genshin Impact, Zenless Zone Zero, Neverness to Everness','milora | 鳴潮、崩壊：スターレイル、原神、ゼンレスゾーンゼロ、異環','milora｜鸣潮、崩坏：星穹铁道、原神、绝区零、异环'],
 ['miniReport','回報','Report','報告','报告'],
 ['miniHsr','崩鐵','HSR','スタレ','崩铁'],['miniSoon','期待','Soon','近日公開','期待'],
 ['wuwa','鳴潮','Wuthering Waves','鳴潮','鸣潮'],['genshin','原神','Genshin Impact','原神','原神'],
 ['hna','崩壞：因緣精靈','Honkai: Nexus Anima','崩壊：ネクサスアニマ','崩坏：因缘精灵'],['notBeta','尚未公測','Public beta not yet available','公開ベータ未開始','尚未公测'],
 ['endfield','明日方舟：終末地','Arknights: Endfield','アークナイツ：エンドフィールド','明日方舟：终末地'],
 ['progress','完成進度','Completion progress','達成状況','完成进度'],['done','已完成','Completed','達成済み','已完成'],
 ['achievementCount','／ {count} 項成就','/ {count} achievements','/ 実績 {count} 件','／ {count} 项成就'],
 ['pageTitle','milora','milora','milora','milora'],
 ['hsr','崩壞：星穹鐵道','Honkai: Star Rail','崩壊：スターレイル','崩坏：星穹铁道'],['zzz','絕區零','Zenless Zone Zero','ゼンレスゾーンゼロ','绝区零'],['nte','異環','Neverness to Everness','異環','异环'],
 ['recorder','成就紀錄器','Achievement tracker','実績トラッカー','成就记录器'],['games','遊戲','Games','ゲーム','游戏'],
 ['completion','全站完成度','Site completion rate','サイト全体の達成率','全站完成度'],
 ['stage','階段','Stages','段階','阶段'],['exclusive','互斥','Exclusive choices','排他','互斥'],
 ['rewardPrimo','原石 × {count}','Primogems × {count}','原石 × {count}','原石 × {count}'],
 ['rewardAstrite','星聲 × {count}','Astrite × {count}','星声 × {count}','星声 × {count}'],
 ['rewardJade','星瓊 × {count}','Stellar Jade × {count}','星玉 × {count}','星琼 × {count}'],
 ['rewardPoly','菲林 × {count}','Polychrome × {count}','ポリクローム × {count}','菲林 × {count}'],
 ['rewardNte','環石 × {count}','Rewards × {count}','報酬 × {count}','环石 × {count}'],
 ['loginNeeded','請先登入。','Please sign in.','ログインしてください。','请先登录。'],
 ['credentials','使用者名稱、電子信箱或密碼錯誤。','Incorrect username, email or password.','ユーザー名・メールアドレス・パスワードが正しくありません。','用户名、邮箱或密码错误。'],
 ['inactive','此帳號已被管理員停用。','This account has been disabled.','このアカウントは無効にされています。','此账号已被管理员停用。'],
 ['verifyNeeded','請先到信箱完成帳號驗證。','Verify your account through your email first.','先にメールでアカウントを確認してください。','请先到邮箱完成账号验证。'],
 ['rateLimit','操作太頻繁，請等待最多 5 分鐘後再試。','Too many attempts. Wait up to 5 minutes and try again.','操作回数が多すぎます。最大5分待ってから再試行してください。','操作过于频繁，请等待最多5分钟后再试。'],
 ['verifyInvalid','驗證連結無效或已過期。','The verification link is invalid or expired.','確認リンクが無効または期限切れです。','验证链接无效或已过期。'],
 ['usernameTaken','此使用者名稱已被使用。','This username is already taken.','このユーザー名は使用済みです。','此用户名已被使用。'],
 ['currentWrong','目前密碼錯誤。','Current password is incorrect.','現在のパスワードが正しくありません。','当前密码错误。'],
 ['resetInvalid','重設連結無效或已過期。','The reset link is invalid or expired.','再設定リンクが無効または期限切れです。','重置链接无效或已过期。'],
 ['passwordResetInvalid','密碼重設連結無效或已過期。','The password reset link is invalid or expired.','パスワード再設定リンクが無効または期限切れです。','密码重置链接无效或已过期。'],
 ['requestFailed','請求失敗（{status}）','Request failed ({status})','リクエストに失敗しました（{status}）','请求失败（{status}）'],
 ['verifyFailed','信箱驗證失敗：{error}','Email verification failed: {error}','メール確認に失敗しました：{error}','邮箱验证失败：{error}'],
 ['logoutFailed','登出失敗：{error}','Sign-out failed: {error}','ログアウトに失敗しました：{error}','退出失败：{error}'],
 ['loggingOut','登出中…','Signing out…','ログアウト中…','正在退出…'],['notFound','找不到此頁面。','Page not found.','ページが見つかりません。','找不到此页面。'],
 ['accountOffline','帳號服務未連線','Account service unavailable','アカウントサービスに接続できません','账号服务未连接'],
 ['deleteNotice','刪除通知','Delete notification','通知を削除','删除通知'],['deleteNoticeConfirm','確定要刪除這則通知嗎？','Delete this notification?','この通知を削除しますか？','确定删除这条通知吗？'],
 ['selectGame','遊戲選擇','Game selection','ゲーム選択','游戏选择'],['markLogo','共鳴波紋標誌','Resonance wave logo','共鳴の波紋ロゴ','共鸣波纹标志'],
 ['soon','敬請期待','Coming soon','近日公開','敬请期待'],['guide','攻略','Guide','攻略','攻略'],['report','回報問題','Report issue','問題を報告','报告问题'],
 ['rewardMissing','獎勵未標示','Reward not specified','報酬未記載','奖励未标注'],
 ['close','關閉','Close','閉じる','关闭'],['cancel','取消','Cancel','キャンセル','取消'],['understood','我知道了','Got it','確認しました','知道了'],
 ['reportTitle','回報成就資料問題','Report achievement data issue','実績データの問題を報告','报告成就数据问题'],
 ['type','問題類型','Issue type','問題の種類','问题类型'],['nameWrong','名稱錯誤','Incorrect name','名前が正しくない','名称错误'],
 ['conditionWrong','條件錯誤','Incorrect condition','条件が正しくない','条件错误'],['versionWrong','版本錯誤','Incorrect version','バージョンが正しくない','版本错误'],
 ['categoryWrong','分類錯誤','Incorrect category','分類が正しくない','分类错误'],['missing','缺少成就','Missing achievement','実績が不足','缺少成就'],['other','其他','Other','その他','其他'],
 ['details','詳細說明','Details','詳細','详细说明'],['reportSubmit','送出回報','Submit report','報告を送信','提交报告'],
 ['reported','回報已送出，管理員處理後會透過站內通知告知。','Report submitted. You will receive a site notification after review.','報告を送信しました。対応後にサイト内通知でお知らせします。','报告已提交，管理员处理后会通过站内通知告知。'],
 ['notifications','站內通知','Site notifications','サイト内通知','站内通知'],['notification','通知','Notifications','通知','通知'],['unread','未讀','Unread','未読','未读'],
 ['read','標為已讀','Mark as read','既読にする','标为已读'],['readAll','全部標為已讀','Mark all as read','すべて既読にする','全部标为已读'],['go','前往','Open','開く','前往'],
 ['noNotifications','目前沒有通知。','No notifications.','通知はありません。','目前没有通知。'],
 ['supportTitle','問題回報與客服單','Support tickets','お問い合わせ','问题报告与客服单'],['newTicket','建立新客服單','Create support ticket','新しい問い合わせを作成','创建客服单'],
 ['subject','主旨','Subject','件名','主题'],['description','問題說明','Describe the issue','問題の説明','问题说明'],['submit','送出','Submit','送信','提交'],
 ['tickets','我的客服單','My support tickets','自分の問い合わせ','我的客服单'],['reply','送出回覆','Send reply','返信する','发送回复'],['deleteTicket','刪除客服單','Delete ticket','問い合わせを削除','删除客服单'],
 ['pendingTicket','等待處理','Pending','対応待ち','等待处理'],['openTicket','處理中','In progress','対応中','处理中'],['resolvedTicket','已解決','Resolved','解決済み','已解决'],['closedTicket','已關閉','Closed','終了','已关闭'],
 ['replyHint','補充說明','Additional details','追加の説明','补充说明'],['noTickets','尚未建立客服單。','No support tickets yet.','問い合わせはまだありません。','尚未创建客服单。'],
 ['deleteConfirm','確定永久刪除此客服單及全部對話嗎？','Permanently delete this ticket and its entire conversation?','この問い合わせとすべての会話を完全に削除しますか？','确定永久删除此客服单及全部对话吗？'],
 ['choiceLocked','此互斥組已有其他成就被選擇；請先取消原選項','Another achievement in this exclusive group is selected. Deselect it first.','この排他グループでは別の実績が選択されています。先にその選択を解除してください。','此互斥组已有其他成就被选择；请先取消原选项'],
 ['navToggle','展開或收合遊戲選單','Expand or collapse game menu','ゲームメニューを開閉','展开或收起游戏菜单'],['toggle','展開或收合選單','Expand or collapse menu','メニューを開閉','展开或收起菜单'],
 ['saveFailed','進度儲存失敗：{error}','Progress save failed: {error}','進捗を保存できませんでした：{error}','进度保存失败：{error}'],
 ['bulkFailed','批次標註失敗：{error}','Bulk marking failed: {error}','一括チェックに失敗しました：{error}','批量标记失败：{error}'],
 ['clearFailed','批次清除失敗：{error}','Bulk clear failed: {error}','一括消去に失敗しました：{error}','批量清除失败：{error}'],
 ['importFailed','進度匯入失敗：{error}','Progress import failed: {error}','進捗のインポートに失敗しました：{error}','进度导入失败：{error}'],
 ['nothingDone','目前篩選結果沒有已完成的成就。','No completed achievements match these filters.','絞り込み結果に達成済みの実績はありません。','当前筛选结果没有已完成的成就。'],
 ['nothingMark','目前篩選結果沒有可直接標註的成就；未解鎖階段與尚未選擇的多項互斥組不會自動勾選。','No achievements can be marked. Locked stages and exclusive groups with multiple choices are not selected automatically.','チェックできる実績はありません。未解放の段階や複数候補の排他グループは自動で選択されません。','当前没有可直接标记的成就；未解锁阶段与未选择的多项互斥组不会自动勾选。'],
 ['guestImport','進度已匯入訪客紀錄；互斥與階段成就已依規則整理後匯入。','Progress imported into guest records with exclusive and stage rules applied.','排他・段階ルールに従ってゲストの進捗をインポートしました。','进度已导入访客记录；互斥与阶段成就已按规则整理。'],
 ['accountOwner','帳號「{email}」','account “{email}”','アカウント「{email}」','账号“{email}”'],['guestOwner','訪客','guest','ゲスト','访客'],
 ['accountImported','進度已匯入帳號「{email}」。','Progress imported into account “{email}”.','アカウント「{email}」に進捗をインポートしました。','进度已导入账号“{email}”。'],
 ['versionLabel','版本 {value}','Version {value}','バージョン {value}','版本 {value}'],['categoryLabel','分類：{value}','Category: {value}','分類：{value}','分类：{value}'],
 ['achievementLabel','成就：{value}','Achievement: {value}','実績：{value}','成就：{value}'],
 ['achievementId','成就 ID {value}','Achievement ID {value}','実績ID {value}','成就 ID {value}'],
 ['headerInfo','目前更新到{version}版本｜有bug請回報','Current version: {version} · Please report bugs','現在のバージョン：{version}・不具合を報告してください','当前更新到{version}版本｜有bug请报告'],
 ['markConfirm','確定將{owner}目前篩選結果中的 {count} 項成就標註為已完成嗎？{note}','Mark {count} filtered achievements as completed for {owner}?{note}','{owner}の絞り込み結果 {count} 件を達成済みにしますか？{note}','确定将{owner}当前筛选结果中的 {count} 项成就标记为已完成吗？{note}'],
 ['clearConfirm','確定清除{owner}目前篩選結果中的 {count} 項完成紀錄嗎？\n\n若包含階段成就，後續階段會依規則一併取消。','Clear {count} filtered completion records for {owner}?\n\nLater stages will also be cleared according to stage rules.','{owner}の絞り込み結果 {count} 件の達成記録を消去しますか？\n\n段階実績の後続段階もルールに従って解除されます。','确定清除{owner}当前筛选结果中的 {count} 项完成记录吗？\n\n后续阶段会按规则一并取消。'],
 ['skipStages','{count} 項未解鎖階段將略過','{count} locked stages will be skipped','未解放の段階 {count} 件をスキップ','将跳过 {count} 项未解锁阶段'],
 ['skipGroups','{count} 組含多個選項的互斥成就將略過','{count} exclusive groups with multiple choices will be skipped','複数候補の排他グループ {count} 組をスキップ','将跳过 {count} 组含多个选项的互斥成就']
 ];
 const keys=new Map(rows.map(row=>[row[1],row[0]]));
 for(const [index,code] of api.languages.entries())api.register(code,Object.fromEntries(rows.map(row=>['publicExtra.'+row[0],row[index+1]])));
 const patterns=[[/^進度儲存失敗：([\s\S]*)$/,'saveFailed','error'],[/^批次標註失敗：([\s\S]*)$/,'bulkFailed','error'],[/^批次清除失敗：([\s\S]*)$/,'clearFailed','error'],[/^進度匯入失敗：([\s\S]*)$/,'importFailed','error'],[/^版本 (.+)$/,'versionLabel','value'],[/^分類：(.+)$/,'categoryLabel','value'],[/^成就：(.+)$/,'achievementLabel','value'],[/^進度已匯入帳號「(.+)」。$/,'accountImported','email']];
 function t(key,params={}){return api.t('publicExtra.'+key,params)}
 function translate(value){const key=keys.get(value);if(key)return t(key);for(const [pattern,key,param] of patterns){const match=value.match(pattern);if(match)return t(key,{[param]:match[1]})}
  const ticketStates={pending:'pendingTicket',open:'openTicket',resolved:'resolvedTicket',closed:'closedTicket'};if(Object.hasOwn(ticketStates,value))return t(ticketStates[value]);
  const sender=value.match(/^(管理員|使用者)｜(.*)$/s);if(sender)return t(sender[1]==='管理員'?'ticketAdmin':'ticketUser')+'｜'+sender[2];
  let error=value.match(/^(信箱驗證失敗：|登出失敗：)([\s\S]*)$/);if(error)return t(error[1]==='信箱驗證失敗：'?'verifyFailed':'logoutFailed',{error:translate(error[2])});
  error=value.match(/^(?:請求|要求)失敗[（(](\d+)[）)]$/);if(error)return t('requestFailed',{status:error[1]});
  const reward=value.match(/^(原石|星聲|星瓊|菲林|環石) × (\d+)$/);if(reward)return t({'原石':'rewardPrimo','星聲':'rewardAstrite','星瓊':'rewardJade','菲林':'rewardPoly','環石':'rewardNte'}[reward[1]],{count:reward[2]});
  const completion=value.match(/^全站完成度 (.+%)$/);if(completion)return t('completion')+' '+completion[1];
  const count=value.match(/^／ ([\d,]+) 項成就$/);if(count)return t('achievementCount',{count:count[1]});
  const id=value.match(/^成就 ID (.+)$/);if(id)return t('achievementId',{value:id[1]});
  if(value.includes('｜milora'))return value.split('｜').map(part=>translate(part)).join(' | ');
  const match=value.match(/^目前更新到(.+)版本\s*[｜|]\s*有bug請回報$/);if(match)return t('headerInfo',{version:match[1]});
  const title=value.match(/^(鳴潮|原神|崩壞：星穹鐵道|崩鐵|絕區零|異環)成就紀錄器$/);if(title)return gameName({'鳴潮':'wuwa','原神':'genshin','崩鐵':'hsr','崩壞：星穹鐵道':'hsr','絕區零':'zzz','異環':'nte'}[title[1]],title[1])+' · '+t('recorder');return value}
 function gameName(id,fallback){const key=id==='wuthering-waves'?'wuwa':id;return ['wuwa','genshin','hsr','zzz','nte','hna','endfield'].includes(key)?t(key):fallback}
 window.MiloraPublicText=Object.freeze({translate,t,gameName});
 const game=document.body.classList.contains('gameProjectPage');
 const selectors=game?['header h1','header .top p','.gameNavText strong','.gameNavText small','.gameNavBrandText strong','.gameNavSectionTitle',
  '#list .achievementReportBtn','#list .achievementGuideBtn','#list .hiddenTag','#list .tag.version','#list .meta > .tag:not(.version):not(.customTag)','#list .reward',
  '#achievementReportDialog h2','#achievementReportForm label','#reportType option','#achievementReportForm button','#reportAchievementName','#achievementReportMessage',
  '#notificationDialog h2','#notificationDialog button','#userNotificationList .announcementLevelBadge','#userNotificationList .statusBadge','#userNotificationList .notificationLink','#userNotificationList .adminEmpty',
  '#supportDialog h2','#supportDialog h3','#closeSupportBtn','#supportCreateForm label','#supportCreateForm button','#mySupportList .listItemActions button','#mySupportList .adminEmpty','#mySupportList .statusBadge','#mySupportList .ticketMessage .sender',
  '#closeAchievementReportBtn','#sessionNoticeDialog button','#list .achievementCompletionText > span','#list .relatedGroupLabel']:['#accountProgressPanel .accountProgressName','#accountProgressPanel .accountProgressSub',
  '#accountNotificationList .accountNotificationLink','#accountNotificationList button','#accountNotificationList .announcementSummary h3 > span','#accountNotificationList .notificationEmpty',
  '#accountProgressPanel .accountProgressHeadLine > span','#accountProgressPanel .accountProgressCount','.stage .panel > h1','.stage .panel > .status'];
 const attrSelectors=game?['.gameNavItem','.gameNavText[data-mini-label]','.gameNavToggle','#gameSelectorPanel','#list .check','#list .achievementCompletion','#mySupportList .ticketUserReplyText']:[];
 const originals=new WeakMap();
 function update(node,attribute){const value=attribute?node.getAttribute(attribute):node.nodeValue;if(!value)return;let states=originals.get(node);if(!states){states={};originals.set(node,states)}
  const slot=attribute||'text',previous=states[slot],source=previous&&value===previous.output?previous.source:value,trimmed=source.trim(),output=source.replace(trimmed,translate(trimmed));states[slot]={source,output};
  if(value!==output){if(attribute)node.setAttribute(attribute,output);else node.nodeValue=output}}
 function apply(){document.querySelectorAll(selectors.join(',')).forEach(el=>el.childNodes.forEach(node=>{if(node.nodeType===Node.TEXT_NODE)update(node)}));
  document.querySelectorAll(attrSelectors.join(',')||':not(*)').forEach(el=>{for(const attr of ['title','aria-label','placeholder','data-mini-label'])update(el,attr)});
  const title=document.querySelector('title');if(title)title.childNodes.forEach(node=>update(node))}
 apply();window.addEventListener('milora-language-change',apply);
 new MutationObserver(apply).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder','data-mini-label']});
 const title=document.querySelector('title');if(title)new MutationObserver(apply).observe(title,{subtree:true,childList:true,characterData:true});
})();
