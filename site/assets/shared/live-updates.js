(() => {
  'use strict';
  const listeners = new Set();
  let pending = 0;
  const notify = () => {
    if (pending) clearTimeout(pending);
    pending = setTimeout(() => {
      pending = 0;
      window.dispatchEvent(new Event('milora:data-changed'));
      for (const listener of [...listeners]) {
        try { listener(); } catch (error) { console.warn('即時資料更新失敗', error); }
      }
    }, 150);
  };
  window.MiloraLive = {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    refresh: notify,
  };
  // IIS/ARR cannot safely carry a persistent stream in this site's app pool.
  // Poll only the tiny revision marker; regular page data is loaded on change.
  const revisionUrl = location.pathname.startsWith('/api/private/') ? '/api/live-revision?private=true' : '/api/live-revision';
  let revision = null;
  let timer = 0;
  let controller = null;
  let stopped = false;
  let disconnected = false;
  const schedule = delay => {
    if (stopped || document.hidden) return;
    clearTimeout(timer);
    timer = setTimeout(checkRevision, delay);
  };
  const checkRevision = async () => {
    if (stopped || document.hidden || controller) return;
    controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    let delay = 1000;
    try {
      const response = await fetch(revisionUrl, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error(`Revision request failed: ${response.status}`);
      const next = String((await response.json()).revision ?? '');
      if (!next) throw new Error('Revision response is empty');
      if (revision !== null && revision !== next) notify();
      revision = next;
      if (disconnected) window.dispatchEvent(new Event('milora:live-connected'));
      disconnected = false;
    } catch (error) {
      delay = 3000;
      if (!disconnected) window.dispatchEvent(new Event('milora:live-disconnected'));
      disconnected = true;
    } finally {
      clearTimeout(timeout);
      controller = null;
      schedule(delay);
    }
  };
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(timer);
    else schedule(0);
  });
  window.addEventListener('pagehide', () => {
    stopped = true;
    clearTimeout(timer);
    controller?.abort();
  }, { once: true });
  schedule(0);

  if (!matchMedia('(pointer: coarse)').matches) return;
  document.documentElement.style.overscrollBehaviorY = 'contain';
  const hint = document.createElement('div');
  hint.setAttribute('role', 'status');
  hint.setAttribute('data-live-refresh-hint', '');
  hint.style.cssText = 'position:fixed;top:12px;left:50%;z-index:2147483647;transform:translate(-50%,-150%);padding:9px 16px;border-radius:999px;background:#18313b;color:#efffff;box-shadow:0 8px 24px #0008;font:700 13px system-ui;pointer-events:none;transition:transform .2s';
  const translate = text => window.MiloraPublicText?.translate(text) || text;
  let hintSource = '下拉更新';
  const updateHint = () => { hint.textContent = translate(hintSource); };
  updateHint();
  window.addEventListener('milora-language-change', updateHint);
  document.addEventListener('DOMContentLoaded', () => document.body.append(hint), { once: true });
  let startY = 0, startX = 0, pulling = false, distance = 0;
  const atTop = target => {
    for (let element = target; element && element !== document.body; element = element.parentElement) {
      if (element.scrollHeight > element.clientHeight + 4 && /auto|scroll/.test(getComputedStyle(element).overflowY)) {
        return element.scrollTop <= 0;
      }
    }
    return (document.scrollingElement?.scrollTop || 0) <= 0;
  };
  document.addEventListener('touchstart', event => {
    pulling = false;
    if (event.touches.length !== 1 || event.target.closest('input,textarea,select,[contenteditable="true"]') || !atTop(event.target)) return;
    startY = event.touches[0].clientY;
    startX = event.touches[0].clientX;
    pulling = true;
    distance = 0;
  }, { passive: true });
  document.addEventListener('touchmove', event => {
    if (!pulling || event.touches.length !== 1) return;
    const dy = event.touches[0].clientY - startY;
    if (Math.abs(event.touches[0].clientX - startX) > Math.max(24, dy)) { pulling = false; return; }
    distance = Math.max(0, dy);
    hintSource = distance >= 85 ? '放開即可更新' : '下拉更新';
    updateHint();
    hint.style.transform = distance > 15 ? 'translate(-50%,0)' : 'translate(-50%,-150%)';
  }, { passive: true });
  document.addEventListener('touchend', () => {
    hint.style.transform = 'translate(-50%,-150%)';
    if (!pulling || distance < 85) return;
    pulling = false;
    const draft = [...document.querySelectorAll('textarea,[contenteditable="true"]')].some(element => element.isContentEditable ? element.textContent.trim() : element.value.trim());
    if (draft && !confirm(translate('目前有未儲存的文字，仍要重新整理並放棄內容嗎？'))) return;
    location.reload();
  }, { passive: true });
})();
