(function(){
 'use strict';
 const codes={'zh-Hant':'zh_tw',en:'en',ja:'ja','zh-Hans':'zh_cn'};
 const labels={
  'zh-Hant':{spoiler:'暴雷／反黑',sticker:'貼圖／GIF'},
  en:{spoiler:'Spoiler',sticker:'Stickers / GIF'},
  ja:{spoiler:'ネタバレ',sticker:'スタンプ／GIF'},
  'zh-Hans':{spoiler:'剧透／隐藏',sticker:'贴图／GIF'}
 };
 const language=()=>window.MiloraI18n?.getLanguage()||'zh-Hant';
 function nativeLanguage(){
  const current=language(),base=window.SUNEDITOR_LANG?.[codes[current]]||window.SUNEDITOR_LANG?.zh_tw||window.SUNEDITOR_LANG?.en;
  return current==='zh-Hant'?{...base,undo:'復原',redo:'重做',blockStyle:'段落格式',formats:'段落格式',tag_p:'一般段落',tag_h:'標題',font:'字型',fontSize:'字體大小',underline:'底線',lineHeight:'行距',bulletedList:'項目符號',numberedList:'編號清單',tag_blockquote:'引用',codeBlock:'程式碼區塊',codeView:'HTML 原始碼',fullScreen:'全螢幕'}:{...base};
 }
 function pluginTitle(key){return labels[language()]?.[key]||labels['zh-Hant'][key]}
 function bind(){
  // SunEditor 3.3.3 marks lang as fixed. Keep this editor's language and
  // undo history intact; the next page load uses the selected UI language.
  document.getElementById('guideEditorPanel').setAttribute('data-editor-language',language());
 }
 window.MiloraGuideEditorI18n=Object.freeze({nativeLanguage,pluginTitle,bind});
})();
