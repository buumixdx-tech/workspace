// static/util.js — 任务 #210+ 拆分时引入
// 共享工具: 跨模块使用的基础函数。所有前端模块都依赖这里。
// 暴露到 window.Util: { $, $$, api, isAbortError, htmlEscape, fmtChg, fmtChgCls,
//                       flashIfChanged, renderMd, cssEscape, formatVolume, formatAmount }

(function () {
  const $ = sel => sel.startsWith('#')
    ? document.getElementById(sel.slice(1))
    : document.querySelector(sel);
  const $$ = sel => document.querySelectorAll(sel);

  async function api(url, opts = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.error || '请求失败');
    return json;
  }

  // AbortError 当作"请求被取消" — 不报警,正常控制流。
  function isAbortError(e) {
    return e && (e.name === 'AbortError' || e.code === 20);
  }

  function htmlEscape(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // 涨跌幅格式化: +1.23% / -1.23% / --
  function fmtChg(v) {
    if (v == null) return '--';
    const pct = (v * 100).toFixed(2);
    return v > 0 ? `+${pct}%` : `${pct}%`;
  }
  function fmtChgCls(v) {
    if (v == null) return 'flat';
    if (v > 0) return 'up';
    if (v < 0) return 'down';
    return 'flat';
  }

  // 状态对比 + CSS 动画: 价格/涨跌幅变化时给元素短暂高亮再褪色
  const _prevFlash = new Map();
  function flashIfChanged(el, key, newVal, opts = {}) {
    if (!el) return;
    const old = _prevFlash.get(key);
    if (newVal == null) {
      _prevFlash.set(key, null);
      return;
    }
    _prevFlash.set(key, newVal);
    if (old == null) return;
    const threshold = opts.threshold ?? 0.0001;
    if (Math.abs(newVal - old) < threshold) return;
    const cls = newVal > old ? 'flash-up' : 'flash-down';
    el.classList.remove('flash-up', 'flash-down');
    void el.offsetWidth;
    el.classList.add(cls);
  }

  function renderMd(text) {
    if (!text) return '';
    return text
      .replace(/^### (.+)$/gm, '<h2>$1</h2>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/^(.+)$/gm, '$1');
  }

  // CSS.escape polyfill — ^ 在 attribute selector 里需要 escape
  function cssEscape(s) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
    return String(s).replace(/([!"#$%&'()*+,./:;<=>?@[\]^`{|}~])/g, '\\$1');
  }

  function formatVolume(v) {
    if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
    if (v >= 1e4) return (v / 1e4).toFixed(2) + '万';
    return v.toFixed(0);
  }

  function formatAmount(a) {
    if (a >= 1e8) return (a / 1e8).toFixed(2) + '亿';
    if (a >= 1e4) return (a / 1e4).toFixed(2) + '万';
    return a.toFixed(0);
  }

  // 暴露到 window — 所有子模块都能用
  window.Util = {
    $, $$, api, isAbortError, htmlEscape,
    fmtChg, fmtChgCls, flashIfChanged, renderMd,
    cssEscape, formatVolume, formatAmount,
  };
})();