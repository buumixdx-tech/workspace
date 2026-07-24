// avlib UI: poster-wall browse + filters + search + detail modal.

const PAGE = 24;
const state = { offset: 0, total: 0, search: '', filters: {}, sort: 'added' };
const $ = (id) => document.getElementById(id);

async function api(path) {
  const r = await fetch(path);
  return r.json();
}

function firstActress(s) {
  try { const a = JSON.parse(s || '[]'); return a[0] || ''; } catch { return ''; }
}

function fmtDur(sec) {
  if (!sec) return '';
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return h ? `${h}h${m}m` : `${m}m`;
}

async function loadList() {
  const p = new URLSearchParams();
  p.set('limit', PAGE);
  p.set('offset', state.offset);
  p.set('sort', state.sort);
  for (const [k, v] of Object.entries(state.filters)) if (v) p.set(k, v);
  let data;
  if (state.search) {
    data = { items: (await api('/api/search?q=' + encodeURIComponent(state.search) + '&limit=40')).items, total: 0 };
  } else {
    data = await api('/api/movies?' + p);
  }
  state.total = data.total || data.items.length;
  renderGrid(data.items);
  renderPager();
}

function renderGrid(items) {
  const g = $('grid');
  if (!items.length) { g.innerHTML = '<p style="color:var(--muted);grid-column:1/-1;text-align:center">无结果</p>'; return; }
  g.innerHTML = items.map((m) => {
    const actress = firstActress(m.actresses);
    const badges = [];
    if (m.is_uncensored_leak) badges.push('<span class="badge uc">无码</span>');
    return `<div class="card" data-code="${m.code}">
      <img class="cover" loading="lazy" src="/api/cover/${encodeURIComponent(m.code)}" onerror="this.style.opacity=.2">
      <div class="meta">
        <div class="title">${m.title_cn || m.title || m.code}</div>
        <div class="sub"><span>${actress || '—'}</span><span>${m.released_date ? m.released_date.slice(0,4) : ''} ${badges.join('')}</span></div>
      </div>
    </div>`;
  }).join('');
  g.querySelectorAll('.card').forEach((c) =>
    c.addEventListener('click', () => openDetail(c.dataset.code))
  );
}

function renderPager() {
  const page = Math.floor(state.offset / PAGE) + 1;
  const pages = Math.ceil(state.total / PAGE) || 1;
  $('page-info').textContent = `${page} / ${pages}  (共 ${state.total})`;
  $('prev').disabled = state.offset === 0;
  $('next').disabled = state.offset + PAGE >= state.total;
}

async function openDetail(code) {
  const m = await api('/api/movies/' + encodeURIComponent(code));
  if (m.error) return;
  const chips = (arr, key) =>
    (arr || []).map((v) => `<span class="chip" data-key="${key}" data-val="${encodeURIComponent(v)}">${v}</span>`).join(' ');
  let acts;
  try { acts = JSON.parse(m.actresses || '[]'); } catch { acts = []; }
  let gens; try { gens = JSON.parse(m.genres || '[]'); } catch { gens = []; }
  let labs; try { labs = JSON.parse(m.labels || '[]'); } catch { labs = []; }
  let mks; try { mks = JSON.parse(m.markers || '[]'); } catch { mks = []; }
  let srs; try { srs = JSON.parse(m.series || '[]'); } catch { srs = []; }

  // Group videos by variant; preserve the priority order from the API
  // (censored → leak → '' → others).
  const variantOrder = [];
  const byVariant = {};
  for (const v of m.videos || []) {
    if (!(v.variant in byVariant)) { byVariant[v.variant] = []; variantOrder.push(v.variant); }
    byVariant[v.variant].push(v);
  }
  const variantLabel = (v) => v === '' ? 'untagged' : v;
  const variantTabs = variantOrder.length > 1
    ? `<div class="part-bar variant-tabs">${variantOrder.map((v, i) =>
        `<button class="part-btn variant-tab${i === 0 ? ' active' : ''}" data-variant="${encodeURIComponent(v)}">${variantLabel(v)} <span class="n">(${byVariant[v].length})</span></button>`
      ).join('')}</div>` : '';
  const videoRows = (variant, idx) => byVariant[variant].map((v) => {
    const size = (v.size_bytes / 1024 / 1024 / 1024).toFixed(2);
    const dim = v.width && v.height ? ` · ${v.width}×${v.height}` : '';
    const probeBadge = v.probe_status === 'probed'
      ? `<span class="badge vs" title="v=${v.v_codec||'-'} a=${v.a_codec||'-'}">${v.width||'-'}×${v.height||'-'}</span>`
      : `<span class="badge" title="probe pending">?probe</span>`;
    return `<div class="video-row" data-vid="${v.id}" style="${variantOrder.length > 1 && variantOrder[idx] !== variant ? 'display:none' : ''}">
      <span class="video-label">${v.part_label ? 'Part ' + v.part_label : 'Part 1'}</span>
      <span class="video-file">${v.filename}</span>
      <span class="video-size">${size} GB${dim}</span>
      ${probeBadge}
      <select class="variant-select" data-vid="${v.id}">
        <option value="">untagged</option>
        <option value="censored"${v.variant === 'censored' ? ' selected' : ''}>censored</option>
        <option value="leak"${v.variant === 'leak' ? ' selected' : ''}>leak</option>
      </select>
      <button class="probe-btn" data-vid="${v.id}" title="ffprobe">⚙</button>
    </div>`;
  }).join('');

  const videoPanel = (m.videos || []).length ? `
    <div class="row"><span class="k">文件</span>
      ${variantTabs}
      <div class="video-list">
        ${variantOrder.map((v, i) => videoRows(v, i)).join('')}
      </div>
    </div>` : '';

  $('modal-card').innerHTML = `
    <button class="close">×</button>
    <div class="modal-body">
      <img class="modal-cover" src="/api/cover/${encodeURIComponent(m.code)}" onerror="this.style.opacity=.2">
      <div>
        <h2>${m.title_cn || m.title || m.code}</h2>
        <div class="code">${m.code}</div>
        ${m.title && m.title !== m.title_cn ? `<div class="row"><span class="k">原文</span>${m.title}</div>` : ''}
        <div class="row"><span class="k">演员</span><div class="chips">${chips(acts, 'actress')}</div></div>
        <div class="row"><span class="k">厂牌</span><div class="chips">${chips(mks, 'maker')}</div></div>
        <div class="row"><span class="k">发行</span><div class="chips">${chips(labs, '')}</div></div>
        <div class="row"><span class="k">类型</span><div class="chips">${chips(gens, 'genre')}</div></div>
        <div class="row"><span class="k">系列</span><div class="chips">${chips(srs, 'series')}</div></div>
        <div class="row"><span class="k">发行日</span>${m.released_date || '—'}</div>
        <div class="row"><span class="k">时长</span>${fmtDur(m.duration_sec)}</div>
        <div class="row"><span class="k">标记</span>
          ${m.is_uncensored_leak ? '<span class="badge uc">无码流出</span>' : ''}
        </div>
        ${videoPanel}
        <button class="play-btn">▶ 播放</button>
      </div>
    </div>`;
  $('modal').classList.remove('hidden');
  $('modal-card').querySelectorAll('.chip').forEach((c) =>
    c.addEventListener('click', () => {
      if (!c.dataset.key) return;
      state.filters[c.dataset.key] = decodeURIComponent(c.dataset.val);
      state.offset = 0; state.search = '';
      syncFilterUI();
      loadList();
      closeModal();
    })
  );

  // Variant tabs: show only rows of selected variant
  $('modal-card').querySelectorAll('.variant-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      const v = decodeURIComponent(tab.dataset.variant);
      $('modal-card').querySelectorAll('.variant-tab').forEach((t) => t.classList.toggle('active', t === tab));
      $('modal-card').querySelectorAll('.video-row').forEach((row) => {
        const sel = row.querySelector('.variant-select');
        row.style.display = (sel && sel.value === v) ? '' : 'none';
      });
    });
  });
  // PATCH on variant change
  $('modal-card').querySelectorAll('.variant-select').forEach((sel) => {
    sel.addEventListener('change', async (e) => {
      const vid = parseInt(sel.dataset.vid, 10);
      const variant = sel.value;
      try {
        const r = await fetch(`/api/videos/${vid}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ variant }),
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        // Reload detail to refresh group ordering
        openDetail(m.code);
      } catch (err) {
        alert('改 variant 失败: ' + err.message);
      }
    });
  });
  // Probe trigger
  $('modal-card').querySelectorAll('.probe-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const vid = parseInt(btn.dataset.vid, 10);
      btn.disabled = true; btn.textContent = '…';
      try {
        const r = await fetch(`/api/internal/probe/${vid}`, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        openDetail(m.code);
      } catch (err) {
        alert('probe 失败: ' + err.message);
        btn.disabled = false; btn.textContent = '⚙';
      }
    });
  });

  const pb = $('modal-card').querySelector('.play-btn');
  if (pb) pb.addEventListener('click', () => openPlayer(m));
}

async function openPlayer(m) {
  const code = m.code;
  const title = m.title_cn || m.title || code;
  // group videos by variant, preserve priority order from API
  const variantOrder = [];
  const byVariant = {};
  for (const v of m.videos || []) {
    if (!(v.variant in byVariant)) { byVariant[v.variant] = []; variantOrder.push(v.variant); }
    byVariant[v.variant].push(v);
  }
  const variantLabel = (v) => v === '' ? 'untagged' : v;
  const variantBar = variantOrder.length > 1
    ? `<div class="part-bar variant-tabs">${variantOrder.map((v, i) =>
        `<button class="part-btn variant-tab${i === 0 ? ' active' : ''}" data-variant="${encodeURIComponent(v)}">${variantLabel(v)} <span class="n">(${byVariant[v].length}p)</span></button>`
      ).join('')}</div>` : '';

  const overlay = document.createElement('div');
  overlay.className = 'player-overlay';
  overlay.innerHTML = `
    <div class="player-box">
      <button class="close">×</button>
      ${variantBar}
      <video autoplay playsinline preload="metadata"></video>
      <div class="player-bar">
        <span class="player-title"></span>
        <span class="player-parts"></span>
        <a class="vlc-link" href="/api/playlist/${encodeURIComponent(code)}.m3u" download>⬇ 用 VLC/mpv 打开 (.m3u)</a>
      </div>
      <div class="player-note">加载中…</div>
    </div>`;
  document.body.appendChild(overlay);

  const v = overlay.querySelector('video');
  const titleEl = overlay.querySelector('.player-title');
  const noteEl = overlay.querySelector('.player-note');

  // Plyr: single instance for the whole overlay lifetime. Switching source
  // (variant or part) uses the standard `player.source = {...}` setter, which
  // gives us native mobile touch-drag scrubbing on the progress bar.
  let player = null;
  if (window.Plyr) {
    player = new Plyr(v, {
      controls: ['play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'fullscreen'],
      seekTime: 10,
      hideControls: true,
      resetOnEnd: true,
      fullscreen: {
        enabled: true,
        fallback: false,   // Plyr's CSS fallback only fills .plyr__video-wrapper,
                           // which is nested inside .player-box (max-width 1100px).
                           // We provide our own CSS fallback on .player-overlay.
        iosNative: true,   // iOS Safari: use webkitEnterFullscreen() (true fullscreen).
      },
    });
    player.on('waiting', () => { noteEl.textContent = '缓冲中…'; noteEl.style.color = '#e8a23d'; });
    player.on('canplay', () => { noteEl.textContent = ''; });
    player.on('stalled', () => { noteEl.textContent = '网络慢,等待数据…'; noteEl.style.color = '#e8a23d'; });
    player.on('error', () => {
      noteEl.innerHTML = `<b>浏览器无法播放此格式（${code}）。</b>请点上面的 .m3u 用 VLC/mpv 打开。`;
      noteEl.style.color = '#e8a23d';
    });
    // Fullscreen escalation: Plyr requests fullscreen on its internal
    // .plyr__video-wrapper, which often fails when the wrapper is nested in a
    // positioned overlay (stacking context). If that happens we escalate to
    // fullscreening the whole .player-overlay; if that also fails, fall back
    // to a CSS-only fullscreen that fills the viewport.
    player.on('enterfullscreen', () => {
      if (v.webkitDisplayingFullscreen) return; // iOS native — leave as-is
      if (document.fullscreenElement) {
        overlay.classList.add('is-fullscreen');
        return;
      }
      // Plyr's native call failed — try the overlay itself.
      const req = overlay.requestFullscreen?.() || overlay.webkitRequestFullscreen?.();
      if (req && typeof req.then === 'function') {
        req.then(() => overlay.classList.add('is-fullscreen'))
           .catch(() => overlay.classList.add('is-fullscreen'));
      } else {
        overlay.classList.add('is-fullscreen');
      }
    });
    player.on('exitfullscreen', () => {
      overlay.classList.remove('is-fullscreen');
      if (document.fullscreenElement === overlay) document.exitFullscreen?.().catch(() => {});
    });
  } else {
    // Plyr script didn't load (offline?). Fall back to native controls so the
    // video still plays — touch-drag just won't be as nice.
    v.setAttribute('controls', '');
  }

  let curVariant = variantOrder[0];
  let curPartIdx = 0;        // for ended→next in multipart
  let onEnded = null;        // swapped per multipart playlist

  function setEndedHandler(fn) {
    if (onEnded && player) player.off('ended', onEnded);
    onEnded = fn;
    if (fn && player) player.on('ended', fn);
  }

  function setSrc(streamUrl) {
    if (player) {
      player.source = { type: 'video', sources: [{ src: streamUrl, type: 'video/mp4' }] };
    } else {
      v.src = streamUrl;
    }
  }

  async function playVariant(variant) {
    curVariant = variant;
    overlay.querySelectorAll('.variant-tab').forEach((t) => t.classList.toggle('active', decodeURIComponent(t.dataset.variant) === variant));
    const vs = byVariant[variant] || [];
    const partCount = vs.length;
    const vq = `?variant=${encodeURIComponent(variant)}`;
    overlay.querySelector('.player-parts').innerHTML = '';
    titleEl.textContent = title + (variantOrder.length > 1 ? '  ·  ' + variantLabel(variant) : '') + (partCount > 1 ? `  ·  ${partCount}p concat` : '');
    noteEl.textContent = '加载中…';
    noteEl.style.color = '';
    setEndedHandler(null);     // clear prior multipart auto-advance, if any
    try {
      const r = await fetch(`/api/play/${encodeURIComponent(code)}${vq}`).then((x) => x.json());
      if (r.mode === 'direct') {
        setSrc(`/api/stream/${encodeURIComponent(code)}${vq}`);
        (player || v).play?.().catch(() => {});
        if (player) noteEl.textContent = '加载中…';
      } else if (r.mode === 'multipart') {
        // Multi-part: play parts sequentially in-browser. Each part is a
        // single-file stream (?part=N), so per-part progress bar + seek work
        // natively. Plyr 'ended' auto-advances to the next part.
        const parts = r.parts || [];
        curPartIdx = 0;
        const partsEl = overlay.querySelector('.player-parts');
        // Render part switch buttons (Part A / Part B / ...)
        partsEl.innerHTML = parts.map((p, i) =>
          `<button class="part-btn" data-idx="${i}" type="button">Part ${p.label}</button>`
        ).join('');
        const playPart = (i) => {
          curPartIdx = i;
          titleEl.textContent = title
            + (variantOrder.length > 1 ? '  ·  ' + variantLabel(curVariant) : '')
            + `  ·  Part ${parts[i].label} (${i+1}/${parts.length})`;
          noteEl.textContent = `加载 Part ${parts[i].label}…`;
          noteEl.style.color = '';
          partsEl.querySelectorAll('.part-btn').forEach((b, bi) =>
            b.classList.toggle('active', bi === i));
          setSrc(parts[i].streamUrl);
          (player || v).play?.().catch(() => {});
        };
        partsEl.querySelectorAll('.part-btn').forEach((b) => {
          b.addEventListener('click', () => playPart(parseInt(b.dataset.idx, 10)));
        });
        setEndedHandler(() => {
          if (curPartIdx < parts.length - 1) playPart(curPartIdx + 1);
          else noteEl.textContent = '播放结束';
        });
        playPart(0);
      } else if (r.mode === 'unsupported') {
        // Browser can't decode this codec — fall back to native controls so
        // the user sees the file at least, and surface the VLC .m3u link.
        if (player) {
          try { player.pause(); } catch {}
          player.destroy();
          player = null;
        }
        v.removeAttribute('src');
        try { v.load(); } catch {}
        v.setAttribute('controls', '');
        noteEl.textContent = `该视频编码为 ${r.v_codec || '未知'}(${r.container || ''}),浏览器暂不支持,请用 VLC/mpv 打开 .m3u`;
        noteEl.style.color = '#e8a23d';
      } else {
        noteEl.textContent = '无法播放: ' + (r.mode || '未知');
        noteEl.style.color = '#e8a23d';
      }
    } catch (e) {
      noteEl.textContent = '加载失败: ' + e.message;
      noteEl.style.color = '#e8a23d';
    }
  }

  overlay.querySelectorAll('.variant-tab').forEach((tab) =>
    tab.addEventListener('click', () => playVariant(decodeURIComponent(tab.dataset.variant)))
  );
  playVariant(variantOrder[0]);

  const close = () => {
    setEndedHandler(null);
    if (player) { try { player.destroy(); } catch {} player = null; }
    overlay.remove();
  };
  overlay.querySelector('.close').onclick = close;
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
}

function closeModal() { $('modal').classList.add('hidden'); }

async function loadFacets() {
  const f = await api('/api/facets');
  const fill = (id, items) => {
    const sel = $(id);
    items.forEach((it) => {
      const o = document.createElement('option');
      o.value = it.name; o.textContent = `${it.name} (${it.n})`;
      sel.appendChild(o);
    });
  };
  fill('f-maker', f.makers);
  fill('f-genre', f.genres);
  fill('f-series', f.series);
  fill('f-actress', f.actresses);
  fill('f-year', f.years.map((y) => ({ name: y.y, n: y.n })));
}

function syncFilterUI() {
  $('f-maker').value = state.filters.maker || '';
  $('f-genre').value = state.filters.genre || '';
  $('f-series').value = state.filters.series || '';
  $('f-actress').value = state.filters.actress || '';
  $('f-year').value = state.filters.year || '';
  $('f-uncensored').checked = state.filters.uncensored === '1';
}

// ---- scan / refresh video source ----
let scanTimer = null;
function setScanUI(running, text) {
  const btn = $('refresh'), st = $('scan-status');
  if (btn) btn.disabled = running;
  if (st) {
    st.textContent = text || '';
    st.classList.toggle('active', !!running);
  }
}
async function startScan() {
  setScanUI(true, '启动中…');
  try {
    await fetch('/api/scan', { method: 'POST' }); // 202 started or 409 already-running -> poll either way
    pollScan();
  } catch (e) { setScanUI(false, '启动失败: ' + e.message); }
}
async function pollScan() {
  clearTimeout(scanTimer);
  try {
    const s = await (await fetch('/api/scan/status')).json();
    if (s.running) {
      const last = s.log && s.log.length ? s.log[s.log.length - 1] : '';
      setScanUI(true, '扫描中… ' + String(last).slice(0, 70));
      scanTimer = setTimeout(pollScan, 2000);
    } else {
      const sm = s.summary;
      if (sm) {
        const bits = [`+${sm.scraped} 新`];
        if (sm.error) bits.push(`${sm.error} 错`);
        if (sm.skipped) bits.push(`${sm.skipped} 已存在`);
        if (sm.conflicts) bits.push(`${sm.conflicts} 冲突`);
        if (sm.videosTotal != null) bits.push(`共 ${sm.videosTotal} 视频`);
        setScanUI(false, (s.exitCode === 0 ? '✓ ' : '⚠ ') + bits.join(' · '));
      } else {
        setScanUI(false, s.exitCode === 0 ? '✓ 完成' : '⚠ exit ' + s.exitCode);
      }
      if (sm && sm.scraped > 0) loadList(); // surface new entries
      const st = $('scan-status');
      setTimeout(() => { if (st && !st.classList.contains('active')) st.textContent = ''; }, 6000);
    }
  } catch (e) { scanTimer = setTimeout(pollScan, 3000); }
}
async function checkScanStatus() {
  // resume polling if a scan is mid-flight (page refresh / other tab triggered it)
  try {
    const s = await (await fetch('/api/scan/status')).json();
    if (s.running) { setScanUI(true, '扫描中…'); pollScan(); }
  } catch (e) { /* ignore */ }
}

function bind() {
  let st;
  $('search').addEventListener('input', (e) => {
    clearTimeout(st);
    st = setTimeout(() => { state.search = e.target.value.trim(); state.offset = 0; loadList(); }, 250);
  });
  $('sort').addEventListener('change', (e) => { state.sort = e.target.value; loadList(); });
  const fmap = { 'f-maker': 'maker', 'f-genre': 'genre', 'f-series': 'series', 'f-actress': 'actress', 'f-year': 'year' };
  for (const [id, key] of Object.entries(fmap)) {
    $(id).addEventListener('change', (e) => { state.filters[key] = e.target.value; state.offset = 0; state.search = ''; loadList(); });
  }
  $('f-uncensored').addEventListener('change', (e) => { state.filters.uncensored = e.target.checked ? '1' : ''; state.offset = 0; loadList(); });
  $('clear-filters').addEventListener('click', () => {
    state.filters = {}; state.offset = 0; state.search = ''; $('search').value = '';
    syncFilterUI(); loadList();
  });
  $('prev').addEventListener('click', () => { state.offset = Math.max(0, state.offset - PAGE); loadList(); });
  $('next').addEventListener('click', () => { if (state.offset + PAGE < state.total) { state.offset += PAGE; loadList(); } });
  $('modal').querySelector('.modal-bg').addEventListener('click', closeModal);
  $('modal-card').addEventListener('click', (e) => { if (e.target.classList.contains('close')) closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  $('refresh').addEventListener('click', startScan);

  // Mobile filter modal: re-use existing <aside id="sidebar"> as a modal overlay.
  const mfb = document.getElementById('mobile-filters-btn');
  if (mfb) mfb.addEventListener('click', () => {
    const aside = document.getElementById('sidebar');
    if (!aside) return;
    aside.classList.toggle('open');
    let bd = document.getElementById('sidebar-bd');
    if (!bd) {
      bd = document.createElement('div');
      bd.id = 'sidebar-bd';
      document.body.appendChild(bd);
      bd.addEventListener('click', () => {
        aside.classList.remove('open');
        bd.classList.remove('open');
      });
    }
    bd.classList.toggle('open');
  });
  // close-x in sidebar header
  const cx = document.querySelector('aside .sidebar-header .close-x');
  if (cx) cx.addEventListener('click', () => {
    const a = document.getElementById('sidebar');
    const bd = document.getElementById('sidebar-bd');
    if (a) a.classList.remove('open');
    if (bd) bd.classList.remove('open');
  });
}

(async function init() {
  bind();
  await loadFacets();
  await loadList();
  checkScanStatus(); // resume polling if a scan is mid-flight
})();
