// static/sector.js — 任务 #210 拆分
// 板块树渲染、drag/drop、移动、metrics 刷新。
// 依赖: window.state, window.Util
// 公开 API:
//   Sector.load()                — 拉一次全量 sectors 树并渲染
//   Sector.refresh()             — 3s tick 局部刷新 metrics, 不破坏折叠/选中
//   Sector.render()              — 用 state.sectorsTree 重渲整个树
//   Sector.move(id, parentId, sortOrder) — 移动板块
//   Sector.findNode(id)          — 在 state.sectorsTree 递归找节点
//   Sector.bindDropZone()        — 绑定 root drop zone (init 时调一次)

(function () {
  const { $, $$, api, htmlEscape, fmtChg, fmtChgCls, flashIfChanged } = window.Util;
  const _tree = document.getElementById('sector-tree');

  let _dragId = null;       // 当前拖动的 sector id
  let _dragParentId = null; // 拖动前的 parent_id（null 表示顶级）
  let _dropIndicator = null;

  function showDropIndicator(el) {
    hideDropIndicator();
    _dropIndicator = document.createElement('div');
    _dropIndicator.className = 'sector-drop-indicator';
    _dropIndicator.style.cssText = 'height:2px;background:var(--accent);margin:0 12px;pointer-events:none;';
    el.style.position = 'relative';
    el.parentNode.insertBefore(_dropIndicator, el);
  }
  function hideDropIndicator() {
    if (_dropIndicator) { _dropIndicator.remove(); _dropIndicator = null; }
  }

  function renderNode(node, depth = 0) {
    const hasChildren = node.children && node.children.length > 0;
    const isActive = node.id === state.currentSectorId;
    const colorStyle = node.color ? `background:${node.color}` : '';
    const childrenHtml = hasChildren
      ? `<div class="sector-children">${node.children.map(n => renderNode(n, depth + 1)).join('')}</div>`
      : '';
    return `
      <div class="sector-node${isActive ? ' active' : ''}" draggable="true" data-id="${node.id}" data-name="${htmlEscape(node.name)}">
        ${hasChildren ? '<span class="sector-chevron">▶</span>' : '<span style="width:10px;display:inline-block"></span>'}
        <span class="sector-dot" style="${colorStyle}"></span>
        <span class="sector-name">${htmlEscape(node.name)}</span>
        <span class="sector-change ${fmtChgCls(node.change_pct)}" data-sid="${node.id}">${fmtChg(node.change_pct)}</span>
      </div>
      ${childrenHtml}
    `;
  }

  function render() {
    if (!_tree) return;
    _tree.innerHTML = state.sectorsTree.map(node => renderNode(node)).join('');
  }

  function findNodeIn(nodes, id) {
    for (const n of nodes) {
      if (n.id === id) return n;
      if (n.children) {
        const f = findNodeIn(n.children, id);
        if (f) return f;
      }
    }
    return null;
  }
  // 公开: 单参数入口, 默认在 state.sectorsTree 找
  function findNode(id) {
    if (id == null) return null;
    return findNodeIn(state.sectorsTree, id);
  }
  function findNodeParentId(tree, id) {
    for (const node of tree) {
      if (node.children?.some(c => c.id === id)) return node.id;
      const found = findNodeParentId(node.children || [], id);
      if (found !== null) return found;
    }
    return null;
  }
  function getSiblings(tree, parentId) {
    if (parentId === null) return tree;
    const parent = findNodeIn(tree, parentId);
    return parent?.children || [];
  }

  async function move(sectorId, newParentId, newSortOrder) {
    try {
      await rebalanceIfConflict(sectorId, newParentId, newSortOrder);
      await api(`/api/sectors/${sectorId}`, {
        method: 'PUT',
        body: JSON.stringify({ parent_id: newParentId, sort_order: newSortOrder }),
      });
      await load();
      if (state.currentSectorId) await StockList.load(state.currentSectorId);
    } catch (e) {
      alert('移动失败: ' + e.message);
    }
  }

  async function rebalanceIfConflict(movingId, parentId, newOrder) {
    const siblings = getSiblings(state.sectorsTree, parentId);
    const hasConflict = siblings.some(s => s.id !== movingId && s.sort_order === newOrder);
    if (!hasConflict) return;
    const sorted = [...siblings].sort((a, b) => a.sort_order - b.sort_order);
    const updates = sorted.map((s, i) => ({ id: s.id, order: i * 1024 }));
    for (const u of updates) {
      await api(`/api/sectors/${u.id}`, {
        method: 'PUT',
        body: JSON.stringify({ sort_order: u.order }),
      });
    }
  }

  async function load() {
    const json = await api('/api/sectors');
    state.sectorsTree = json.data || [];
    render();
  }

  async function refresh() {
    let json;
    try {
      json = await api('/api/sectors/metrics');
    } catch {
      return;
    }
    const data = json.data || {};
    function walk(nodes) {
      for (const n of nodes) {
        const m = data[String(n.id)];
        n.change_pct = m ? m.change_pct : null;
        n.turnover = m ? m.turnover : null;
        if (n.children) walk(n.children);
      }
    }
    walk(state.sectorsTree);
    document.querySelectorAll('.sector-change[data-sid]').forEach(el => {
      const sid = el.dataset.sid;
      const m = data[sid];
      const v = m ? m.change_pct : null;
      el.textContent = fmtChg(v);
      el.className = `sector-change ${fmtChgCls(v)}`;
      if (v != null) flashIfChanged(el, `sector:${sid}`, v);
    });
    if (state.currentSectorId) {
      const node = findNodeIn(state.sectorsTree, state.currentSectorId);
      const chgEl = $('#sector-title-change');
      if (chgEl && node) {
        chgEl.className = `sector-title-change ${fmtChgCls(node.change_pct)}`;
        chgEl.textContent = fmtChg(node.change_pct);
        flashIfChanged(chgEl, `sector-title:${state.currentSectorId}`, node.change_pct);
      }
      const panel = $('#sector-detail-panel');
      if (panel && panel.style.display !== 'none') {
        const m = data[String(state.currentSectorId)];
        if (m) StockList.renderSectorDetailPanel({ metrics: m });
      }
    }
  }

  function bindDropZone() {
    if (!_tree) return;
    // root drop zone（一次性绑定）
    _tree.addEventListener('dragover', e => {
      if (!_dragId) return;
      if (!e.target.closest('.sector-node')) {
        hideDropIndicator();
        e.preventDefault();
      }
    }, true);
    _tree.addEventListener('drop', e => {
      const node = e.target.closest('.sector-node');
      if (!node && _dragId) {
        e.preventDefault();
        move(_dragId, null, 0);
        _dragId = null;
      }
    }, true);

    _tree.addEventListener('dragstart', e => {
      const node = e.target.closest('.sector-node');
      if (!node) return;
      _dragId = parseInt(node.dataset.id);
      _dragParentId = findNodeParentId(state.sectorsTree, _dragId);
      node.style.opacity = '0.4';
      e.dataTransfer.effectAllowed = 'move';
    }, true);
    _tree.addEventListener('dragend', e => {
      const node = e.target.closest('.sector-node');
      if (node) node.style.opacity = '';
      hideDropIndicator();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      _dragId = null;
    }, true);
    _tree.addEventListener('dragover', e => {
      const node = e.target.closest('.sector-node');
      if (!node || !_dragId) return;
      const targetId = parseInt(node.dataset.id);
      if (targetId === _dragId) return;
      const rect = node.getBoundingClientRect();
      const mid = rect.top + rect.height * 0.5;
      if (e.clientY < mid) {
        showDropIndicator(node);
        node.classList.remove('drag-over');
      } else {
        hideDropIndicator();
        node.classList.add('drag-over');
      }
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }, true);
    _tree.addEventListener('dragleave', e => {
      const node = e.target.closest('.sector-node');
      if (node && !node.contains(e.relatedTarget)) {
        node.classList.remove('drag-over');
      }
    }, true);
    _tree.addEventListener('dragenter', e => {
      e.preventDefault();
    }, true);
    _tree.addEventListener('drop', e => {
      const node = e.target.closest('.sector-node');
      if (!node) { e.preventDefault(); move(_dragId, null, 0); _dragId = null; return; }
      if (!_dragId) return;
      e.preventDefault();
      const targetId = parseInt(node.dataset.id);
      if (targetId === _dragId) { _dragId = null; return; }

      hideDropIndicator();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));

      const rect = node.getBoundingClientRect();
      const mid = rect.top + rect.height * 0.5;
      if (e.clientY < mid) {
        const targetParentId = findNodeParentId(state.sectorsTree, targetId);
        const siblings = getSiblings(state.sectorsTree, targetParentId);
        const idx = siblings.findIndex(s => s.id === targetId);
        const beforeId = idx > 0 ? siblings[idx - 1].id : null;
        const beforeOrder = beforeId ? (findNodeIn(state.sectorsTree, beforeId)?.sort_order ?? 0) : -1024;
        const targetOrder = findNodeIn(state.sectorsTree, targetId)?.sort_order ?? 0;
        const newOrder = Math.floor((beforeOrder + targetOrder) / 2);
        move(_dragId, targetParentId, newOrder);
      } else {
        move(_dragId, targetId, 0);
      }
      _dragId = null;
    }, true);
  }

  window.Sector = { load, refresh, render, move, findNode, bindDropZone };
})();