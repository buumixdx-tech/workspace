// static/notes.js — 任务 #212 拆分
// 笔记 CRUD + inline note 渲染。依赖 window.state, window.Util, window.Modal, window.StockList。
// 公开 API:
//   Notes.load(code)                 — 拉单只 notes,刷右边 list
//   Notes.renderList(notes)          — 渲染右侧笔记区
//   Notes.create()                   — 新建笔记弹窗
//   Notes.edit(id)                   — 编辑笔记弹窗
//   Notes.delete(id)                 — 删除笔记
//   Notes.showInline(code, n)        — 在 stock-row 下展开 inline 下拉
//   Notes.collapseInline(code)       — 折叠 inline 下拉
//   Notes.switchNoteTab(tab)         — 笔记编辑器 edit/preview 切换

(function () {
  const { $, $$, api, htmlEscape, renderMd } = window.Util;

  // 后端 tags 字段始终返回 array;但旧的 db row 或者异常路径可能给字符串 — 兼容一下。
  function _parseTags(t) {
    if (Array.isArray(t)) return t;
    if (typeof t === 'string') {
      try { const v = JSON.parse(t); return Array.isArray(v) ? v : []; }
      catch { return []; }
    }
    return [];
  }

  function load(code) {
    return api(`/api/stocks/${encodeURIComponent(code)}/notes`)
      .then(json => renderList(json.data || []))
      .catch(() => renderList([]));
  }

  function renderList(notes) {
    const container = $('#notes-list');
    const btnAction = $('#btn-note-action');
    if (!notes.length) {
      if (container) {
        container.innerHTML = '<div class="empty-state" style="padding:20px;font-size:11px">暂无笔记</div>';
        container.style.display = '';
      }
      if (btnAction) {
        btnAction.textContent = '+ 新建';
        btnAction.onclick = () => create();
      }
      return;
    }
    if (container) container.style.display = 'none';
    if (btnAction) {
      btnAction.textContent = '✎ 编辑';
      btnAction.onclick = () => edit(notes[0].id);
    }
  }

  function create() {
    if (!state.selectedStockCode) { alert('请先选择一只股票'); return; }
    state.editingNoteId = null;
    Modal.show('📝 新建笔记', `
      <div class="form-group">
        <label class="form-label">标题 <span id="title-char-count" style="color:var(--text-dim);font-weight:normal"></span></label>
        <input id="f-note-title" class="form-input" placeholder="选填，不超过15字" maxlength="15">
      </div>
      <div class="form-group" style="flex:1;display:flex;flex-direction:column;">
        <label class="form-label">内容 <span id="body-char-count" style="color:var(--text-dim);font-weight:normal"></span></label>
        <textarea id="f-note-body" class="form-input" placeholder="支持 Markdown..." style="flex:1;min-height:180px;resize:none;font-family:var(--mono);font-size:12px;line-height:1.6;padding:8px;"></textarea>
      </div>
      <div class="form-group">
        <label class="form-label">标签（逗号分隔）</label>
        <input id="f-note-tags" class="form-input" placeholder="如：AI，业绩，全角半角逗号均可">
      </div>
      <div class="modal-footer" style="padding:0;border:none;margin-top:12px;display:flex;gap:8px;justify-content:flex-end">
        <button class="btn-secondary" onclick="Modal.close()">取消</button>
        <button class="btn-primary" id="btn-save-note">保存</button>
      </div>
    `);
    _bindNoteEditor({
      onSave: () => api(`/api/stocks/${encodeURIComponent(state.selectedStockCode)}/notes`, {
        method: 'POST', body: JSON.stringify(_readEditorPayload()),
      }),
      afterSave: () => { Modal.close(); load(state.selectedStockCode); },
    });
  }

  function edit(id) {
    state.editingNoteId = id;
    api(`/api/notes/${id}`)
      .then(json => {
        const n = json.data;
        const tags = _parseTags(n.tags);
        Modal.show('📝 编辑笔记', `
          <div class="form-group">
            <label class="form-label">标题 <span id="title-char-count" style="color:var(--text-dim);font-weight:normal"></span></label>
            <input id="f-note-title" class="form-input" placeholder="选填，不超过15字" maxlength="15" value="${htmlEscape(n.title || '')}">
          </div>
          <div class="form-group" style="flex:1;display:flex;flex-direction:column;">
            <label class="form-label">内容 <span id="body-char-count" style="color:var(--text-dim);font-weight:normal"></span></label>
            <textarea id="f-note-body" class="form-input" placeholder="支持 Markdown..." style="flex:1;min-height:180px;resize:none;font-family:var(--mono);font-size:12px;line-height:1.6;padding:8px;">${htmlEscape(n.body || '')}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label">标签（逗号分隔）</label>
            <input id="f-note-tags" class="form-input" placeholder="如：AI，业绩，全角半角逗号均可" value="${htmlEscape(tags.join(', '))}">
          </div>
          <div class="modal-footer" style="padding:0;border:none;margin-top:12px;display:flex;gap:8px;justify-content:flex-end">
            <button class="btn-danger" onclick="Notes.delete(${id})" style="margin-right:auto">删除</button>
            <button class="btn-secondary" onclick="Modal.close()">取消</button>
            <button class="btn-primary" id="btn-save-note">保存</button>
          </div>
        `);
        _bindNoteEditor({
          initial: { title: n.title, body: n.body, tags },
          onSave: () => api(`/api/notes/${id}`, {
            method: 'PUT', body: JSON.stringify(_readEditorPayload()),
          }),
          afterSave: () => { Modal.close(); load(state.selectedStockCode); },
        });
      })
      .catch(e => alert(e.message));
  }

  function remove(id) {
    if (!confirm('确认删除该笔记？')) return;
    state.editingNoteId = null;
    api(`/api/notes/${id}`, { method: 'DELETE' })
      .then(() => { Modal.close(); load(state.selectedStockCode); })
      .catch(e => alert(e.message));
  }

  function _readEditorPayload() {
    const title = $('#f-note-title').value.trim().slice(0, 15);
    const body = $('#f-note-body').value;
    const tags = $('#f-note-tags').value.split(/[,，]/).map(t => t.trim()).filter(Boolean);
    return { title, body, tags };
  }

  function _bindNoteEditor({ initial, onSave, afterSave }) {
    const titleInput = $('#f-note-title');
    const bodyInput = $('#f-note-body');
    const titleCountEl = $('#title-char-count');
    const bodyCountEl = $('#body-char-count');

    if (initial) {
      titleCountEl.textContent = `(${initial.title?.length || 0}/15)`;
      bodyCountEl.textContent = `(${initial.body?.length || 0}/300)`;
    }
    titleInput.addEventListener('input', () => {
      const len = titleInput.value.length;
      titleCountEl.textContent = `(${len}/15)`;
      titleCountEl.style.color = len > 15 ? 'var(--danger)' : 'var(--text-dim)';
    });
    bodyInput.addEventListener('input', () => {
      const len = bodyInput.value.length;
      bodyCountEl.textContent = `(${len}/300)`;
      bodyCountEl.style.color = len > 300 ? 'var(--danger)' : 'var(--text-dim)';
    });

    $('#btn-save-note').addEventListener('click', () => {
      if (typeof state.selectedStockCode !== 'string' || !state.selectedStockCode) {
        alert('请先在列表中点击选择一只股票'); return;
      }
      if (titleInput.value.length > 15) { alert('标题不超过15字'); return; }
      if (bodyInput.value.length > 300) { alert('内容不超过300字'); return; }
      onSave().then(afterSave).catch(e => alert(e.message));
    });
  }

  function switchNoteTab(tab) {
    $('#btn-edit').classList.toggle('active', tab === 'edit');
    $('#btn-preview').classList.toggle('active', tab === 'preview');
    if (tab === 'edit') {
      $('#note-body-input').style.display = 'flex';
      $('#note-preview').style.display = 'none';
    } else {
      $('#note-body-input').style.display = 'none';
      $('#note-preview').style.display = 'flex';
      $('#note-preview').innerHTML = renderMd($('#note-body-input').value);
    }
  }

  function save() {
    const title = $('#note-title-input').value.trim().slice(0, 15);
    const body = $('#note-body-input').value;
    const tags = $('#note-tags-input').value.split(',').map(t => t.trim()).filter(Boolean);
    const payload = { title, body, tags };
    const code = state.selectedStockCode;
    const id = state.editingNoteId;
    const promise = id
      ? api(`/api/notes/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
      : api(`/api/stocks/${encodeURIComponent(code)}/notes`, { method: 'POST', body: JSON.stringify(payload) });
    promise
      .then(() => { $('#note-editor').style.display = 'none'; $('#notes-list').style.display = 'flex'; load(code); })
      .catch(e => alert(e.message));
  }

  function cancel() {
    $('#note-editor').style.display = 'none';
    $('#notes-list').style.display = 'flex';
    state.editingNoteId = null;
  }

  // ── Inline note ────────────────────────────────────────────
  function showInline(code, n) {
    const stockRow = document.querySelector(`.stock-row[data-code="${cssEscape(code)}"]`);
    if (!stockRow) return;
    const tags = _parseTags(n.tags);
    const bodyHtml = n.body ? renderMd(n.body) : '<em style="color:var(--text-dim)">无内容</em>';
    const titleDisplay = n.title ? htmlEscape(n.title) : '<em style="color:var(--text-dim)">无标题</em>';

    let noteRow = document.getElementById('note-row-' + code);
    let isNew = false;
    if (!noteRow) {
      noteRow = document.createElement('div');
      noteRow.className = 'stock-note-row';
      noteRow.id = 'note-row-' + code;
      isNew = true;
    }
    noteRow.innerHTML = `
      <div class="note-editor-inline" id="note-inline-${code}">
        <div class="note-view-inline" id="note-view-${code}" onclick="Notes.collapseInline('${code}')">
          <div style="padding:6px 12px 4px;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
            <span style="font-size:13px;font-weight:700;color:var(--text-bright)">${titleDisplay}</span>
            ${tags.length ? `<div style="display:flex;gap:3px;flex-wrap:wrap">${tags.map(t => `<span class="tag">${htmlEscape(t)}</span>`).join('')}</div>` : ''}
            <button class="btn-ghost" style="margin-left:auto;font-size:10px;padding:2px 6px" onclick="event.stopPropagation();Notes.inlineEdit('${code}', ${n.id})">✎ 编辑</button>
          </div>
          <div class="note-body-view" id="note-body-${code}" style="font-size:12px;line-height:1.7;color:var(--text);font-family:var(--mono)">${bodyHtml}</div>
          <div class="note-toggle" id="note-toggle-${code}" style="display:none" onclick="event.stopPropagation();Notes.toggleBody('${code}')">展开全文 ▾</div>
        </div>
        <div class="note-edit-inline" id="note-edit-${code}" style="display:none">
          <div style="padding:6px 12px 0">
            <input id="inline-title-${code}" class="form-input" placeholder="标题（选填，不超过15字）" maxlength="15" value="${htmlEscape(n.title || '')}" style="font-size:12px;padding:4px 8px;">
          </div>
          <div style="padding:6px 12px 0">
            <textarea id="inline-body-${code}" class="form-input" placeholder="支持 Markdown..." style="min-height:80px;resize:none;font-family:var(--mono);font-size:11px;line-height:1.6;padding:6px 8px;">${htmlEscape(n.body || '')}</textarea>
          </div>
          <div id="inline-body-count-${code}" style="padding:0 12px 4px;font-size:10px;color:var(--text-dim)"></div>
          <div style="padding:4px 12px 8px;display:flex;gap:6px;align-items:center">
            <input id="inline-tags-${code}" class="form-input" placeholder="标签，逗号分隔" value="${htmlEscape(tags.join(', '))}" style="flex:1;font-size:11px;padding:4px 8px;">
            <button class="btn-secondary" style="font-size:11px;padding:4px 8px" onclick="Notes.inlineCancel('${code}')">取消</button>
            <button class="btn-primary" style="font-size:11px;padding:4px 10px" onclick="Notes.inlineSave('${code}', ${n.id})">保存</button>
          </div>
        </div>
      </div>
    `;

    if (isNew) {
      if (stockRow.nextSibling) stockRow.parentNode.insertBefore(noteRow, stockRow.nextSibling);
      else stockRow.parentNode.appendChild(noteRow);
    }

    noteRow.style.display = '';
    noteRow.style.maxHeight = '0';
    noteRow.style.overflow = 'hidden';
    noteRow.style.transition = 'max-height 0.3s ease';
    requestAnimationFrame(() => {
      noteRow.style.maxHeight = noteRow.scrollHeight + 'px';
      // 内容超过 180px 才显示「展开全文」
      const bodyEl = $('#note-body-' + code);
      const toggleEl = $('#note-toggle-' + code);
      if (bodyEl && toggleEl && bodyEl.scrollHeight > 180) {
        toggleEl.style.display = 'block';
      }
    });

    const bodyInput = $('#inline-body-' + code);
    const bodyCount = $('#inline-body-count-' + code);
    if (bodyInput && bodyCount) {
      bodyInput.addEventListener('input', () => {
        const len = bodyInput.value.length;
        bodyCount.textContent = `${len}/300`;
        bodyCount.style.color = len > 300 ? 'var(--danger)' : 'var(--text-dim)';
      });
      bodyCount.textContent = `${bodyInput.value.length}/300`;
    }
  }

  function collapseInline(code) {
    const noteRow = $('#note-row-' + code);
    if (!noteRow) return;
    noteRow.style.maxHeight = '0';
    setTimeout(() => { noteRow.style.display = 'none'; }, 300);
  }

  function inlineEdit(code) {
    const viewEl = $('#note-view-' + code);
    const editEl = $('#note-edit-' + code);
    if (!viewEl || !editEl) return;
    viewEl.style.display = 'none';
    editEl.style.display = 'block';
  }

  function inlineCancel(code) {
    const viewEl = $('#note-view-' + code);
    const editEl = $('#note-edit-' + code);
    if (!viewEl || !editEl) return;
    editEl.style.display = 'none';
    viewEl.style.display = 'block';
  }

  function inlineSave(code, noteId) {
    const title = $('#inline-title-' + code).value.trim().slice(0, 15);
    const body = $('#inline-body-' + code).value;
    const tagsStr = $('#inline-tags-' + code).value;
    if (title.length > 15) { alert('标题不超过15字'); return; }
    if (body.length > 300) { alert('内容不超过300字'); return; }
    const tags = tagsStr.split(/[,，]/).map(t => t.trim()).filter(Boolean);
    const payload = { title, body, tags };
    api(`/api/notes/${noteId}`, { method: 'PUT', body: JSON.stringify(payload) })
      .then(() => StockList.selectStock(code))
      .catch(e => alert('保存失败: ' + e.message));
  }

  function cssEscape(s) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
    return String(s).replace(/([!"#$%&'()*+,./:;<=>?@[\]^`{|}~])/g, '\\$1');
  }

  function toggleBody(code) {
    const body = $('#note-body-' + code);
    const toggle = $('#note-toggle-' + code);
    const noteRow = $('#note-row-' + code);
    if (!body || !toggle || !noteRow) return;
    const expanded = body.classList.toggle('note-body-expanded');
    toggle.textContent = expanded ? '收起 ▴' : '展开全文 ▾';
    // 容器 max-height 是 noteRow.scrollHeight,内容变高后要重新量一次
    noteRow.style.maxHeight = noteRow.scrollHeight + 'px';
  }

  window.Notes = {
    load, renderList, create, edit, delete: remove,
    save, cancel, switchNoteTab,
    showInline, collapseInline, toggleBody,
    inlineEdit, inlineCancel, inlineSave,
    _parseTags,
  };
})();