'use strict';
const themeButton = '<button class="theme-switch" type="button"><span class="to-night">☾ 夜间</span><span class="to-day">☀ 日间</span></button>';
(() => {
  const key = 'zhixu.appearance';
  const system = matchMedia('(prefers-color-scheme: dark)');
  function apply(preference) {
    const night = preference === 'night' || (preference !== 'day' && system.matches);
    document.documentElement.dataset.theme = night ? 'night' : 'day';
    document.querySelector('meta[name="theme-color"]').content = night ? '#0c1727' : '#f4f6fa';
  }
  function restore() {
    let value;
    try { value = localStorage.getItem(key); } catch {}
    apply(value);
  }
  restore();
  system.addEventListener('change', restore);
  window.addEventListener('storage', event => { if (event.key === key || event.key === null) restore(); });
  document.addEventListener('click', event => {
    if (!event.target.closest('.theme-switch')) return;
    const value = document.documentElement.dataset.theme === 'night' ? 'day' : 'night';
    apply(value);
    try { localStorage.setItem(key, value); } catch {}
  });
})();
