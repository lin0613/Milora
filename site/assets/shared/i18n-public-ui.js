(function () {
  'use strict';
  const i18n = window.MiloraI18n;
  if (!i18n) return;
  // These are application-owned UI strings. Authored content is deliberately outside the bindings below.
  const rows = [
    ['extra.reportNav','回報單','Support tickets','お問い合わせ','报告单'],
    ['extra.guideSubtitle','成就攻略','Achievement guide','実績攻略','成就攻略'],['extra.mobile','手機版','Mobile','モバイル','手机版'],
    ['extra.publicLinks','公開功能入口','Public features','公開機能','公开功能入口'],['extra.mobileNav','手機版主導覽','Mobile navigation','モバイルナビゲーション','手机版主导航'],
    ['extra.frameTitle','milora頁面','Game achievement tracker page','miloraページ','milora页面'],['extra.social','社群連結','Social links','ソーシャルリンク','社群链接'],
    ['extra.invalidResetFull','密碼重設連結無效或已過期。 請重新輸入信箱並申請新的密碼重設信。','The password reset link is invalid or expired. Enter your email to request a new reset email.','再設定リンクが無効または期限切れです。メールアドレスを入力して新しい再設定メールを申請してください。','密码重置链接无效或已过期。请重新输入邮箱并申请新的重置邮件。'],
    ['extra.retryLink','請稍後重新開啟郵件連結再試。','Try opening the email link again later.','後でもう一度メールのリンクを開いてください。','请稍后重新打开邮件链接再试。'],
    ['extra.homeIntro','目前支援鳴潮、崩壞：星穹鐵道、原神、絕區零與異環的成就查詢、紀錄、統計與攻略','Browse, track and view achievement statistics and guides for Wuthering Waves, Honkai: Star Rail, Genshin Impact, Zenless Zone Zero and Neverness to Everness.','鳴潮、崩壊：スターレイル、原神、ゼンレスゾーンゼロ、異環の実績検索・記録・統計・攻略に対応。','目前支持鸣潮、崩坏：星穹铁道、原神、绝区零与异环的成就查询、记录、统计与攻略'],
    ['extra.noUsername','尚未設定使用者名稱','Username not set','ユーザー名未設定','尚未设置用户名'],
    ['extra.resetUnavailable','暫時無法驗證重設連結','Reset link verification temporarily unavailable','再設定リンクを現在確認できません','暂时无法验证重置链接'],
    ['extra.emailVerified','信箱驗證完成，所有遊戲專案已自動登入。','Email verified. You are signed in across all game projects.','メールを確認しました。すべてのゲームプロジェクトにログインしました。','邮箱验证完成，所有游戏项目已自动登录。'],
    ['extra.resetNotVerified','密碼重設連結尚未通過驗證。','The reset link has not been verified.','再設定リンクがまだ確認されていません。','密码重置链接尚未通过验证。'],
    ['extra.usernameInvalid','使用者名稱至少 3 個字，且只能使用英文字母與數字。','Username must contain 3–30 letters or digits.','ユーザー名は3〜30文字の英数字にしてください。','用户名须为3–30个英文字母或数字。'],
    ['extra.savingUsername','正在儲存使用者名稱……','Saving username…','ユーザー名を保存中…','正在保存用户名……'],
    ['extra.passwordChanged','密碼更換成功。','Password changed.','パスワードを変更しました。','密码更改成功。'],
    ['extra.resetUpdated','密碼更新完成，請重新登入。','Password updated. Please sign in again.','パスワードを更新しました。再ログインしてください。','密码更新完成，请重新登录。'],
    ['extra.updatedIntro','密碼已更新，請使用新密碼登入。','Password updated. Sign in with your new password.','新しいパスワードでログインしてください。','密码已更新，请使用新密码登录。'],
    ['extra.mismatch','兩次輸入的密碼不一致。','Passwords do not match.','パスワードが一致しません。','两次输入的密码不一致。'],
    ['extra.resendLegacy','若帳號尚未驗證，新的驗證信將在幾分鐘內寄達。','If the account is unverified, a verification email will arrive within a few minutes.','未確認の場合は数分以内に確認メールが届きます。','若账号尚未验证，新的验证邮件将在几分钟内送达。'],
    ['extra.registerLegacy','註冊完成。請到信箱點擊驗證連結，再回來登入。','Registered. Open the verification link in your email, then sign in.','登録しました。メールの確認リンクを開いてからログインしてください。','注册完成。请到邮箱点击验证链接，再返回登录。'],
    ['extra.updatingPassword','正在更新密碼……','Updating password…','パスワードを更新中…','正在更新密码……'],
    ['extra.passwordUpdated','密碼更新完成。請使用新密碼登入。','Password updated. Sign in with your new password.','パスワードを更新しました。新しいパスワードでログインしてください。','密码更新完成。请使用新密码登录。'],
    ['extra.signInAgain','密碼已更新，請重新登入。','Password updated. Sign in again.','パスワードを更新しました。再ログインしてください。','密码已更新，请重新登录。'],
    ['extra.loginReport','請先登入再回報成就資料。','Sign in before reporting achievement data.','実績データを報告するにはログインしてください。','请先登录再报告成就数据。'],
    ['extra.sessionChanged','登入狀態已更新','Sign-in status changed','ログイン状態が更新されました','登录状态已更新'],
    ['site.name','milora','milora','milora','milora'],
    ['site.tagline','一個自製的成就紀錄器','A personal project for tracking game achievements','個人制作のmilora','一个自制的成就记录器'],
    ['site.description','支援鳴潮、崩壞：星穹鐵道、原神、絕區零與異環的成就查詢、完成紀錄、進度統計與攻略。','Browse achievements, track progress, and read guides for Wuthering Waves, Honkai: Star Rail, Genshin Impact, Zenless Zone Zero, and Neverness to Everness.','鳴潮、崩壊：スターレイル、原神、ゼンレスゾーンゼロ、NTEの実績検索、達成記録、進捗集計、攻略に対応。','支持鸣潮、崩坏：星穹铁道、原神、绝区零与异环的成就查询、完成记录、进度统计与攻略。'],
    ['site.usage','未登入即可瀏覽公開成就與攻略；登入後可保存個人的完成進度。另提供各遊戲兌換碼與兌換資訊查詢。','Browse public achievements and guides without signing in. Sign in to save your progress. Game redemption codes and redemption information are also available.','公開実績と攻略はログインせずに閲覧できます。ログインすると達成状況を保存できます。各ゲームの交換コードと交換情報も確認できます。','无需登录即可浏览公开成就与攻略；登录后可保存个人完成进度。另提供各游戏兑换码与兑换信息查询。'],
    ['nav.home','首頁','Home','ホーム','首页'],
    ['nav.games','遊戲','Games','ゲーム','游戏'],
    ['nav.features','功能','Features','機能','功能'],
    ['nav.redeem','兌換碼','Redemption codes','交換コード','兑换码'],
    ['nav.redeemHint','查看遊戲兌換碼','View game codes','ゲームの交換コードを見る','查看游戏兑换码'],
    ['nav.account','帳號設定','Account settings','アカウント設定','账号设置'],
    ['nav.accountHint','登入、註冊與帳號管理','Sign in, register, and manage your account','ログイン・登録・アカウント管理','登录、注册与账号管理'],
    ['nav.support','問題回報','Report an issue','問題を報告','问题反馈'],
    ['nav.supportHint','建立與查看客服單','Create and view support tickets','お問い合わせの作成・確認','创建与查看客服单'],
    ['nav.notifications','通知','Notifications','通知','通知'],
    ['nav.messageCenter','訊息中心','Message center','メッセージセンター','消息中心'],
    ['nav.login','登入／註冊','Sign in / Register','ログイン／登録','登录／注册'],
    ['nav.logout','登出','Sign out','ログアウト','退出登录'],
    ['nav.loading','正在載入頁面……','Loading page…','ページを読み込み中…','正在加载页面……'],
    ['nav.chooseGame','選擇遊戲','Choose a game','ゲームを選択','选择游戏'],
    ['nav.sidebar','收合或展開側邊欄','Collapse or expand sidebar','サイドバーを折りたたむ／展開','收起或展开侧边栏'],
    ['game.tracker','成就紀錄器','Achievement tracker','実績トラッカー','成就记录器'],
    ['game.soon','敬請期待','Coming soon','近日公開','敬请期待'],
    ['game.unavailable','成就紀錄器｜尚未開放','Achievement tracker | Not yet available','実績トラッカー｜未公開','成就记录器｜尚未开放'],
    ['game.wuwa','鳴潮','Wuthering Waves','鳴潮','鸣潮'],
    ['game.hsr','崩壞：星穹鐵道','Honkai: Star Rail','崩壊：スターレイル','崩坏：星穹铁道'],
    ['game.genshin','原神','Genshin Impact','原神','原神'],
    ['game.zzz','絕區零','Zenless Zone Zero','ゼンレスゾーンゼロ','绝区零'],
    ['game.nte','異環','Neverness to Everness','NTE','异环'],
    ['game.hna','崩壞：因緣精靈','Honkai: Nexus Anima','崩壊：ネクサスアニマ','崩坏：因缘精灵'],
    ['link.wuwa','鳴潮成就','Wuthering Waves','鳴潮の実績','鸣潮成就'],
    ['link.hsr','崩壞：星穹鐵道成就','Honkai: Star Rail','スターレイルの実績','崩坏：星穹铁道成就'],
    ['link.genshin','原神成就','Genshin Impact','原神の実績','原神成就'],
    ['link.zzz','絕區零成就','Zenless Zone Zero','ゼンゼロの実績','绝区零成就'],
    ['link.nte','異環成就','Neverness to Everness','NTEの実績','异环成就'],
    ['auth.start','登入或註冊','Sign in or register','ログインまたは登録','登录或注册'],
    ['auth.login','登入','Sign in','ログイン','登录'],
    ['auth.register','註冊','Register','新規登録','注册'],
    ['auth.create','建立帳號','Create account','アカウントを作成','创建账号'],
    ['auth.identifier','使用者名稱或電子信箱','Username or email','ユーザー名またはメールアドレス','用户名或电子邮箱'],
    ['auth.email','電子信箱','Email','メールアドレス','电子邮箱'],
    ['auth.password','密碼','Password','パスワード','密码'],
    ['auth.minPassword','至少 8 個字元','At least 8 characters','8文字以上','至少 8 个字符'],
    ['auth.forgot','忘記密碼？','Forgot password?','パスワードを忘れた場合','忘记密码？'],
    ['auth.resend','重新寄送驗證信','Resend verification email','確認メールを再送','重新发送验证邮件'],
    ['auth.show','顯示密碼','Show password','パスワードを表示','显示密码'],
    ['auth.hide','隱藏密碼','Hide password','パスワードを隠す','隐藏密码'],
    ['auth.cancel','取消','Cancel','キャンセル','取消'],
    ['auth.close','關閉','Close','閉じる','关闭'],
    ['auth.username','使用者名稱','Username','ユーザー名','用户名'],
    ['auth.setUsername','設定使用者名稱','Set username','ユーザー名を設定','设置用户名'],
    ['auth.changeUsername','更改使用者名稱','Change username','ユーザー名を変更','更改用户名'],
    ['auth.saveUsername','儲存使用者名稱','Save username','ユーザー名を保存','保存用户名'],
    ['auth.usernameHint','使用者名稱限用英文與數字，長度不得少於 3 個字元。','Use letters and numbers only, with at least 3 characters.','ユーザー名は英数字のみで、3文字以上にしてください。','用户名仅限英文字母和数字，长度不少于 3 个字符。'],
    ['auth.usernameExample','例如 Ace123','For example, Ace123','例：Ace123','例如 Ace123'],
    ['auth.changePassword','更換密碼','Change password','パスワードを変更','更改密码'],
    ['auth.currentPassword','目前密碼','Current password','現在のパスワード','当前密码'],
    ['auth.enterCurrent','輸入目前密碼','Enter current password','現在のパスワードを入力','输入当前密码'],
    ['auth.newPassword','新密碼','New password','新しいパスワード','新密码'],
    ['auth.confirmPassword','再次輸入新密碼','Confirm new password','新しいパスワードを再入力','再次输入新密码'],
    ['auth.confirmChange','確認更換密碼','Confirm password change','パスワードの変更を確定','确认更改密码'],
    ['auth.updatePassword','更新密碼','Update password','パスワードを更新','更新密码'],
    ['auth.resetPassword','重設密碼','Reset password','パスワードを再設定','重置密码'],
    ['auth.sendReset','寄送重設郵件','Send reset email','再設定メールを送信','发送重置邮件'],
    ['auth.resetInstructions','請輸入註冊時使用的電子信箱，我們會寄送密碼重設連結。','Enter the email used to register. We will send a password reset link.','登録したメールアドレスを入力してください。パスワード再設定リンクを送信します。','请输入注册时使用的邮箱，我们会发送密码重置链接。'],
    ['auth.cannotReset','無法重設密碼','Unable to reset password','パスワードを再設定できません','无法重置密码'],
    ['auth.invalidReset','此密碼重設連結無效、已使用或已過期。請重新申請密碼重設信。','This reset link is invalid, already used, or expired. Request a new reset email.','このリンクは無効、使用済み、または期限切れです。再設定メールを再度リクエストしてください。','此密码重置链接无效、已使用或已过期。请重新申请密码重置邮件。'],
    ['auth.returnLogin','返回登入','Back to sign in','ログインに戻る','返回登录'],
    ['auth.loggedIn','帳號已登入','Signed in','ログイン済み','账号已登录'],
    ['auth.owner','站長','Site owner','サイト管理者','站长'],
    ['auth.admin','管理員','Administrator','管理者','管理员'],
    ['auth.member','一般用戶','Member','一般ユーザー','普通用户'],
    ['auth.checkReset','正在驗證重設連結','Checking reset link','再設定リンクを確認中','正在验证重置链接'],
    ['auth.checkResetHint','正在確認此連結是否仍然有效，請稍候……','Checking whether this link is still valid. Please wait…','リンクの有効性を確認しています。しばらくお待ちください…','正在确认此链接是否仍有效，请稍候……'],
    ['auth.setNew','設定新密碼','Set a new password','新しいパスワードを設定','设置新密码'],
    ['auth.resetValid','連結有效。更新後，所有舊登入階段都會失效。','Link verified. Updating your password will invalidate all previous sessions.','リンクを確認しました。更新すると、以前のログインセッションはすべて無効になります。','链接有效。更新后，所有旧登录会话都会失效。'],
    ['auth.checkEmail','正在驗證信箱','Verifying email','メールアドレスを確認中','正在验证邮箱'],
    ['auth.checkEmailHint','正在確認郵件連結，請稍候……','Checking the email link. Please wait…','メールのリンクを確認しています。しばらくお待ちください…','正在确认邮件链接，请稍候……'],
    ['auth.validEmail','請輸入有效的電子信箱。','Enter a valid email address.','有効なメールアドレスを入力してください。','请输入有效的电子邮箱。'],
    ['auth.enterIdentifier','請輸入使用者名稱或電子信箱。','Enter your username or email.','ユーザー名またはメールアドレスを入力してください。','请输入用户名或电子邮箱。'],
    ['auth.passwordShort','密碼至少需要 8 個字元。','Password must be at least 8 characters.','パスワードは8文字以上にしてください。','密码至少需要 8 个字符。'],
    ['auth.creating','正在建立帳號並寄送驗證信……','Creating account and sending verification email…','アカウントを作成し、確認メールを送信しています…','正在创建账号并发送验证邮件……'],
    ['auth.signingIn','正在登入……','Signing in…','ログイン中…','正在登录……'],
    ['auth.registerSent','如果這是新信箱，請到信箱點擊驗證連結；若未收到，請查看垃圾郵件。已有帳號可直接登入或重設密碼。','If this is a new email address, check your inbox for the verification link, including spam. Existing accounts can sign in or reset their password.','新規メールアドレスの場合は、受信箱の確認リンクを開いてください。迷惑メールもご確認ください。既存のアカウントはログインまたはパスワードの再設定ができます。','如果这是新邮箱，请到邮箱点击验证链接；未收到时请检查垃圾邮件。已有账号可直接登录或重置密码。'],
    ['auth.success','登入成功。','Signed in successfully.','ログインしました。','登录成功。'],
    ['auth.sendingReset','正在寄送密碼重設信……','Sending password reset email…','パスワード再設定メールを送信中…','正在发送密码重置邮件……'],
    ['auth.resetSent','若此信箱已註冊，密碼重設信將在幾分鐘內寄達。請一併查看垃圾郵件。','If this email is registered, a reset email should arrive within a few minutes. Also check spam.','登録済みのメールアドレスであれば、数分以内に再設定メールが届きます。迷惑メールもご確認ください。','若此邮箱已注册，密码重置邮件将在几分钟内送达。请同时检查垃圾邮件。'],
    ['auth.resendEmailRequired','請先輸入有效的電子信箱。','Enter a valid email address first.','先に有効なメールアドレスを入力してください。','请先输入有效的电子邮箱。'],
    ['auth.verificationSent','若帳號尚未驗證，新的驗證信將在幾分鐘內寄達；若未收到，請查看垃圾郵件。','If your account is unverified, a new verification email should arrive within a few minutes. Check spam if it does not arrive.','未確認のアカウントには、数分以内に新しい確認メールが届きます。届かない場合は迷惑メールをご確認ください。','若账号尚未验证，新的验证邮件将在几分钟内送达；未收到时请检查垃圾邮件。'],
    ['auth.usernameSaved','使用者名稱已更新。','Username updated.','ユーザー名を更新しました。','用户名已更新。'],
    ['auth.currentShort','目前密碼至少需要 8 個字元。','Current password must be at least 8 characters.','現在のパスワードは8文字以上にしてください。','当前密码至少需要 8 个字符。'],
    ['auth.newShort','新密碼至少需要 8 個字元。','New password must be at least 8 characters.','新しいパスワードは8文字以上にしてください。','新密码至少需要 8 个字符。'],
    ['auth.mismatch','兩次輸入的新密碼不一致。','The new passwords do not match.','新しいパスワードが一致しません。','两次输入的新密码不一致。'],
    ['auth.samePassword','新密碼不可與目前密碼相同。','New password must differ from your current password.','現在のパスワードと異なるパスワードにしてください。','新密码不能与当前密码相同。'],
    ['auth.changing','正在更換密碼……','Changing password…','パスワードを変更中…','正在更改密码……'],
    ['account.progress','遊戲完成率','Game completion','ゲーム達成率','游戏完成率'],
    ['account.progressHint','每款遊戲獨立顯示目前已完成的成就','Completed achievements are shown separately for each game.','達成済みの実績をゲームごとに表示します。','每款游戏独立显示当前已完成的成就'],
    ['account.loadingProgress','正在載入遊戲進度……','Loading game progress…','ゲームの進捗を読み込み中…','正在加载游戏进度……'],
    ['account.noProgress','目前沒有可顯示的遊戲進度。','No game progress to display.','表示できるゲームの進捗はありません。','目前没有可显示的游戏进度。'],
    ['account.notifications','站內通知','Site notifications','サイト内通知','站内通知'],
    ['account.readAll','全部標為已讀','Mark all as read','すべて既読にする','全部标为已读'],
    ['account.loadingNotifications','正在載入通知……','Loading notifications…','通知を読み込み中…','正在加载通知……'],
    ['nav.accountShort','帳號','Account','アカウント','账号'],
    ['nav.accountGuest','登入、註冊與帳號管理','Sign in, register and manage your account','ログイン・登録・アカウント管理','登录、注册与账号管理'],
    ['nav.accountSubtitle','登入與帳號管理','Sign in and manage your account','ログイン・アカウント管理','登录与账号管理'],
    ['account.noNotifications','目前沒有通知。','No notifications.','通知はありません。','目前没有通知。'],
    ['auth.passwordChanged','密碼更換成功。','Password changed.','パスワードを変更しました。','密码更改成功。'],
    ['auth.signingOut','正在登出所有專案……','Signing out of all projects…','すべてのプロジェクトからログアウト中…','正在退出所有项目……'],
    ['auth.signedOut','已登出，請重新登入。','Signed out. Please sign in again.','ログアウトしました。再度ログインしてください。','已退出，请重新登录。'],
    ['auth.savingUsername','正在儲存使用者名稱……','Saving username…','ユーザー名を保存中…','正在保存用户名……'],
    ['auth.usernameInvalid','使用者名稱至少 3 個字，且只能使用英文字母與數字。','Username must contain 3–30 letters or numbers.','ユーザー名は英数字3～30文字で入力してください。','用户名必须为3～30个英文字母或数字。'],
    ['auth.resetMismatch','兩次輸入的密碼不一致。','Passwords do not match.','パスワードが一致しません。','两次输入的密码不一致。'],
    ['auth.resetDone','密碼更新完成，請重新登入。','Password updated. Please sign in again.','パスワードを更新しました。再度ログインしてください。','密码已更新，请重新登录。'],
    ['auth.resetIntro','密碼已更新，請使用新密碼登入。','Password updated. Sign in with your new password.','新しいパスワードでログインしてください。','密码已更新，请使用新密码登录。']
  ];
  const literalKeys = new Map(rows.map(row => [row[1], row[0]]));
  for (let index = 0; index < i18n.languages.length; index++) {
    i18n.register(i18n.languages[index], Object.fromEntries(rows.map(row => [row[0], row[index + 1]])));
  }
  function translate(value) {
    const key = literalKeys.get(value);
    if(value==='尚未設定使用者名稱')return i18n.t('extra.noUsername');
    const retrySuffix=' 請稍後重新開啟郵件連結再試。';
    if(value.endsWith(retrySuffix)){const error=value.slice(0,-retrySuffix.length);return (window.MiloraPublicText?.translate(error)||error)+' '+i18n.t('extra.retryLink')}
    return key ? i18n.t(key) : window.MiloraPublicText?.translate(value)||value;
  }
  window.MiloraUI = Object.freeze({translate});
  const isHub = Boolean(document.getElementById('hub'));
  const isAccount = Boolean(document.getElementById('authForm'));
  const selectors = isHub ? [
    '.brandTitle strong', '#homeBtn .navText strong', '#homeBtn .navText small', '.sectionTitle',
    '#supportBtn .navText strong', '#supportBtn .navText small', '#redeemBtn .navText strong', '#redeemBtn .navText small',
    '#accountBtn .navText strong', '#loginBtn', '#logoutBtn', '#loading', '#notificationHubBtn > span',
    '#indexableHomeIntro h1', '#indexableHomeIntro p', '#indexableHomeIntro a',
    '#gameList .navText strong', '#gameList .navText small', '#mobileGameList strong', '#mobileGameList small',
    '#mobileBottomNav span', '#mobileCurrentTitle', '#mobileGameSheet h2', '#accountStatus', '#mobileCurrentSubtitle'
  ] : isAccount ? [
    '.hero h1', '#mainTitle', '#mainIntro', '#guestView button', '#guestView label',
    '#identifierLabel', '#accountView > .actions button', '#usernameTitle', '#usernameForm label',
    '#usernameForm .fieldHint', '#usernameForm button', '#changePasswordTitle', '#changePasswordForm label',
    '#changePasswordForm button', '#resetPanel label', '#resetPanel button', '#forgotPasswordTitle',
    '#forgotPasswordPanel .notice', '#forgotPasswordForm label', '#forgotPasswordForm button',
    '#resetLinkInvalidTitle', '#resetLinkInvalidConfirmBtn', '#resetLinkInvalidMessage', '#accountRole',
    '#accountNotificationTitle', '#accountNotificationReadAllBtn', '#accountProgressTitle',
    '#accountProgressPanel .accountProgressHead p', '.accountProgressEmpty', '.notificationEmpty',
    '#authMessage', '#accountMessage', '#usernameMessage', '#changePasswordMessage', '#resetMessage',
    '#forgotPasswordMessage', '#externalMessage', '#authTitle', '#authIntro', '#authSubmitBtn', '#registerLink', '#forgotBtn', '#resendVerificationBtn',
    '#authForm label', '#authForm button', '#closeAuthBtn', '#forgotPasswordDialog h2', '#forgotPasswordDialog .small', '#forgotPasswordForm button',
    '#resetDialog h2', '#resetDialog .small', '#resetForm label', '#resetForm button', '#sessionNoticeTitle', '#accountNotificationMessage'
  ] : ['#intro h1', '#intro p'];
  const attributeSelectors = isHub ? ['#homeBtn .navText', '#supportBtn .navText', '#redeemBtn .navText', '#accountBtn .navText', '#gameList .navText', '#gameList .navItem', '#toggle', '#mobileCurrentPageBtn', '#mobileNotificationBtn', '#notificationHubBtn', '#indexableHomeIntro nav', '#mobileBottomNav', '#projectFrame', '.sidebarSocialLinks', '#mobileHomeSocialLinks'] :
    isAccount ? ['#authForm input', '#usernameInput', '#changePasswordForm input', '#resetForm input', '.passwordToggle', '.changePasswordClose'] : [];
  const originals = new WeakMap();
  function update(node, attribute) {
    const read = () => attribute ? node.getAttribute(attribute) : node.nodeValue;
    const value = read();
    if (!value) return;
    const slot = attribute || 'text';
    let state = originals.get(node);
    if (!state) { state = {}; originals.set(node, state); }
    const previous = state[slot];
    const source = previous && value === previous.output ? previous.source : value;
    const trimmed = source.trim();
    const output = source.replace(trimmed, translate(trimmed));
    state[slot] = {source, output};
    if (value !== output) {
      if (attribute) node.setAttribute(attribute, output); else node.nodeValue = output;
    }
  }
  function applyUI() {
    document.querySelectorAll(selectors.join(',')).forEach(element => {
      // Direct UI text only: no descent into user-generated content or input values.
      element.childNodes.forEach(node => { if (node.nodeType === Node.TEXT_NODE) update(node); });
    });
    if (isAccount) document.querySelectorAll('#identifierLabel').forEach(element => element.childNodes.forEach(node => update(node)));
    if (attributeSelectors.length) document.querySelectorAll(attributeSelectors.join(',')).forEach(element => {
      for (const attribute of ['placeholder', 'title', 'aria-label', 'data-mini-label']) update(element, attribute);
    });
    if (isHub) {
      // Only translate the fixed guest labels; authenticated usernames remain untouched.
      for (const id of ['accountStatus','mobileCurrentSubtitle']) {
        const element = document.getElementById(id);
        if (element) {
          element.childNodes.forEach(node => {
            const prior = originals.get(node)?.text;
            const source = prior && node.nodeValue === prior.output ? prior.source : node.nodeValue;
            if (source === '登入、註冊與帳號管理' || source === '登入與帳號管理') update(node);
          });
        }
      }
    }
  }
  applyUI();
  window.addEventListener('milora-language-change', applyUI);
  // Observe UI updates, then translate only the explicit selector allowlist above.
  // Our own updates reach a fixed point because output strings are tracked per node.
  new MutationObserver(applyUI).observe(document.body, {subtree:true, childList:true, characterData:true, attributes:true,
    attributeFilter:['placeholder','aria-label','title','data-mini-label']});
})();
