// stock_watchlist — Bloomberg-style frontend (任务 #210+ 拆分后)
// 本文件只剩: state、window.ui 兼容 shim(给 html onclick 用)、event delegation、
// tick loop、init。所有业务逻辑已搬到 static/{util,chart,sector,stocklist,notes,modal}.js

// ── State ───────────────────────────────────────────────────
var ui = {};   // 兼容层,html onclick="ui.xxx" 通过这里转发到对应模块

const state = {
  sectorsTree: [],
  currentSectorId: null,
  currentStocks: [],
  currentDirectStocks: [],
  currentSectorChildren: [],
  selectedStockCode: null,
  currentFilter: 'all',
  visibleLabels: new Set(['core', 'focus', 'monitor', 'observation']),
  editingNoteId: null,
  chartData: { minute: null, kline: null },
  chartMode: 'minute',
  chartInstance: null,
  chartCode: null,
  _lastSelectAt: 0,
  busySelecting: false,
  _selectionController: null,
  notesCache: {},
  subSectorCache: {},
};

// state 必须挂在 window — chart/sector/stocklist/notes/modal 子模块都依赖
window.state = state;

// ── ui 兼容 shim: 把 templates/index.html 上的 onclick 转发到对应模块 ─
window.ui.selectStock = code => window.StockList.selectStock(code);
window.ui.closeDetail = () => window.StockList.closeDetail();
window.ui.closeModal = () => window.Modal.close();
window.ui.createSector = () => window.Modal.createSector();
window.ui.editSector = () => window.Modal.editSector();
window.ui.deleteSector = () => window.Modal.deleteSector();
window.ui.openSectorConfig = () => window.Modal.openConfig();
window.ui.addStockToCurrentSector = () => window.StockList.addStockToCurrentSector();
window.ui.filterStocks = label => window.StockList.filterStocks(label);
window.ui.toggleLabelVisible = (label, checked) => window.StockList.toggleLabelVisible(label, checked);
window.ui.toggleLabel = code => window.StockList.toggleLabel(code);
window.ui.removeStock = code => window.StockList.removeStock(code);
window.ui.createNote = () => window.Notes.create();
window.ui.editNote = id => window.Notes.edit(id);
window.ui.deleteNote = id => window.Notes.delete(id);
window.ui.saveNote = () => window.Notes.save();
window.ui.cancelNote = () => window.Notes.cancel();
window.ui.switchNoteTab = tab => window.Notes.switchNoteTab(tab);
window.ui.collapseInlineNote = code => window.Notes.collapseInline(code);
window.ui.inlineEditNote = code => window.Notes.inlineEdit(code);
window.ui.inlineCancelEdit = code => window.Notes.inlineCancel(code);
window.ui.inlineSaveNote = code => window.Notes.inlineSave(code);
window.saveInlineNote = (code, noteId) => window.Notes.inlineSave(code, noteId);

// ── Indices ticker (topbar) ─────────────────────────────────
async function fetchIndices() {
  try {
    const json = await window.Util.api('/api/indices');
    const data = json.data || [];
    for (const idx of data) {
      const key = idx.key;
      const q = idx.quote;
      const valEl = document.getElementById('idx-' + key);
      const chgEl = document.getElementById('idx-chg-' + key);
      if (valEl) {
        if (q && q.last_price != null) valEl.textContent = q.last_price.toFixed(2);
        else valEl.textContent = '--';
      }
      if (chgEl) {
        if (q && q.change_pct != null) {
          const pct = (q.change_pct * 100).toFixed(2);
          const sign = q.change_pct > 0 ? '+' : '';
          chgEl.textContent = `${sign}${pct}%`;
          chgEl.className = 'index-chg ' + window.Util.fmtChgCls(q.change_pct);
          if (q.last_price != null) {
            window.Util.flashIfChanged(chgEl, `idx-chg:${key}`, q.change_pct);
          }
        } else {
          chgEl.textContent = '--';
          chgEl.className = 'index-chg flat';
        }
      }
    }
  } catch {}
}

function startIndicesTicker() {
  fetchIndices();
  setInterval(fetchIndices, 3000);
}

// ── Clock ───────────────────────────────────────────────────
function startClock() {
  function tick() {
    const el = document.getElementById('clock');
    if (el) {
      const now = new Date();
      el.textContent = now.toLocaleTimeString('zh-CN', { hour12: false });
    }
  }
  tick();
  setInterval(tick, 1000);
}

// ── Sector tree click delegation (取子板块/折叠) ────────────
document.addEventListener('click', async e => {
  const nodeEl = e.target.closest('.sector-node');
  if (!nodeEl) return;
  if (e.target.classList.contains('sector-chevron')) {
    nodeEl.classList.toggle('open');
    const childContainer = nodeEl.nextElementSibling;
    if (childContainer && childContainer.classList.contains('sector-children')) {
      childContainer.style.display = nodeEl.classList.contains('open') ? '' : 'none';
    }
    return;
  }
  const id = parseInt(nodeEl.dataset.id);
  state.currentSectorId = id;
  const node = window.Sector.findNode(id);
  document.getElementById('sector-title').textContent = node?.name || '板块';
  const chgEl = document.getElementById('sector-title-change');
  if (chgEl) {
    chgEl.className = `sector-title-change ${window.Util.fmtChgCls(node?.change_pct)}`;
    chgEl.textContent = window.Util.fmtChg(node?.change_pct);
  }
  document.getElementById('sector-actions').style.display = 'flex';
  window.Sector.render();
  await window.StockList.load(id);
});

// ── Resize handle (panel 可拖拽宽度) ────────────────────────
function initResizeHandle() {
  function makeResizable(handleId, getTarget, getMin, getMax) {
    const handle = document.getElementById(handleId);
    if (!handle) return;
    let dragging = false;
    handle.addEventListener('mousedown', e => {
      dragging = true;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
    document.addEventListener('mousemove', e => {
      if (!dragging) return;
      const target = getTarget();
      if (!target) return;
      const rect = target.getBoundingClientRect();
      const newWidth = e.clientX - rect.left;
      target.style.flex = 'none';
      target.style.width = Math.max(getMin(), Math.min(newWidth, getMax())) + 'px';
    });
    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });
  }
  makeResizable('resize-handle-s2m', () => document.getElementById('sidebar'), () => 120, () => 400);
  makeResizable('resize-handle', () => document.getElementById('main'), () => 180, () => 800);
}

// ── Init ────────────────────────────────────────────────────
async function init() {
  startClock();
  startIndicesTicker();
  initResizeHandle();

  // 绑定 sector tree 的拖排 root drop zone (一次性)
  window.Sector.bindDropZone();

  // localStorage config 推到后端
  await window.Modal.applyConfig();

  // 同步初始 label filter
  const labels = [...state.visibleLabels];
  await window.Util.api('/api/sectors/metrics/filter', {
    method: 'PUT',
    body: JSON.stringify({ labels }),
  }).catch(() => {});

  await window.Sector.load();

  // 3s tick: 行情批量刷新 + chart 局部刷 + 板块 metrics 局部刷
  setInterval(() => {
    if (state.busySelecting || (Date.now() - state._lastSelectAt) < 200) return;
    const codes = state.currentStocks.map(s => s.stock_code || s.code).filter(c => c);
    if (state.selectedStockCode && !codes.includes(state.selectedStockCode)) {
      codes.push(state.selectedStockCode);
    }
    if (codes.length) window.StockList.fetchQuotesBatch(codes);
    if (state.selectedStockCode) window.Chart.refresh(state.selectedStockCode);
    window.Sector.refresh();
  }, 3000);
}

init();
