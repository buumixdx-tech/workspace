// static/stocklist.js — 任务 #211 拆分
// stock 列表渲染、detail panel、个股 drag/drop、quote 拉取与 DOM 更新、
// selectStock、filter、add/toggle/remove stock。
// 依赖: window.state, window.Util, window.Sector, window.Chart, window.Notes, window.Modal
// 公开 API:
//   StockList.load(sectorId)             — 拉板块树 + 拉 notes 缓存 + 渲染
//   StockList.applyFilter()              — 当前 filter 重新渲染
//   StockList.updateCounts()             — 更新顶部 count-* 标签
//   StockList.selectStock(code)          — 选中个股,刷新 detail/chart/note
//   StockList.closeDetail()              — 关闭右侧详情
//   StockList.fetchQuotesBatch(codes)    — 3s tick 用,批量拉 quote
//   StockList.renderSectorDetailPanel(s) — sector 模块 refresh 时调
//   StockList.bindDropZone()             — 绑定 stock-list 容器上的拖排 (init 一次)

(function () {
  const {
    $, $$, api, isAbortError, htmlEscape, fmtChg, fmtChgCls,
    flashIfChanged, cssEscape, formatVolume, formatAmount,
  } = window.Util;

  const LABEL_ORDER = { core: 0, focus: 1, monitor: 2, observation: 3, associate: 3 };
  const LABEL_NAMES = { core: '核心', focus: '关注', monitor: '观察', associate: '关联', observation: '观察' };

  let _dragStockCode = null;
  let _stockDropIndicator = null;

  function showStockDropIndicator(beforeEl) {
    hideStockDropIndicator();
    _stockDropIndicator = document.createElement('div');
    _stockDropIndicator.style.cssText = 'height:2px;background:var(--accent);margin:0 12px;pointer-events:none;';
    beforeEl.style.position = 'relative';
    beforeEl.parentNode.insertBefore(_stockDropIndicator, beforeEl);
  }
  function hideStockDropIndicator() {
    if (_stockDropIndicator) { _stockDropIndicator.remove(); _stockDropIndicator = null; }
  }

  // ── Detail panel ───────────────────────────────────────────
  function renderSectorDetailPanel(sector) {
    const panel = $('#sector-detail-panel');
    if (!panel) return;
    const m = sector.metrics;
    if (!m) { panel.style.display = 'none'; return; }
    panel.style.display = '';

    const chgEl = $('#sdp-chg');
    chgEl.textContent = fmtChg(m.change_pct);
    chgEl.className = `sdp-value ${fmtChgCls(m.change_pct)}`;

    const turnEl = $('#sdp-turnover');
    if (m.turnover != null) {
      turnEl.textContent = (m.turnover * 100).toFixed(2) + '%';
      turnEl.className = 'sdp-value';
    } else {
      turnEl.textContent = '--';
      turnEl.className = 'sdp-value flat';
    }

    const active = m.stock_count || 0;
    const total = m.total_count;
    $('#sdp-count').textContent = total != null && total !== active
      ? active + '/' + total
      : active;
    $('#sdp-count').className = 'sdp-value';
    $('#sdp-count').title = total != null && total !== active
      ? active + ' 只活跃交易 / ' + total + ' 只板块成员(其中 ' + (total - active) + ' 只停牌)'
      : '';

    renderSdpList('#sdp-gainers', m.top_gainers || [], false);
    renderSdpList('#sdp-losers', m.top_losers || [], false);
    renderSdpList('#sdp-contributors', m.contributors || [], true);
  }

  function renderSdpList(sel, items, showContribution) {
    const body = $(sel);
    if (!body) return;
    if (!items.length) {
      body.innerHTML = '<div class="sdp-empty">无</div>';
      return;
    }
    const listKey = sel.replace('#', '');
    body.innerHTML = items.map(it => {
      const code = htmlEscape(it.code);
      const display = htmlEscape(it.name || it.code);
      const v = showContribution ? it.contribution : it.change_pct;
      const vStr = showContribution
        ? (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + 'pp'
        : fmtChg(v);
      const vCls = fmtChgCls(v);
      const limitBadge = it.limit_flag === 'up'
        ? '<span class="sdp-limit-flag up" title="涨停一字板">一字</span>'
        : it.limit_flag === 'down'
        ? '<span class="sdp-limit-flag down" title="跌停一字板">一字</span>'
        : '';
      return `<div class="sdp-item" data-code="${code}">
        <span class="sdp-item-code">${display}${limitBadge}</span>
        <span class="sdp-item-v ${vCls}">${vStr}</span>
      </div>`;
    }).join('');
    body.querySelectorAll('.sdp-item').forEach((itemEl, idx) => {
      const it = items[idx];
      const vEl = itemEl.querySelector('.sdp-item-v');
      if (vEl && it) {
        flashIfChanged(vEl, `sdp:${listKey}:${it.code}`, showContribution ? it.contribution : it.change_pct);
      }
    });
  }

  // ── Filter / Counts ────────────────────────────────────────
  function _effectiveFilter(label) {
    if (label === 'monitor') return ['monitor', 'observation'];
    return [label];
  }
  function visibleFilter(stocks) {
    const v = state.visibleLabels;
    const f = state.currentFilter;
    return stocks.filter(s => {
      const labelOk = v.has(s.label) || (s.label === 'observation' && v.has('monitor')) || (s.label === 'monitor' && v.has('observation'));
      const filterOk = f === 'all' || _effectiveFilter(f).includes(s.label);
      return labelOk && filterOk;
    });
  }
  function applyFilter() {
    renderStockList(state.currentDirectStocks, state.currentSectorChildren);
  }

  async function collectAllStocksRecursive(sectorId) {
    try {
      const json = await api(`/api/sectors/${sectorId}/tree`);
      const stocks = json.data.stocks || [];
      const children = json.data.children || [];
      const results = [...stocks];
      for (const child of children) {
        const grand = await collectAllStocksRecursive(child.id);
        results.push(...grand);
      }
      return results;
    } catch {
      return [];
    }
  }

  async function updateCounts() {
    const allStocks = await collectAllStocksRecursive(state.currentSectorId);
    const all = allStocks.length;
    const core = allStocks.filter(s => s.label === 'core').length;
    const focus = allStocks.filter(s => s.label === 'focus').length;
    const monitor = allStocks.filter(s => s.label === 'monitor' || s.label === 'observation').length;
    const associate = allStocks.filter(s => s.label === 'associate').length;
    $('#count-all').textContent = all;
    $('#count-core').textContent = core;
    $('#count-focus').textContent = focus;
    $('#count-observation').textContent = monitor;
    $('#count-associate').textContent = associate;
  }

  // ── Load sector / sub-sector ───────────────────────────────
  async function loadSubSectorContent(sid) {
    if (state.subSectorCache[sid]) return;
    try {
      const json = await api(`/api/sectors/${sid}/tree`);
      state.subSectorCache[sid] = json.data;
    } catch {
      state.subSectorCache[sid] = { stocks: [], children: [] };
    }
  }

  async function load(sectorId) {
    const json = await api(`/api/sectors/${sectorId}/tree`);
    const sector = json.data.sector;
    const directStocks = json.data.stocks || [];
    const children = json.data.children || [];

    state.currentSectorId = sectorId;
    state.currentDirectStocks = directStocks;
    state.currentStocks = directStocks;
    state.currentSectorChildren = children;
    state.selectedStockCode = null;
    state.subSectorCache = {};

    // 批量拉全板块 notes — 切个股时优先读 cache
    try {
      const notesJson = await api(`/api/sectors/${sectorId}/notes`);
      const notesByStock = (notesJson.data && notesJson.data.notes_by_stock) || {};
      for (const code in notesByStock) {
        state.notesCache[code] = notesByStock[code];
      }
    } catch (e) {
      console.warn('[load] bulk notes fetch failed:', e.message);
    }

    // 板块标题旁涨跌幅
    const chgEl = $('#sector-title-change');
    if (chgEl) {
      const cp = sector.metrics ? sector.metrics.change_pct : null;
      chgEl.className = `sector-title-change ${fmtChgCls(cp)}`;
      chgEl.textContent = fmtChg(cp);
    }

    renderSectorDetailPanel(sector);
    children.forEach(child => { state.subSectorCache[child.id] = null; });

    closeDetail();
    await Promise.all(children.map(child => loadSubSectorContent(child.id)));

    // 合并子板块股到 currentStocks(去重)
    const seen = new Set(directStocks.map(s => s.stock_code || s.code));
    const merged = [...directStocks];
    for (const child of children) {
      const data = state.subSectorCache[child.id];
      if (!data || !Array.isArray(data.stocks)) continue;
      for (const s of data.stocks) {
        const code = s.stock_code || s.code;
        if (code && !seen.has(code)) { seen.add(code); merged.push(s); }
      }
    }
    state.currentStocks = merged;
    state.currentDirectStocks = directStocks;

    renderStockList(directStocks, children);
    await updateCounts();
  }

  // ── Render stock rows / sub-sectors ────────────────────────
  function stockRowHtml(s, sectorId, codesJson = null) {
    const code = htmlEscape(s.stock_code || s.code || '');
    const name = htmlEscape(s.name || code);
    const boardName = htmlEscape(s.board_name || '');
    const isSelected = code === state.selectedStockCode;
    const sidAttr = sectorId ? `data-sid="${sectorId}"` : '';
    const codesAttr = codesJson ? ` data-codes='${htmlEscape(codesJson)}'` : '';
    return `
      <div class="stock-row ${s.label} ${isSelected ? 'selected' : ''}" data-code="${code}" ${sidAttr}${codesAttr}>
        <span class="label-dot"></span>
        <span class="stock-name">${name}</span>
        <span class="stock-code">${code}</span>
        <span class="stock-board">${boardName}</span>
        <div class="stock-actions">
          <button class="btn-label" onclick="event.stopPropagation();StockList.toggleLabel('${code}')">${LABEL_NAMES[s.label] || s.label}</button>
          <button class="btn-remove" onclick="event.stopPropagation();StockList.removeStock('${code}')">✕</button>
        </div>
        <div class="stock-right">
          <span class="price" id="price-${code}">--</span>
          <span class="change flat" id="chg-${code}">--</span>
        </div>
      </div>`;
  }

  function collectAllAncestorCodes(childData, codes) {
    const siblingCodes = new Set(codes);
    if (childData.children) {
      for (const gc of childData.children) {
        const gcData = state.subSectorCache[gc.id];
        if (gcData && gcData.stocks) {
          for (const s of gcData.stocks) siblingCodes.add(s.stock_code || s.code);
        }
      }
    }
    return siblingCodes;
  }

  function renderSubChildren(childData, parentCodes, sectorId) {
    const { stocks = [], children = [] } = childData;
    const ancestorCodes = new Set(parentCodes);
    const allAncestorCodes = collectAllAncestorCodes(childData, ancestorCodes);

    const visible = visibleFilter(stocks.filter(s => !allAncestorCodes.has(s.stock_code || s.code)));
    const sorted = visible.sort((a, b) => LABEL_ORDER[a.label] - LABEL_ORDER[b.label]);
    const allCodes = stocks.map(s => s.stock_code || s.code);
    const codesJson = JSON.stringify(allCodes);

    let html = '';
    html += sorted.map(s => stockRowHtml(s, sectorId, codesJson)).join('');

    children.forEach(gc => {
      const gcData = state.subSectorCache[gc.id];
      const gcStocks = gcData ? gcData.stocks || [] : [];
      const gcVisible = visibleFilter(gcStocks.filter(s => !allAncestorCodes.has(s.stock_code || s.code)));
      const count = gcVisible.length;
      if (count === 0) return;
      const colorStyle = gc.color ? `background:${gc.color}` : 'background:#6b7280';
      const gcChgCls = fmtChgCls(gc.change_pct);
      const gcChg = fmtChg(gc.change_pct);
      html += `
        <div class="sub-sector-block" data-sid="${gc.id}">
          <div class="sub-sector-toggle open">
            <span class="sector-chevron">▶</span>
            <span class="sub-sector-dot" style="${colorStyle}"></span>
            <span class="sub-sector-name">${htmlEscape(gc.name)}</span>
            <span class="sector-change ${gcChgCls}" data-sid="${gc.id}">${gcChg}</span>
            <span class="sub-sector-count">${count}个</span>
          </div>
          <div class="sub-sector-children">${gcData ? renderSubChildren(gcData, allAncestorCodes, gc.id) : ''}</div>
        </div>`;
    });

    sorted.forEach(s => fetchQuote(s.stock_code || s.code));
    return html || '<div class="empty-state" style="padding:12px">无</div>';
  }

  function renderStockList(directStocks, children) {
    const container = $('#stock-list');
    if (!container) return;

    const parentCodes = new Set(directStocks.map(s => s.stock_code || s.code));
    const visibleDirect = visibleFilter(directStocks).sort((a, b) => LABEL_ORDER[a.label] - LABEL_ORDER[b.label]);
    const allDirectCodes = directStocks.map(s => s.stock_code || s.code);

    let html = '';
    const directCodesJson = JSON.stringify(allDirectCodes);
    html += visibleDirect.map(s => stockRowHtml(s, null, directCodesJson)).join('');

    children.forEach(child => {
      const childData = state.subSectorCache[child.id];
      const childStocks = childData ? childData.stocks || [] : [];
      const visibleChild = visibleFilter(childStocks.filter(s => !parentCodes.has(s.stock_code || s.code)));
      const count = visibleChild.length;
      if (count === 0) return;
      const colorStyle = child.color ? `background:${child.color}` : 'background:#6b7280';
      const subChgCls = fmtChgCls(child.change_pct);
      const subChg = fmtChg(child.change_pct);
      html += `
        <div class="sub-sector-block" data-sid="${child.id}">
          <div class="sub-sector-toggle open">
            <span class="sector-chevron">▶</span>
            <span class="sub-sector-dot" style="${colorStyle}"></span>
            <span class="sub-sector-name">${htmlEscape(child.name)}</span>
            <span class="sector-change ${subChgCls}" data-sid="${child.id}">${subChg}</span>
            <span class="sub-sector-count">${count}个</span>
          </div>
          <div class="sub-sector-children">${childData ? renderSubChildren(childData, parentCodes, child.id) : ''}</div>
        </div>`;
    });

    if (!html) {
      container.innerHTML = '<div class="empty-state">暂无标的</div>';
      return;
    }
    container.innerHTML = html;

    // 恢复笔记展开状态 — 重渲会吞 note-row
    if (state.selectedStockCode) {
      const sel = state.selectedStockCode;
      const notes = state.notesCache[sel];
      if (notes && notes.length > 0) {
        requestAnimationFrame(() => {
          const stockRow = document.querySelector(`.stock-row[data-code="${cssEscape(sel)}"]`);
          if (stockRow) Notes.showInline(sel, notes[0]);
        });
      }
    }

    // 子板块折叠事件
    container.querySelectorAll('.sub-sector-toggle').forEach(toggle => {
      toggle.addEventListener('click', async () => {
        const block = toggle.closest('.sub-sector-block');
        const sid = parseInt(block.dataset.sid);
        const childList = block.querySelector('.sub-sector-children');
        const isOpen = toggle.classList.contains('open');

        if (!isOpen) {
          if (childList.innerHTML === '') {
            const childData = state.subSectorCache[sid];
            if (childData) {
              childList.innerHTML = renderSubChildren(childData, parentCodes, sid);
              bindChildStockDrag(childList, sid);
            }
          }
          toggle.classList.add('open');
          childList.style.display = '';
        } else {
          toggle.classList.remove('open');
          childList.style.display = 'none';
        }
      });
    });

    bindDirectStockDrag(container, allDirectCodes);
    visibleDirect.forEach(s => fetchQuote(s.stock_code || s.code));
  }

  // ── Drag binding ───────────────────────────────────────────
  function bindDirectStockDrag(container, allDirectCodes) {
    if (container._dragBound) return;
    container._dragBound = true;
    container.addEventListener('dragstart', e => {
      const row = e.target.closest('.stock-row');
      if (!row) return;
      _dragStockCode = row.dataset.code;
      row.style.opacity = '0.4';
      e.dataTransfer.effectAllowed = 'move';
    });
    container.addEventListener('dragend', e => {
      const row = e.target.closest('.stock-row');
      if (row) row.style.opacity = '';
      hideStockDropIndicator();
      _dragStockCode = null;
    });
    container.addEventListener('dragover', e => {
      const row = e.target.closest('.stock-row');
      if (!row || !_dragStockCode) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const rect = row.getBoundingClientRect();
      const mid = rect.top + rect.height * 0.5;
      if (e.clientY < mid) {
        showStockDropIndicator(row);
      } else {
        const next = row.nextElementSibling;
        if (next && next.matches('.stock-row')) showStockDropIndicator(next);
        else hideStockDropIndicator();
      }
    });
    container.addEventListener('dragleave', e => { /* nothing */ });
    container.addEventListener('drop', e => {
      const row = e.target.closest('.stock-row');
      e.preventDefault();
      if (!row || !_dragStockCode || _dragStockCode === row.dataset.code) {
        _dragStockCode = null; return;
      }
      const targetSid = row.dataset.sid ? parseInt(row.dataset.sid) : state.currentSectorId;
      const codes = JSON.parse(row.dataset.codes || '[]');
      if (!codes.length) { _dragStockCode = null; return; }
      const rect = row.getBoundingClientRect();
      const insertBefore = e.clientY < rect.top + rect.height * 0.5;
      const fromIdx = codes.indexOf(_dragStockCode);
      if (fromIdx >= 0) codes.splice(fromIdx, 1);
      const toIdx = codes.indexOf(row.dataset.code);
      const insertIdx = insertBefore ? toIdx : toIdx + 1;
      codes.splice(insertIdx, 0, _dragStockCode);
      hideStockDropIndicator();
      _dragStockCode = null;
      api(`/api/sectors/${targetSid}/stocks/reorder`, {
        method: 'PUT',
        body: JSON.stringify({ codes }),
      }).then(() => load(state.currentSectorId)).catch(e => alert('排序失败: ' + e.message));
    });
    container.addEventListener('click', e => {
      const row = e.target.closest('.stock-row');
      if (row && row.dataset.code && !e.target.closest('button')) {
        selectStock(row.dataset.code);
      }
    });
  }

  function bindChildStockDrag(container, sid) {
    container.addEventListener('dragstart', e => {
      const row = e.target.closest('.stock-row');
      if (!row) return;
      _dragStockCode = row.dataset.code;
      row.style.opacity = '0.4';
      e.dataTransfer.effectAllowed = 'move';
    });
    container.addEventListener('dragend', e => {
      const row = e.target.closest('.stock-row');
      if (row) row.style.opacity = '';
      hideStockDropIndicator();
      _dragStockCode = null;
    });
    container.addEventListener('dragover', e => {
      const row = e.target.closest('.stock-row');
      if (!row || !_dragStockCode) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const rect = row.getBoundingClientRect();
      if (e.clientY < rect.top + rect.height * 0.5) {
        showStockDropIndicator(row);
      } else {
        const next = row.nextElementSibling;
        if (next && next.matches('.stock-row')) showStockDropIndicator(next);
        else hideStockDropIndicator();
      }
    });
    container.addEventListener('drop', e => {
      const row = e.target.closest('.stock-row');
      e.preventDefault();
      if (!row || !_dragStockCode || _dragStockCode === row.dataset.code) {
        _dragStockCode = null; return;
      }
      const targetSid = row.dataset.sid ? parseInt(row.dataset.sid) : sid;
      const codes = JSON.parse(row.dataset.codes || '[]');
      if (!codes.length) { _dragStockCode = null; return; }
      const rect = row.getBoundingClientRect();
      const insertBefore = e.clientY < rect.top + rect.height * 0.5;
      const fromIdx = codes.indexOf(_dragStockCode);
      if (fromIdx >= 0) codes.splice(fromIdx, 1);
      const toIdx = codes.indexOf(row.dataset.code);
      const insertIdx = insertBefore ? toIdx : toIdx + 1;
      codes.splice(insertIdx, 0, _dragStockCode);
      hideStockDropIndicator();
      _dragStockCode = null;
      api(`/api/sectors/${targetSid}/stocks/reorder`, {
        method: 'PUT',
        body: JSON.stringify({ codes }),
      }).then(() => load(state.currentSectorId)).catch(e => alert('排序失败: ' + e.message));
    });
    container.addEventListener('click', e => {
      const toggle = e.target.closest('.sub-sector-toggle');
      if (!toggle) return;
      const block = toggle.closest('.sub-sector-block');
      const gcId = parseInt(block.dataset.sid);
      const childList = block.querySelector('.sub-sector-children');
      const isOpen = toggle.classList.contains('open');
      if (!isOpen) {
        toggle.classList.add('open');
        childList.style.display = '';
        if (childList.innerHTML === '') {
          const gcData = state.subSectorCache[gcId];
          if (gcData) {
            const parentCodes = new Set();
            childList.innerHTML = renderSubChildren(gcData, parentCodes, gcId);
            bindChildStockDrag(childList, gcId);
          }
        }
      } else {
        toggle.classList.remove('open');
        childList.style.display = 'none';
      }
    });
  }

  function bindDropZone() {
    const c = $('#stock-list');
    if (!c) return;
    // 注: stock-list 自身的拖排 delegate 在 renderStockList -> bindDirectStockDrag 里
    // 一次性绑定(_dragBound marker)。这里只需要 container 本身存在即可。
  }

  // ── Quote fetch / DOM update ───────────────────────────────
  async function fetchQuotesBatch(codes) {
    if (!codes || !codes.length) return;
    try {
      const json = await api(`/api/stocks/quotes?codes=${codes.map(encodeURIComponent).join(',')}`);
      const data = json.data || {};
      for (const code of codes) {
        const q = data[code];
        if (!q) continue;
        updateQuoteDOM(code, q);
      }
    } catch {}
  }

  function updateQuoteDOM(code, q) {
    if (!q) return;
    const priceEl = $(`#price-${code}`);
    const chgEl = $(`#chg-${code}`);
    if (priceEl) {
      priceEl.textContent = q.is_suspended ? '停牌' : (q.last_price != null ? q.last_price.toFixed(2) : '--');
      flashIfChanged(priceEl, `price:${code}`, q.last_price, { threshold: 0.005 });
    }
    if (chgEl) {
      if (q.is_suspended) {
        chgEl.className = 'change flat suspended';
        chgEl.textContent = '--';
      } else if (q.change > 0) {
        chgEl.className = 'change up';
        chgEl.textContent = `+${q.change.toFixed(2)} +${((q.change_pct || 0) * 100).toFixed(2)}%`;
      } else if (q.change < 0) {
        chgEl.className = 'change down';
        chgEl.textContent = `${q.change.toFixed(2)} ${(q.change_pct * 100).toFixed(2)}%`;
      } else {
        chgEl.className = 'change flat';
        chgEl.textContent = '0.00 0.00%';
      }
      flashIfChanged(chgEl, `chg:${code}`, q.change_pct);
    }
    if (code === state.selectedStockCode) {
      updateQuoteUI(q);
    }
  }

  async function fetchQuote(code) {
    try {
      const json = await api(`/api/stocks/${encodeURIComponent(code)}`);
      if (!json.data.quote) return;
      updateQuoteDOM(code, json.data.quote);
    } catch {}
  }

  function updateQuoteUI(q) {
    const lastEl = $('#q-last');
    lastEl.textContent = q.is_suspended ? '停牌' : (q.last_price != null ? q.last_price.toFixed(2) : '--');
    flashIfChanged(lastEl, `q-last:${state.selectedStockCode}`, q.last_price, { threshold: 0.005 });
    const chgEl = $('#q-change');
    if (q.is_suspended) {
      chgEl.className = 'change-lg flat suspended';
      chgEl.textContent = '--';
    } else if (q.change > 0) {
      chgEl.className = 'change-lg up';
      chgEl.textContent = `+${q.change.toFixed(2)} (+${((q.change_pct || 0) * 100).toFixed(2)}%)`;
    } else if (q.change < 0) {
      chgEl.className = 'change-lg down';
      chgEl.textContent = `${q.change.toFixed(2)} (${(q.change_pct * 100).toFixed(2)}%)`;
    } else {
      chgEl.className = 'change-lg flat';
      chgEl.textContent = '0.00 (0.00%)';
    }
    flashIfChanged(chgEl, `q-change:${state.selectedStockCode}`, q.change_pct);

    const openStr = q.open != null ? q.open.toFixed(2) : '--';
    const prevStr = q.pre_close != null ? q.pre_close.toFixed(2) : '--';
    $('#q-open').textContent = (openStr === '--' && prevStr === '--') ? '--' : `${openStr} / ${prevStr}`;

    const highStr = q.high != null ? q.high.toFixed(2) : '--';
    const lowStr = q.low != null ? q.low.toFixed(2) : '--';
    $('#q-high').textContent = (highStr === '--' && lowStr === '--') ? '--' : `${highStr} / ${lowStr}`;

    const totalMvStr = q.total_mv != null ? formatAmount(q.total_mv) : '--';
    const circMvStr = q.circ_mv != null ? formatAmount(q.circ_mv) : '--';
    $('#q-low').textContent = (totalMvStr === '--' && circMvStr === '--') ? '--' : `${totalMvStr} / ${circMvStr}`;

    const volStr = q.volume != null ? formatVolume(q.volume) : '--';
    const amtStr = q.amount != null ? formatAmount(q.amount) : '--';
    $('#q-volume').textContent = (volStr === '--' && amtStr === '--') ? '--' : `${volStr} / ${amtStr}`;

    $('#q-amount').textContent = q.turnover_rate != null ? `${(+q.turnover_rate).toFixed(2)}%` : '--';
    $('#q-limit').textContent = q.limit_up != null ? `${q.limit_up.toFixed(2)} / ${q.limit_down.toFixed(2)}` : '--';

    lastEl.classList.remove('near-limit-up', 'near-limit-down', 'at-limit-up', 'at-limit-down');
    if (q.last_price != null && q.limit_up != null) {
      if (q.last_price >= q.limit_up - 0.01) lastEl.classList.add('at-limit-up');
      else if (q.last_price >= q.limit_up * 0.995) lastEl.classList.add('near-limit-up');
    }
    if (q.last_price != null && q.limit_down != null) {
      if (q.last_price <= q.limit_down + 0.01) lastEl.classList.add('at-limit-down');
      else if (q.last_price <= q.limit_down * 1.005) lastEl.classList.add('near-limit-down');
    }
  }

  // ── Select / close ─────────────────────────────────────────
  async function selectStock(code) {
    if (state.selectedStockCode === code) {
      const noteRow = document.getElementById('note-row-' + code);
      if (noteRow && noteRow.style.display !== 'none') {
        noteRow.style.maxHeight = '0';
        setTimeout(() => { noteRow.style.display = 'none'; }, 300);
        state.selectedStockCode = null;
        $$('.stock-row').forEach(el => el.classList.remove('selected'));
        return;
      }
    }

    if (state._selectionController) state._selectionController.abort();
    const controller = new AbortController();
    state._selectionController = controller;
    const signal = controller.signal;

    console.log('[selectStock]', code);
    state.selectedStockCode = code;

    $$('.stock-row').forEach(el => {
      el.classList.toggle('selected', el.dataset.code === code);
    });
    $$('.stock-note-row').forEach(el => el.style.display = 'none');

    const stock = state.currentStocks.find(s => s.stock_code === code);
    if (!stock) return;

    $('#stock-detail').style.display = 'flex';
    $('#detail-empty').style.display = 'none';
    $('#detail-name').textContent = stock.name || code;
    $('#detail-code').textContent = code;
    $('#detail-board').textContent = stock.board_name || '';

    state.busySelecting = true;

    try {
      const quotePromise = api(`/api/stocks/${encodeURIComponent(code)}`, { signal })
        .then(json => { if (json.data.quote) updateQuoteUI(json.data.quote); })
        .catch(e => { if (!isAbortError(e)) console.warn('[selectStock] quote failed:', e); });

      Chart.load(code, signal);

      let notes = state.notesCache[code];
      if (!notes) {
        try {
          const notesData = await api(`/api/stocks/${encodeURIComponent(code)}/notes`, { signal });
          notes = notesData.data || [];
          state.notesCache[code] = notes;
        } catch (e) {
          if (isAbortError(e)) return;
          notes = [];
        }
      }

      $('#notes-area').style.display = 'flex';
      const notesList = $('#notes-list');
      if (notesList) notesList.style.display = 'none';
      Notes.renderList(notes);

      if (notes.length > 0) Notes.showInline(code, notes[0]);

      await quotePromise;
    } finally {
      state.busySelecting = false;
      state._lastSelectAt = Date.now();
      setTimeout(() => { state._lastSelectAt = 0; }, 200);
    }
  }

  function closeDetail() {
    $('#stock-detail').style.display = 'none';
    $('#detail-empty').style.display = '';
    state.selectedStockCode = null;
  }

  // ── Filter / Toggle / Remove ───────────────────────────────
  function filterStocks(label) {
    state.currentFilter = label;
    $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.filter === label));
    renderStockList(state.currentDirectStocks, state.currentSectorChildren);
  }

  function toggleLabelVisible(label, checked) {
    if (label === 'monitor') {
      if (checked) { state.visibleLabels.add('monitor'); state.visibleLabels.add('observation'); }
      else { state.visibleLabels.delete('monitor'); state.visibleLabels.delete('observation'); }
    } else {
      if (checked) state.visibleLabels.add(label);
      else state.visibleLabels.delete(label);
    }
    const labels = [...state.visibleLabels];
    api('/api/sectors/metrics/filter', {
      method: 'PUT',
      body: JSON.stringify({ labels }),
    }).then(() => Sector.load())
      .then(() => renderStockList(state.currentDirectStocks, state.currentSectorChildren))
      .catch(e => {
        console.warn('[toggleLabelVisible]', e);
        renderStockList(state.currentDirectStocks, state.currentSectorChildren);
      });
  }

  async function toggleLabel(code) {
    const stock = state.currentStocks.find(s => s.stock_code === code);
    if (!stock) return;
    const labels = ['core', 'focus', 'monitor', 'associate'];
    const current = labels.indexOf(stock.label);
    const next = labels[(current + 1) % labels.length];
    try {
      await api(`/api/sectors/${state.currentSectorId}/stocks/${encodeURIComponent(code)}`, {
        method: 'PUT',
        body: JSON.stringify({ label: next }),
      });
      await load(state.currentSectorId);
    } catch (e) { alert(e.message); }
  }

  async function removeStock(code) {
    if (!confirm('确认移除该标的？')) return;
    try {
      await api(`/api/sectors/${state.currentSectorId}/stocks/${encodeURIComponent(code)}`, {
        method: 'DELETE',
      });
      await load(state.currentSectorId);
    } catch (e) { alert(e.message); }
  }

  // ── Add stock (搜索 + 添加) ────────────────────────────────
  function addStockToCurrentSector() {
    if (!state.currentSectorId) { alert('请先选择板块'); return; }
    Modal.show('添加标的', `
      <div class="form-group">
        <label class="form-label">搜索股票</label>
        <div class="search-wrap">
          <input id="f-search" class="form-input" placeholder="输入代码或名称..." autocomplete="off">
          <div id="search-results" class="search-results"></div>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">标注</label>
        <select id="f-label" class="form-select">
          <option value="core">核心标的</option>
          <option value="focus">关注标的</option>
          <option value="monitor">观察标的</option>
          <option value="associate">关联标的</option>
        </select>
      </div>
      <div id="selected-preview" style="display:none;padding:8px;background:var(--bg);border-radius:3px;margin-bottom:12px;font-size:12px">
        <strong id="preview-name"></strong>
        <span id="preview-code" style="color:var(--text-dim);margin-left:8px;font-family:var(--mono)"></span>
      </div>
      <div class="modal-footer" style="padding:0;border:none">
        <button class="btn-secondary" onclick="Modal.close()">取消</button>
        <button class="btn-primary" id="btn-add-stock-confirm">添加</button>
      </div>
    `);

    let timer = null;
    $('#f-search').addEventListener('input', () => {
      clearTimeout(timer);
      const q = $('#f-search').value.trim();
      if (!q) { $('#search-results').style.display = 'none'; return; }
      timer = setTimeout(async () => {
        try {
          const json = await api(`/api/stocks/search?q=${encodeURIComponent(q)}&limit=10`);
          const data = json.data || [];
          if (!data.length) {
            $('#search-results').innerHTML = '<div class="search-item" style="color:var(--text-dim)">无结果</div>';
          } else {
            $('#search-results').innerHTML = data.map(s => `
              <div class="search-item" data-code="${htmlEscape(s.code)}">
                <span class="search-item-name">${htmlEscape(s.name)}</span>
                <span class="search-item-code">${htmlEscape(s.code)}</span>
              </div>
            `).join('');
          }
          $('#search-results').style.display = 'block';
        } catch {}
      }, 250);
    });

    $('#search-results').addEventListener('click', e => {
      const item = e.target.closest('.search-item');
      if (!item || !item.dataset.code) return;
      $('#f-search').value = `${item.querySelector('.search-item-name').textContent} (${item.dataset.code})`;
      $('#f-search').dataset.selected = item.dataset.code;
      $('#search-results').style.display = 'none';
      $('#selected-preview').style.display = 'block';
      $('#preview-name').textContent = item.querySelector('.search-item-name').textContent;
      $('#preview-code').textContent = item.dataset.code;
    });

    const sectorId = state.currentSectorId;
    document.getElementById('btn-add-stock-confirm').addEventListener('click', async () => {
      const code = document.getElementById('f-search').dataset.selected;
      if (!code) { alert('请先从搜索结果中选择股票'); return; }
      const label = document.getElementById('f-label').value;
      try {
        await api(`/api/sectors/${sectorId}/stocks`, {
          method: 'POST',
          body: JSON.stringify({ stock_code: code, label }),
        });
        Modal.close();
        await load(state.currentSectorId);
      } catch (e) { alert(e.message); }
    });
  }

  // ── 切回 tab 自动刷新当前板块(方案 3)────────────────────────
  // 浏览器切走时用户看不见,悄悄重拉数据;
  // 切回时调用 StockList.load 重渲 subSectorCache / 当前 direct stocks。
  // visibilitychange + focus 同时监听 → 跨浏览器稳;
  // 300ms debounce 防止两事件连发导致重入。
  let _revisitTimer = null;
  function _refreshOnRevisit() {
    if (_revisitTimer) clearTimeout(_revisitTimer);
    _revisitTimer = setTimeout(() => {
      _revisitTimer = null;
      if (state.currentSectorId) load(state.currentSectorId);
    }, 300);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') _refreshOnRevisit();
  });
  window.addEventListener('focus', _refreshOnRevisit);

  window.StockList = {
    load, applyFilter, updateCounts, selectStock, closeDetail,
    fetchQuotesBatch, renderSectorDetailPanel, bindDropZone,
    filterStocks, toggleLabelVisible, toggleLabel, removeStock, addStockToCurrentSector,
  };
})();
