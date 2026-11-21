(() => {
  'use strict';
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const seen = new Set();
  const pending = new Set();
  const boundLists = new WeakSet();
  let currentList = null;

  const keyOf = node => node.hasAttribute('data-scroll-reveal-key')
    ? `entry:${node.dataset.scrollRevealKey}`
    : node.matches('.relatedGroup')
    ? `group:${node.dataset.relationGroup}`
    : `achievement:${node.querySelector('.check[data-id]')?.dataset.id}`;

  const clearClasses = node => {
    node.classList.remove('achievementRevealPending', 'achievementRevealEntering');
  };

  const reveal = (node, animate = true) => {
    if (!pending.delete(node)) return;
    observer?.unobserve(node);
    seen.add(keyOf(node));
    node.classList.remove('achievementRevealPending');
    if (animate && !reducedMotion.matches) node.classList.add('achievementRevealEntering');
  };

  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) reveal(entry.target);
    }
  }, { rootMargin: '0px 0px -24px 0px', threshold: 0 }) : null;

  const observe = list => {
    if (!list) return;
    currentList = list;
    observer?.disconnect();
    for (const node of pending) clearClasses(node);
    pending.clear();
    if (!boundLists.has(list)) {
      boundLists.add(list);
      // Keyboard navigation must never land on an invisible control.
      list.addEventListener('focusin', event => {
        let node = event.target;
        while (node && node.parentElement !== list) node = node.parentElement;
        if (node) {
          reveal(node, false);
          clearClasses(node);
        }
      });
      list.addEventListener('animationend', event => {
        if (event.animationName === 'achievementScrollEnter') clearClasses(event.target);
      });
    }
    for (const node of list.children) {
      if (!node.matches('.achievement, .relatedGroup, [data-scroll-reveal-key]')) continue;
      const key = keyOf(node);
      if (!observer || reducedMotion.matches) {
        seen.add(key);
        clearClasses(node);
      } else if (!seen.has(key)) {
        node.classList.add('achievementRevealPending');
        pending.add(node);
        observer.observe(node);
      }
    }
  };

  // Seen item IDs survive list replacement after progress, filters, and language updates.
  window.MiloraAchievementReveal = Object.freeze({ observe });
  reducedMotion.addEventListener('change', () => observe(currentList));
  observe(document.getElementById('list') || document.getElementById('redeemBody') || document.getElementById('accountProgressList'));
})();
