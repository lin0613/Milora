(function(){
 const api=window.MiloraI18n;if(!api)return;
 const rows=[
 ['unsupportedImage','只支援 JPG、PNG、WebP 或 GIF 圖片。','Only JPG, PNG, WebP or GIF images are supported.','JPG・PNG・WebP・GIF画像のみ対応しています。','仅支持 JPG、PNG、WebP 或 GIF 图片。'],
 ['imageLimit','單張圖片上限為 20 MB。','Each image must be no larger than 20 MB.','画像は1枚あたり20 MBまでです。','单张图片上限为20 MB。'],
 ['badImageUrl','圖片網址格式不正確。','Invalid image URL.','画像URLが正しくありません。','图片网址格式不正确。'],
 ['insertSticker','加入這張貼圖','Insert this sticker','このスタンプを挿入','添加这张贴图'],['uploadedStickerAlt','已上傳貼圖','Uploaded sticker','アップロード済みスタンプ','已上传贴图'],
 ['spoilerLabel','點擊顯示或隱藏反黑內容','Click to reveal or hide spoiler content','クリックでネタバレを表示・非表示','点击显示或隐藏剧透内容'],
 ['videoTitle','攻略影片','Guide video','攻略動画','攻略视频'],['noContent','目前沒有內容。','No content yet.','内容はまだありません。','目前没有内容。'],
 ['noCondition','未提供成就說明','No achievement description provided','実績の説明は未提供です','未提供成就说明'],
 ['guideTitle','成就攻略','Achievement guide','実績攻略','成就攻略'],
 ['unsupportedVideo','不支援的影片連結：{error}','Unsupported video link: {error}','未対応の動画リンク：{error}','不支持的视频链接：{error}'],
 ['discardFailed','無法捨棄舊草稿：{error}','Could not discard the old draft: {error}','古い下書きを破棄できません：{error}','无法丢弃旧草稿：{error}'],
 ['draftKeepOpen','草稿儲存失敗，編輯器會保持開啟：{error}','Draft save failed; the editor will remain open: {error}','下書き保存失敗。編集画面は開いたままになります：{error}','草稿保存失败，编辑器将保持打开：{error}'],
 ['draftSwitchFailed','草稿儲存失敗，無法切換投稿：{error}','Draft save failed; cannot switch submissions: {error}','下書きを保存できないため投稿を切り替えられません：{error}','草稿保存失败，无法切换投稿：{error}'],
 ['edit','編輯攻略','Edit guide','攻略を編集','编辑攻略'],['loginEdit','登入後編輯攻略','Sign in to edit guide','ログインして攻略を編集','登录后编辑攻略'],
 ['content','攻略內容','Guide content','攻略内容','攻略内容'],['emptyTitle','暫無攻略','No guide yet','攻略はまだありません','暂无攻略'],
 ['emptyHint','目前還沒有通過審查的攻略內容。','No approved guide is available yet.','審査を通過した攻略はまだありません。','目前还没有通过审核的攻略内容。'],
 ['loading','正在載入攻略……','Loading guide…','攻略を読み込み中…','正在加载攻略……'],
 ['closeEditor','關閉編輯','Close editor','編集を閉じる','关闭编辑'],['cancel','取消','Cancel','キャンセル','取消'],
 ['submit','送出審查','Submit for review','審査に提出','提交审核'],['preview','預覽文章','Preview article','記事をプレビュー','预览文章'],
 ['previewTitle','文章預覽','Article preview','記事プレビュー','文章预览'],['closePreview','關閉預覽','Close preview','プレビューを閉じる','关闭预览'],
 ['close','關閉','Close','閉じる','关闭'],['emoji','加入 Emoji','Insert emoji','絵文字を挿入','添加 Emoji'],
 ['sticker','貼圖／GIF','Stickers / GIF','スタンプ／GIF','贴图／GIF'],
 ['stickerHint','上傳後可在此瀏覽器重複使用；網站貼圖庫日後可加入素材。','Uploaded stickers can be reused in this browser. Site sticker assets can be added later.','アップロードしたスタンプはこのブラウザーで再利用できます。サイトの素材は後で追加できます。','上传后可在此浏览器重复使用；网站贴图库可在之后加入素材。'],
 ['uploadSticker','上傳貼圖或 GIF','Upload sticker or GIF','スタンプまたはGIFをアップロード','上传贴图或 GIF'],
 ['noStickers','目前沒有已儲存的貼圖。','No saved stickers.','保存済みのスタンプはありません。','目前没有已保存的贴图。'],
 ['submitHint','送出後狀態將變成「等待審查」，管理員核准前不會公開。','Submitted guides await review and remain private until approved.','提出後は審査待ちとなり、管理者の承認まで公開されません。','提交后状态为“等待审核”，管理员批准前不会公开。'],
 ['pending','等待審查','Awaiting review','審査待ち','等待审核'],['pendingHint','投稿已送出，管理員核准前不會公開。','Submission received. It remains private until approved.','投稿済みです。管理者の承認まで公開されません。','投稿已提交，管理员批准前不会公开。'],
 ['approved','已通過審查','Approved','審査通過','已通过审核'],['approvedHint','這個版本已通過審查。','This version has been approved.','この版は審査を通過しています。','这个版本已通过审核。'],
 ['rejected','需要修改','Changes requested','修正が必要','需要修改'],['rejectedHint','管理員已退回這份投稿，你可以修改後再次送出。','This submission was returned. Edit it and submit again.','投稿が差し戻されました。修正して再提出できます。','管理员已退回这份投稿，你可以修改后再次提交。'],
 ['draftUnsaved','草稿尚未儲存','Draft not saved','下書きは未保存です','草稿尚未保存'],
 ['draftSaving','正在儲存草稿…','Saving draft…','下書きを保存中…','正在保存草稿…'],
 ['draftSaved','草稿已儲存','Draft saved','下書きを保存しました','草稿已保存'],
 ['draftFailed','草稿儲存失敗','Draft save failed','下書きを保存できませんでした','草稿保存失败'],
 ['draftRestored','已恢復上次草稿','Previous draft restored','前回の下書きを復元しました','已恢复上次草稿'],
 ['draftHint','編輯內容會自動儲存為草稿','Edits are saved automatically as a draft','編集内容は下書きとして自動保存されます','编辑内容会自动保存为草稿'],
 ['badUrl','攻略網址不正確。','Invalid guide URL.','攻略のURLが正しくありません。','攻略网址不正确。'],
 ['editorFailed','攻略內容仍可閱讀，但編輯器載入失敗；請重新整理頁面。','The guide is readable, but the editor failed to load. Refresh the page.','攻略は読めますが、エディターを読み込めませんでした。ページを更新してください。','攻略内容仍可阅读，但编辑器加载失败；请刷新页面。'],
 ['waitClose','請等待圖片上傳完成，再關閉編輯器。','Wait for image uploads before closing the editor.','画像のアップロード完了後に編集を閉じてください。','请等待图片上传完成后再关闭编辑器。'],
 ['waitSubmit','請等待圖片上傳完成，再送出攻略。','Wait for image uploads before submitting.','画像のアップロード完了後に提出してください。','请等待图片上传完成后再提交攻略。'],
 ['waitPreview','請先等待圖片上傳完成，再預覽文章。','Wait for image uploads before previewing.','画像のアップロード完了後にプレビューしてください。','请等待图片上传完成后再预览文章。'],
 ['submitted','攻略已送出，投稿狀態為「等待審查」。','Guide submitted and awaiting review.','攻略を提出しました。審査待ちです。','攻略已提交，投稿状态为“等待审核”。'],
 ['uploadingSticker','正在上傳貼圖…','Uploading sticker…','スタンプをアップロード中…','正在上传贴图…'],
 ['uploadedSticker','上傳完成，可點選貼圖加入文章。','Upload complete. Select a sticker to insert it.','アップロード完了。スタンプを選んで挿入できます。','上传完成，可点击贴图添加到文章。'],
 ['words','字數：{count}','Character count: {count}','文字数：{count}','字数：{count}'],
 ['provider','提供者：{name}','Contributor: {name}','提供者：{name}','提供者：{name}'],
 ['author','投稿者：{name}','Author: {name}','投稿者：{name}','投稿者：{name}'],
 ['published','發布於 {date}','Published {date}','公開日時：{date}','发布于 {date}'],
 ['reviewNote','審查備註：{note}','Review note: {note}','審査コメント：{note}','审核备注：{note}'],
 ['uploadFailed','上傳失敗：{error}','Upload failed: {error}','アップロード失敗：{error}','上传失败：{error}'],
 ['previewFailed','文章預覽失敗：{error}','Preview failed: {error}','プレビュー失敗：{error}','文章预览失败：{error}'],
 ['draftError','草稿儲存失敗：{error}','Draft save failed: {error}','下書き保存失敗：{error}','草稿保存失败：{error}'],
 ['restore','找到上次未送出的攻略草稿。要恢復草稿嗎？\n按「取消」會捨棄舊草稿，使用目前已儲存的內容。','Restore your previous unsent draft?\nCancel discards the old draft and uses the current saved content.','前回の未提出の下書きを復元しますか？\nキャンセルすると古い下書きを破棄し、現在の保存済み内容を使用します。','找到上次未提交的攻略草稿。要恢复草稿吗？\n点击“取消”会丢弃旧草稿，使用当前已保存的内容。'],
 ['selectText','請先選取要套用的文字。','Select the text to format first.','先に書式を適用する文字を選択してください。','请先选择要应用格式的文字。'],
 ['selectSpoiler','請先選取要套用暴雷的文字。','Select the spoiler text first.','先にネタバレにする文字を選択してください。','请先选择要隐藏剧透的文字。']
 ];
 api.languages.forEach((language,index)=>api.register(language,Object.fromEntries(rows.map(row=>['guide.'+row[0],row[index+1]]))));
 const keys=new Map(rows.map(row=>[row[1],row[0]]));
 const patterns=[[/^字數：(\d+)$/,'words','count'],[/^提供者：(.*)$/s,'provider','name'],[/^投稿者：(.*)$/s,'author','name'],[/^發布於 (.*)$/s,'published','date'],[/^審查備註：(.*)$/s,'reviewNote','note'],[/^上傳失敗：(.*)$/s,'uploadFailed','error'],[/^文章預覽失敗：(.*)$/s,'previewFailed','error'],[/^草稿儲存失敗：(.*)$/s,'draftError','error']];
 patterns.push([/^不支援的影片連結：(.*)$/s,'unsupportedVideo','error'],[/^無法捨棄舊草稿：(.*)$/s,'discardFailed','error'],[/^草稿儲存失敗，編輯器會保持開啟：(.*)$/s,'draftKeepOpen','error'],[/^草稿儲存失敗，無法切換投稿：(.*)$/s,'draftSwitchFailed','error']);
 function translate(value){const key=keys.get(value);if(key)return api.t('guide.'+key);for(const [pattern,key,param] of patterns){const match=value.match(pattern);if(match)return api.t('guide.'+key,{[param]:param==='error'?translate(match[1]):match[1]})}return window.MiloraPublicText?.translate(value)||value}
 window.MiloraGuideUI=Object.freeze({translate});
 const selectors=['#guideEditButton','#guideEmptyEditButton','#guideNotice','#guideReadingSurface .guideSectionHeader h2',
 '#guideEmptyState h2','#guideEmptyState p','#guideEditorTitle','#guideCloseEditorButton','#guideEditorFooter',
 '.guideEditorFooter > p','#guideDraftStatus','#guideWordCount','#guidePreviewButton','#guideCancelEditorButton','#guideSubmitButton',
 '#guideSubmissionStateTitle','#guideSubmissionStateMessage','#guideSubmissionStateBadge','#guideProviderLine','#guidePublishedAt','#guideEditorProvider',
 '#guidePreviewDialog h2','#guideEmojiDialog h2','#guideStickerDialog h2','#guideStickerDialog .guideFieldHint','#guideStickerDialog label','#guideStickerGrid > p',
 '#guideAchievementCondition[data-guide-empty="true"]','#guidePreviewContent > [data-guide-empty="true"]','#guideAchievementMeta > span'];
 const original=new WeakMap();
 function update(node,attribute){const value=attribute?node.getAttribute(attribute):node.nodeValue;if(!value)return;
 let states=original.get(node);if(!states){states={};original.set(node,states)}const slot=attribute||'text',previous=states[slot];
 const source=previous&&value===previous.output?previous.source:value,trimmed=source.trim(),output=source.replace(trimmed,translate(trimmed));
 states[slot]={source,output};if(value!==output){if(attribute)node.setAttribute(attribute,output);else node.nodeValue=output}}
 function apply(){document.querySelectorAll(selectors.join(',')).forEach(el=>el.childNodes.forEach(node=>{if(node.nodeType===Node.TEXT_NODE)update(node)}));
 document.querySelectorAll('#guideClosePreviewButton,#guideCloseEmojiButton,#guideCloseStickerButton,#guideEditor,#guideEditorPanel .sun-editor-editable,.guideDocument .spoiler').forEach(el=>update(el,'aria-label'));
 document.querySelectorAll('iframe.guideVideo,#guideStickerGrid button').forEach(el=>update(el,'title'));
 document.querySelectorAll('#guideStickerGrid img').forEach(el=>update(el,'alt'))}
 apply();window.addEventListener('milora-language-change',apply);
 new MutationObserver(apply).observe(document.body,{subtree:true,childList:true,characterData:true});
})();
