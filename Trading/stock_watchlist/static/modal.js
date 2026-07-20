// static/modal.js — 任务 #213 拆分
// 模态框基础设施 + 板块/配置 弹窗。依赖 window.state, window.Util, window.Sector, window.StockList。
// 公开 API:
//   Modal.show(title, bodyHtml)        — 显示弹窗
//   Modal.close()                       — 关闭弹窗
//   Modal.createSector()                — 新建板块弹窗
//   Modal.editSector()                  — 编辑当前板块
//   Modal.deleteSector()                — 删除当前板块
//   Modal.openConfig()                  — 板块配置弹窗
//   Modal.applyConfig()                 — 启动时把 localStorage config 推到后端

(function () {
  const { $, api } = window.Util;

  // capture 阶段: 弹窗内非按钮点击阻止冒泡到 sector/stock 处理器,
  // 但按钮自身的 onclick / input / textarea / .search-item 不阻止
  document.addEventListener('click', e => {
    const inModal = e.target.closest('#modal-box');
    const isButton = e.target.closest('button') || e.target.closest('input') || e.target.closest('textarea') || e.target.closest('.search-item');
    if (inModal && !isButton) e.stopPropagation();
  }, true);

  function show(title, bodyHtml) {
    $('#modal-title').textContent = title;
    $('#modal-body').innerHTML = bodyHtml;
    $('#modal-overlay').style.display = 'flex';
  }
  function close() {
    $('#modal-overlay').style.display = 'none';
  }

  // ── Sector config (localStorage) ──────────────────────────
  const SECTOR_CONFIG_KEY = 'sector_metrics_config';
  const DEFAULT_SECTOR_CONFIG = { period: 'today', topN: 3, weightMode: 'total' };

  function loadSectorConfig() {
    try {
      const raw = localStorage.getItem(SECTOR_CONFIG_KEY);
      if (raw) return Object.assign({}, DEFAULT_SECTOR_CONFIG, JSON.parse(raw));
    } catch {}
    return Object.assign({}, DEFAULT_SECTOR_CONFIG);
  }
  function saveSectorConfig(cfg) {
    try { localStorage.setItem(SECTOR_CONFIG_KEY, JSON.stringify(cfg)); } catch {}
  }
  let sectorConfig = loadSectorConfig();

  async function applyConfig() {
    try {
      await api('/api/sectors/metrics/config', {
        method: 'PUT',
        body: JSON.stringify({
          period: sectorConfig.period,
          top_n: sectorConfig.topN,
          weight_mode: sectorConfig.weightMode,
        }),
      });
    } catch (e) {
      console.warn('applySectorConfig failed:', e.message);
    }
  }

  // ── Sector CRUD modals ────────────────────────────────────
  function createSector(parentId = null) {
    show('新建板块', `
      <div class="form-group">
        <label class="form-label">板块名称</label>
        <input id="f-name" class="form-input" placeholder="例如：AI板块">
      </div>
      <div class="form-group">
        <label class="form-label">颜色</label>
        <input id="f-color" type="color" value="#1a8cff" style="width:60px;height:28px;border:none;background:none;cursor:pointer">
      </div>
      <div class="modal-footer" style="padding:0;border:none;margin-top:12px">
        <button class="btn-secondary" onclick="Modal.close()">取消</button>
        <button class="btn-primary" onclick="
          const name = $('#f-name').value.trim();
          const color = $('#f-color').value;
          if (!name) { alert('请输入板块名称'); return; }
          api('/api/sectors', { method:'POST', body: JSON.stringify({ name, color }) })
            .then(() => { Modal.close(); return Sector.load(); })
            .catch(e => alert(e.message));
        ">创建</button>
      </div>
    `);
  }

  function editSector() {
    if (!state.currentSectorId) return;
    const node = Sector.findNode(state.currentSectorId);
    if (!node) return;
    show('编辑板块', `
      <div class="form-group">
        <label class="form-label">板块名称</label>
        <input id="f-name" class="form-input" value="${window.Util.htmlEscape(node.name)}">
      </div>
      <div class="form-group">
        <label class="form-label">颜色</label>
        <input id="f-color" type="color" value="${node.color || '#1a8cff'}" style="width:60px;height:28px;border:none;background:none;cursor:pointer">
      </div>
      <div class="modal-footer" style="padding:0;border:none;margin-top:12px">
        <button class="btn-secondary" onclick="Modal.close()">取消</button>
        <button class="btn-primary" onclick="
          const name = $('#f-name').value.trim();
          const color = $('#f-color').value;
          if (!name) { alert('请输入板块名称'); return; }
          api('/api/sectors/${state.currentSectorId}', { method:'PUT', body: JSON.stringify({ name, color }) })
            .then(() => { Modal.close(); return Sector.load(); })
            .catch(e => alert(e.message));
        ">保存</button>
      </div>
    `);
  }

  function deleteSector() {
    if (!state.currentSectorId) return;
    if (!confirm('删除板块会同时删除所有子板块，确认？')) return;
    api(`/api/sectors/${state.currentSectorId}`, { method: 'DELETE' })
      .then(() => {
        state.currentSectorId = null;
        state.currentStocks = [];
        state.currentDirectStocks = [];
        state.selectedStockCode = null;
        const container = $('#stock-list');
        if (container) container.innerHTML = '';
        $('#sector-title').textContent = '选择板块';
        $('#sector-actions').style.display = 'none';
        StockList.closeDetail();
        return Sector.load();
      })
      .catch(e => alert(e.message));
  }

  function openConfig() {
    const c = sectorConfig;
    show('⚙ 板块配置', `
      <div class="form-group">
        <label class="form-label">涨跌幅周期</label>
        <select id="cfg-period" class="form-select">
          <option value="today" ${c.period === 'today' ? 'selected' : ''}>当日 (today)</option>
          <option value="5d" ${c.period === '5d' ? 'selected' : ''} disabled>5 日 (5d, 暂未实现)</option>
          <option value="20d" ${c.period === '20d' ? 'selected' : ''} disabled>20 日 (20d, 暂未实现)</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">权重模式</label>
        <select id="cfg-weight" class="form-select">
          <option value="total" ${c.weightMode === 'total' ? 'selected' : ''}>总市值加权 (default)</option>
          <option value="circulating" ${c.weightMode === 'circulating' ? 'selected' : ''}>流通市值加权</option>
          <option value="equal" ${c.weightMode === 'equal' ? 'selected' : ''}>等权</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Top N (涨/跌前几名)</label>
        <select id="cfg-topn" class="form-select">
          ${[1,2,3,5,8,10,15,20].map(n => `<option value="${n}" ${c.topN === n ? 'selected' : ''}>${n}</option>`).join('')}
        </select>
      </div>
      <div style="font-size:11px;color:var(--text-dim);margin-top:8px">
        配置写入 localStorage, 跨会话保持; 改动立即触发重算。
      </div>
      <div class="modal-footer" style="padding:0;border:none;margin-top:12px">
        <button class="btn-secondary" onclick="Modal.close()">取消</button>
        <button class="btn-primary" id="btn-save-config">应用</button>
      </div>
    `);

    $('#btn-save-config').addEventListener('click', async () => {
      sectorConfig = {
        period: $('#cfg-period').value,
        weightMode: $('#cfg-weight').value,
        topN: parseInt($('#cfg-topn').value, 10),
      };
      saveSectorConfig(sectorConfig);
      close();
      await applyConfig();
      await Sector.load();
      if (state.currentSectorId) await StockList.load(state.currentSectorId);
    });
  }

  window.Modal = { show, close, createSector, editSector, deleteSector, openConfig, applyConfig };
})();