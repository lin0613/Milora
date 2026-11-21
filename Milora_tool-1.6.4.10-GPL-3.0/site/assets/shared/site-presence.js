(() => {
  'use strict';
  if (!document.getElementById('hub') || window.top !== window.self) return;
  const widgets = [...document.querySelectorAll('[data-site-presence]')];
  if (!widgets.length) return;
  const words = {
    'zh-Hant': {label: '目前瀏覽', count: '{count} 人', loading: '讀取中', unavailable: '暫時無法取得', hint: '最近 90 秒活躍瀏覽器的估算；同一瀏覽器多個分頁只計一次。'},
    'zh-Hans': {label: '当前浏览', count: '{count} 人', loading: '读取中', unavailable: '暂时无法获取', hint: '最近 90 秒活跃浏览器的估算；同一浏览器多个标签页只计一次。'},
    en: {label: 'Currently viewing', count: '{count} people', loading: 'Loading', unavailable: 'Unavailable', hint: 'Estimated active browsers in the last 90 seconds; tabs in the same browser count once.'},
    ja: {label: '現在閲覧中', count: '{count} 人', loading: '読み込み中', unavailable: '取得できません', hint: '過去90秒間のアクティブなブラウザーの推定数。同じブラウザーの複数タブは1件として数えます。'},
    ko: {label: '현재 열람 중', count: '{count}명', loading: '불러오는 중', unavailable: '확인할 수 없음', hint: '최근 90초 동안 활성 상태였던 브라우저의 추정 수입니다. 같은 브라우저의 여러 탭은 하나로 집계됩니다.'},
  };
  const i18n = window.MiloraI18n;
  if (i18n) for (const [language, values] of Object.entries(words)) {
    i18n.register(language, Object.fromEntries(Object.entries(values).map(([key, value]) => ['presence.' + key, value])));
  }
  const language = () => i18n?.getLanguage() || 'zh-Hant';
  const translate = (key, values = {}) => i18n ? i18n.t('presence.' + key, values) :
    Object.entries(values).reduce((text, [name, value]) => text.replace('{' + name + '}', value), words['zh-Hant'][key]);
  const storageKey = 'milora_site_presence_v1';
  const identifierPattern = /^[0-9a-f]{32}$/;
  let state = 'loading', count = null, timer = 0, controller = null, stopped = false;
  const setText = (element, value) => { if (element && element.textContent !== value) element.textContent = value; };
  const paint = () => {
    const value = state === 'ready' ? translate('count', {count: new Intl.NumberFormat(language()).format(count)}) : translate(state);
    for (const widget of widgets) {
      widget.dataset.presenceState = state;
      setText(widget.querySelector('[data-presence-label]'), translate('label'));
      setText(widget.querySelector('[data-presence-value]'), value);
      widget.title = translate('hint');
      widget.setAttribute('aria-label', translate('label') + ': ' + value + '. ' + translate('hint'));
    }
  };
  const storedIdentifier = () => {
    const stored = localStorage.getItem(storageKey);
    if (stored && stored.length === 32 && identifierPattern.test(stored)) return stored;
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const created = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
    localStorage.setItem(storageKey, created);
    return localStorage.getItem(storageKey);
  };
  const identifier = async () => {
    try {
      const value = navigator.locks?.request ? await navigator.locks.request(storageKey, storedIdentifier) : storedIdentifier();
      return typeof value === 'string' && value.length === 32 && identifierPattern.test(value) ? value : null;
    } catch (_) { return null; }
  };
  const schedule = delay => {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(refresh, delay);
  };
  const refresh = async () => {
    if (stopped || document.hidden || controller) return;
    const requestController = new AbortController();
    controller = requestController;
    const timeout = setTimeout(() => requestController.abort(), 6000);
    try {
      const visitorId = await identifier();
      if (requestController.signal.aborted || document.hidden || stopped) return;
      const response = await fetch(visitorId ? '/api/site-presence/heartbeat' : '/api/site-presence', {
        method: visitorId ? 'POST' : 'GET', credentials: 'omit', mode: 'same-origin', redirect: 'error', cache: 'no-store',
        headers: visitorId ? {'Content-Type': 'application/json'} : {},
        body: visitorId ? JSON.stringify({visitor_id: visitorId}) : undefined,
        signal: requestController.signal,
      });
      if (!response.ok) throw new Error('Presence unavailable');
      const payload = await response.json();
      if (!payload || payload.ok !== true || !Number.isSafeInteger(payload.count) || payload.count < 0 || payload.count > 10000) throw new Error('Invalid presence response');
      if (requestController.signal.aborted || document.hidden || stopped) return;
      count = payload.count;
      state = 'ready';
      paint();
    } catch (_) {
      if (!document.hidden && !stopped) {
        count = null;
        state = 'unavailable';
        paint();
      }
    } finally {
      clearTimeout(timeout);
      if (controller === requestController) controller = null;
      schedule(30000);
    }
  };
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { clearTimeout(timer); controller?.abort(); }
    else schedule(0);
  });
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); controller?.abort(); });
  window.addEventListener('pageshow', () => { stopped = false; schedule(0); });
  window.addEventListener('milora-language-change', paint);
  paint();
  schedule(0);
})();
