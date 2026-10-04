(function () {
  'use strict';
  if (window.MiloraI18n) return;
  const languages = Object.freeze(['zh-Hant', 'en', 'ja', 'zh-Hans']);
  const storageKey = 'milora_language';
  const labels = {'zh-Hant': '繁體中文', en: 'English', ja: '日本語', 'zh-Hans': '简体中文'};
  const dictionaries = {
    'zh-Hant': {'language.label': '語言'},
    en: {'language.label': 'Language'},
    ja: {'language.label': '言語'},
    'zh-Hans': {'language.label': '语言'}
  };
  const isLanguage = value => languages.includes(value);
  function detectLanguage() {
    for (const value of navigator.languages || [navigator.language || '']) {
      const tag = String(value).toLowerCase();
      if (/^en(?:-|$)/.test(tag)) return 'en';
      if (/^ja(?:-|$)/.test(tag)) return 'ja';
      if (/^zh(?:-|$)/.test(tag)) return /(?:hans|cn|sg)/.test(tag) ? 'zh-Hans' : 'zh-Hant';
    }
    return 'zh-Hant';
  }
  function storedLanguage() {
    try {
      const value = localStorage.getItem(storageKey);
      return isLanguage(value) ? value : null;
    } catch { return null; }
  }
  let language = storedLanguage() || detectLanguage();
  function fallbackChain(value = language) {
    return [...new Set([isLanguage(value) ? value : 'zh-Hant', 'zh-Hant', 'zh-Hans'])];
  }
  function localized(values, value = language) {
    for (const code of fallbackChain(value)) {
      const text = values && Object.prototype.hasOwnProperty.call(values, code) ? values[code] : null;
      if (typeof text === 'string' && text.trim()) return text;
    }
    return '';
  }
  function t(key, parameters = {}) {
    const values = {};
    for (const code of languages) {
      if (Object.prototype.hasOwnProperty.call(dictionaries[code], key)) values[code] = dictionaries[code][key];
    }
    return (localized(values) || key).replace(/\{([A-Za-z0-9_]+)\}/g, (match, name) =>
      Object.prototype.hasOwnProperty.call(parameters, name) ? String(parameters[name]) : match);
  }
  function apply(root = document) {
    root.querySelectorAll('[data-i18n]').forEach(element => {
      const key = element.dataset.i18n;
      const text = t(key);
      // Only explicitly marked, text-only UI nodes. Form values and authored content are never translated.
      if (text !== key && !element.children.length && !element.matches('input,textarea')) element.textContent = text;
    });
    for (const attribute of ['title', 'placeholder', 'aria-label']) {
      root.querySelectorAll(`[data-i18n-${attribute}]`).forEach(element => {
        const key = element.getAttribute(`data-i18n-${attribute}`);
        const text = t(key);
        if (text !== key) element.setAttribute(attribute, text);
      });
    }
    root.querySelectorAll('[data-language-select]').forEach(select => {
      select.value = language;
      select.setAttribute('aria-label', t('language.label'));
      select.parentElement.title = `${t('language.label')} · ${labels[language]}`;
    });
  }
  function sendToFrame() {
    const frame = document.getElementById('projectFrame');
    try { frame?.contentWindow?.postMessage({type: 'milora-language-changed', language}, location.origin); } catch {}
  }
  function setLanguage(value, {persist = true, notify = true} = {}) {
    if (!isLanguage(value)) return false;
    const changed = value !== language;
    language = value;
    if (persist) try { localStorage.setItem(storageKey, value); } catch {}
    // The page is not fully translated until individual surfaces register their dictionaries.
    document.documentElement.dataset.uiLanguage = language;
    apply();
    if (notify) sendToFrame();
    if (changed) window.dispatchEvent(new CustomEvent('milora-language-change', {detail: {language}}));
    return true;
  }
  function register(code, values) {
    if (!isLanguage(code) || !values || typeof values !== 'object') return false;
    for (const [key, value] of Object.entries(values)) {
      if (typeof value === 'string' && !['__proto__', 'constructor', 'prototype'].includes(key)) dictionaries[code][key] = value;
    }
    apply();
    return true;
  }
  window.MiloraI18n = Object.freeze({languages, labels: Object.freeze(labels), storageKey,
    getLanguage: () => language, detectLanguage, fallbackChain, localized, t, register, apply, setLanguage});
  window.addEventListener('storage', event => {
    if (event.key === storageKey && (event.newValue === null || isLanguage(event.newValue))) {
      setLanguage(event.newValue || detectLanguage(), {persist: false});
    }
  });
  window.addEventListener('message', event => {
    if (event.origin !== location.origin) return;
    const frame = document.getElementById('projectFrame');
    if (event.data?.type === 'milora-language-ready' && frame && event.source === frame.contentWindow) sendToFrame();
    if (window.parent !== window && event.source === window.parent && event.data?.type === 'milora-language-changed' && isLanguage(event.data.language)) {
      setLanguage(event.data.language, {persist: false, notify: false});
    }
  });
  function start() {
    function makePicker(className, selectClass = '') {
      const label = document.createElement('label');
      label.className = `languagePicker ${className}`;
      label.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 4 6 4 9s-1 6-4 9c-3-3-4-6-4-9s1-6 4-9Z"/></svg>';
      const select = document.createElement('select');
      select.className = selectClass;
      select.setAttribute('data-language-select', '');
      label.append(select);
      return label;
    }
    document.querySelector('.content')?.append(makePicker('desktopLanguagePicker'));
    const mobileBar = document.getElementById('mobileAppBar');
    if (mobileBar) {
      mobileBar.insertBefore(makePicker('mobileLanguageButton', 'mobileLanguagePicker'), document.getElementById('mobileNotificationBtn'));
    }
    document.querySelectorAll('[data-language-select]').forEach(select => {
      for (const code of languages) {
        const option = document.createElement('option');
        option.value = code;
        option.textContent = labels[code];
        select.append(option);
      }
      select.addEventListener('change', () => setLanguage(select.value));
    });
    document.getElementById('projectFrame')?.addEventListener('load', sendToFrame);
    setLanguage(language, {persist: false});
    if (window.parent !== window) try { window.parent.postMessage({type: 'milora-language-ready'}, location.origin); } catch {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
