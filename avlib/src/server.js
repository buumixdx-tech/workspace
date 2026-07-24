// Web server: API + static UI. Uses node:http (zero extra deps).
// Run: node src/server.js  (or: npm start)
//   --port 8123  --host 0.0.0.0   (defaults)

import { createServer, request as httpRequest, Agent } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { loadConfig } from './config.js';
import {
  openDb,
  getMovie as getMovieRow,
  getVideosByMovie,
  getVideo,
  listVideos,
  updateVideoVariant,
  updateVideoPartLabel,
  applyProbeToVideo,
  markProbeFailed,
  getReviewQueue,
} from './db.js';
import { webdavUrl, probeMedia } from './probe.js';
import { createClient } from 'webdav';
import { spawn } from 'node:child_process';

const argv = process.argv.slice(2);
const portIdx = argv.indexOf('--port');
const hostIdx = argv.indexOf('--host');

const config = loadConfig();
const PORT = portIdx !== -1 ? parseInt(argv[portIdx + 1], 10) : (config.server?.port ?? 8123);
const HOST = hostIdx !== -1 ? argv[hostIdx + 1] : (config.server?.host ?? '0.0.0.0');

const db = openDb(config.db.path);
const COVER_CACHE = path.join(path.dirname(config.db.path), 'covers');
await mkdir(COVER_CACHE, { recursive: true });

// Last-resort safety net: a single bad stream() request shouldn't take down
// the whole server. Log + keep the process alive. (Per-request try/catch in
// the createServer callback covers normal errors; this catches async /
// stream-pipeline errors that escape the request handler.)
process.on('uncaughtException', (e) => {
  console.error('[uncaughtException]', e && e.stack || e);
});
process.on('unhandledRejection', (e) => {
  console.error('[unhandledRejection]', e && e.stack || e);
});

const WEB_DIR = fileURLToPath(new URL('./web/', import.meta.url));
// Shared HTTP keep-alive agent for the /api/stream Range proxy — reuses the
// socket pool across sequential Range GETs, avoiding cold-start per request.
const streamAgent = new Agent({ keepAlive: true, maxSockets: 32, keepAliveMsecs: 30000 });

const client = createClient(config.webdav.baseUrl, {
  username: config.webdav.username,
  password: config.webdav.password,
});

// ---- auth (optional: enabled only if config.auth.password is set) ----
const AUTH_PASSWORD = config.auth?.password || '';
const AUTH_TOKEN = AUTH_PASSWORD
  ? crypto.createHmac('sha256', AUTH_PASSWORD).update('avlib-v1').digest('hex')
  : '';

function authOk(req) {
  if (!AUTH_PASSWORD) return true;
  const m = /(?:^|;\s*)avlib_auth=([^;]+)/.exec(req.headers.cookie || '');
  return !!m && m[1] === AUTH_TOKEN;
}

async function handleLogin(req, res) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const pw = new URLSearchParams(Buffer.concat(chunks).toString()).get('password') || '';
  if (pw && pw === AUTH_PASSWORD) {
    res.writeHead(200, {
      'Set-Cookie': `avlib_auth=${AUTH_TOKEN}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000`,
      'Content-Type': 'application/json',
    });
    res.end('{"ok":true}');
  } else {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    res.end('{"ok":false}');
  }
}

function handleLogout(res) {
  res.writeHead(200, {
    'Set-Cookie': 'avlib_auth=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0',
    'Content-Type': 'application/json',
  });
  res.end('{"ok":true}');
}
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function json(res, obj, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}

function parseUrl(reqUrl) {
  const u = new URL(reqUrl, 'http://x');
  const query = {};
  for (const [k, v] of u.searchParams) query[k] = v;
  return { pathname: u.pathname, query };
}

// ---------- API ----------

function listMovies(q) {
  const limit = Math.min(parseInt(q.limit) || 24, 100);
  const offset = parseInt(q.offset) || 0;
  const orderBy =
    { added: 'scrape_added_at DESC', released: 'released_at DESC', title: 'title_cn ASC' }[q.sort] ||
    'scrape_added_at DESC';
  const where = ["scrape_status='scraped'"];
  const params = [];
  const addJson = (col, val) => {
    if (val) {
      where.push(`EXISTS (SELECT 1 FROM json_each(${col}) WHERE value=?)`);
      params.push(val);
    }
  };
  addJson('actresses', q.actress);
  addJson('markers', q.maker);
  addJson('genres', q.genre);
  addJson('series', q.series);
  if (q.uncensored === '1') where.push('is_uncensored_leak=1');
  if (q.year) {
    where.push('released_date LIKE ?');
    params.push(q.year + '-%');
  }
  const wsql = 'WHERE ' + where.join(' AND ');
  const total = db.prepare(`SELECT COUNT(*) n FROM movies ${wsql}`).get(...params).n;
  const items = db
    .prepare(
      `SELECT code, title_cn, title, actresses, released_date, duration_sec,
              is_uncensored_leak
       FROM movies ${wsql} ORDER BY ${orderBy} LIMIT ? OFFSET ?`
    )
    .all(...params, limit, offset);
  return { items, total, offset, limit };
}

function getMovie(code) {
  const m = getMovieRow(db, code);
  if (!m) return null;
  delete m.raw_json; // not needed by UI
  m.videos = getVideosByMovie(db, code);
  return m;
}

function searchMovies(q, limit = 20) {
  const like = '%' + q + '%';
  return db
    .prepare(
      `SELECT code, title_cn, title, actresses, released_date
       FROM movies
       WHERE scrape_status='scraped' AND (
         code LIKE ? OR title_cn LIKE ? OR title LIKE ? OR title_en LIKE ?
         OR EXISTS (SELECT 1 FROM json_each(actresses) WHERE value LIKE ?)
       )
       ORDER BY scrape_added_at DESC LIMIT ?`
    )
    .all(like, like, like, like, like, limit);
}

function facets() {
  const sql = (col, limit) =>
    `SELECT value name, COUNT(*) n FROM movies, json_each(${col})
     WHERE scrape_status='scraped' GROUP BY value ORDER BY n DESC ${limit ? 'LIMIT ' + limit : ''}`;
  const years = db
    .prepare(
      `SELECT substr(released_date,1,4) y, COUNT(*) n FROM movies
       WHERE scrape_status='scraped' AND released_date IS NOT NULL
       GROUP BY y ORDER BY y DESC`
    )
    .all();
  return {
    makers: db.prepare(sql('markers', 0)).all(),
    genres: db.prepare(sql('genres', 40)).all(),
    series: db.prepare(sql('series', 40)).all(),
    actresses: db.prepare(sql('actresses', 60)).all(),
    years,
  };
}

async function cover(res, code) {
  const cacheFile = path.join(COVER_CACHE, code + '.jpg');
  if (existsSync(cacheFile)) {
    const buf = await readFile(cacheFile);
    res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Cache-Control': 'public, max-age=86400' });
    return res.end(buf);
  }
  const m = db.prepare('SELECT cover_url FROM movies WHERE code=?').get(code);
  if (!m || !m.cover_url) {
    res.writeHead(404);
    return res.end();
  }
  try {
    const r = await fetch(m.cover_url);
    if (!r.ok) throw new Error('upstream ' + r.status);
    const buf = Buffer.from(await r.arrayBuffer());
    await writeFile(cacheFile, buf);
    res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Cache-Control': 'public, max-age=86400' });
    res.end(buf);
  } catch (e) {
    res.writeHead(502);
    res.end(e.message);
  }
}

const CONTENT_TYPE = {
  mp4: 'video/mp4', mkv: 'video/x-matroska', webm: 'video/webm', mov: 'video/quicktime',
  avi: 'video/x-msvideo', ts: 'video/mp2t', m2ts: 'video/mp2t', mts: 'video/mp2t',
  wmv: 'video/x-ms-wmv', flv: 'video/x-flv', mpg: 'video/mpeg', mpeg: 'video/mpeg',
  rmvb: 'application/vnd.rn-realmedia-vbr', rm: 'application/vnd.rn-realmedia',
  iso: 'application/octet-stream',
};

/** Pick the variant + part(s) to stream for (code, query).
 *  Returns { code, variant, parts, byVariant, allVariants } where `parts` is the
 *  chosen variant's videos ordered by part_index. `?variant=` selects explicitly;
 *  omitted → first variant by priority (censored > leak > untagged > others).
 *  `?part=` (legacy): single-part playback by part_label or 1-based part_index. */
function getVideosForStream(code, query) {
  const all = getVideosByMovie(db, code);
  if (!all.length) return null;
  const byVariant = new Map();
  for (const v of all) {
    if (!byVariant.has(v.variant)) byVariant.set(v.variant, []);
    byVariant.get(v.variant).push(v);
  }
  const allVariants = [...byVariant.keys()];
  let variant = (query.variant !== undefined) ? String(query.variant) : all[0].variant;
  let parts = byVariant.get(variant);
  if (!parts) { variant = all[0].variant; parts = byVariant.get(variant); } // fallback
  // ?part= legacy: select single part (1-based index or label)
  if (query.part !== undefined) {
    const q = String(query.part).toLowerCase();
    const idx = parseInt(q, 10);
    let part = (!isNaN(idx) && idx >= 1 && idx <= parts.length)
      ? parts[idx - 1]
      : parts.find((p) => (p.part_label || '').toLowerCase() === q);
    if (!part) part = parts[0];
    return { code, variant, parts: [part], byVariant, allVariants };
  }
  return { code, variant, parts, byVariant, allVariants };
}

/** Same as webdavUrl but accepts either a plain path or a webdav_path string
 *  (the videos.webdav_path column). They are identical today; kept separate
 *  so callers don't have to know which is which. */
const webdavUrlFor = (webdavPath) => webdavUrl(config, webdavPath);

const webdavHeaders = () => {
  if (!config.webdav.username) return {};
  return {
    Authorization: 'Basic ' + Buffer.from(
      `${config.webdav.username}:${config.webdav.password || ''}`
    ).toString('base64'),
  };
};

/** Transparent WebDAV Range proxy with multi-part concatenation.
 *
 *  Single-part: forward Range header verbatim (browser demuxer handles seeking).
 *  Multi-part: stream all parts of chosen variant in part_index order.
 *    - No Range → 200 OK, Content-Length = sum of part sizes.
 *    - Range inside one part → fetch that part with translated Range, return 206
 *      with Content-Range adjusted to global offset.
 *    - Range crossing parts → 416 Range Not Satisfiable (TODO: stitch via multi-fetch).
 */
function stream(req, res, code, query) {
  const r = getVideosForStream(code, query);
  if (!r || !r.parts.length) {
    res.writeHead(404);
    return res.end('not found');
  }
  const parts = r.parts;
  if (parts.length === 1) return streamOne(req, res, parts[0]);
  return streamMany(req, res, parts);
}

function streamOne(req, res, v) {
  const ctype = CONTENT_TYPE[v.container] || 'application/octet-stream';
  const u = new URL(webdavUrlFor(v.webdav_path));
  const headers = { ...webdavHeaders() };
  if (req.headers.range) headers['Range'] = req.headers.range;

  let aborted = false;
  const upstream = httpRequest({
    hostname: u.hostname, port: u.port || 80, path: u.pathname + u.search,
    method: 'GET', headers, agent: streamAgent, family: 4,
  });

  req.on('close', () => {
    aborted = true;
    try { upstream.destroy(); } catch {}
  });

  upstream.on('error', (e) => {
    if (aborted) return;
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'text/plain' });
    try { res.end('webdav error: ' + e.message); } catch {}
  });

  upstream.on('response', (ures) => {
    if (aborted) { ures.resume(); return; }
    const out = { 'Content-Type': ctype, 'Accept-Ranges': 'bytes' };
    if (ures.headers['content-length'] !== undefined) out['Content-Length'] = ures.headers['content-length'];
    if (ures.headers['content-range']) out['Content-Range'] = ures.headers['content-range'];
    res.writeHead(ures.statusCode, out);
    // HEAD (or upstream with no body): end response, drain upstream. unpipe
    // first so the pipe doesn't try to write after res.end() (which crashes
    // the process with ERR_STREAM_WRITE_AFTER_END).
    if (req.method === 'HEAD' || ures.headers['content-length'] === '0') {
      ures.unpipe(res);
      ures.resume();
      res.end();
      return;
    }
    ures.pipe(res);
  });

  upstream.end();
}

/** Cumulative byte offsets: offsets[i] = start byte of part i in concatenated stream. */
function buildOffsets(parts) {
  const offsets = new Array(parts.length + 1);
  offsets[0] = 0;
  for (let i = 0; i < parts.length; i++) offsets[i + 1] = offsets[i] + parts[i].size_bytes;
  return offsets;
}

/** Parse `bytes=A-B` / `bytes=A-` / `bytes=-N` → {start, end} absolute or null. */
function parseRange(header, total) {
  const m = /^bytes=(\d*)-(\d*)$/.exec(header || '');
  if (!m) return null;
  const [, a, b] = m;
  let start, end;
  if (a === '' && b !== '') { // suffix: last N bytes
    const n = parseInt(b, 10);
    if (!n) return null;
    start = Math.max(0, total - n);
    end = total - 1;
  } else {
    start = a === '' ? 0 : parseInt(a, 10);
    end = b === '' ? total - 1 : parseInt(b, 10);
  }
  if (isNaN(start) || isNaN(end) || start > end || start >= total) return null;
  end = Math.min(end, total - 1);
  return { start, end };
}

/** Multi-part concatenated stream. */
function streamMany(req, res, parts) {
  const ctype = CONTENT_TYPE[parts[0].container] || 'application/octet-stream';
  const offsets = buildOffsets(parts);
  const total = offsets[offsets.length - 1];
  const rangeHeader = req.headers.range;
  const range = rangeHeader ? parseRange(rangeHeader, total) : null;

  // Treat `bytes=0-` (open-ended from start) as "give me everything" — pipe
  // the full concat, don't 416. Browsers send this to probe a video before
  // issuing finer-grained range requests.
  const isWholeFile = range && range.start === 0 && range.end >= total - 1;
  // Find owning part for range.start (highest i where offsets[i] <= start).
  // For any start byte, owning part = the latest part whose cumulative
  // offset doesn't exceed start.
  const owningPart = range && !isWholeFile ? (() => {
    let i = parts.length - 1;
    while (i > 0 && range.start < offsets[i]) i--;
    return i;
  })() : -1;
  const insideOnePart = range && !isWholeFile && owningPart >= 0
    && range.end < offsets[owningPart + 1];
  if (insideOnePart) {
    // Range inside one part → translate and fetch as single-part 206
    const localStart = range.start - offsets[owningPart];
    const localEnd = range.end - offsets[owningPart];
    const v = parts[owningPart];
    const u = new URL(webdavUrlFor(v.webdav_path));
    const headers = { ...webdavHeaders(), Range: `bytes=${localStart}-${localEnd}` };
    let aborted = false;
    const upstream = httpRequest({
      hostname: u.hostname, port: u.port || 80, path: u.pathname + u.search,
      method: 'GET', headers, agent: streamAgent, family: 4,
    });
    req.on('close', () => { aborted = true; try { upstream.destroy(); } catch {} });
    upstream.on('error', () => { if (!aborted && !res.headersSent) res.writeHead(502); try { res.end(); } catch {} });
    upstream.on('response', (ures) => {
      if (aborted) { ures.resume(); return; }
      const out = {
        'Content-Type': ctype,
        'Content-Length': String(localEnd - localStart + 1),
        'Content-Range': `bytes ${range.start}-${range.end}/${total}`,
        'Accept-Ranges': 'bytes',
      };
      res.writeHead(206, out);
      if (req.method === 'HEAD') { ures.unpipe(res); ures.resume(); res.end(); return; }
      ures.pipe(res);
    });
    upstream.end();
    return;
  }

  // Range crossing parts: 416 (TODO: stitch via multi-fetch in a follow-up)
  if (range) {
    res.writeHead(416, {
      'Content-Type': 'text/plain',
      'Content-Range': `bytes */${total}`,
    });
    return res.end('cross-part Range not yet supported; request the full stream');
  }

  // No Range (or "give me everything" `bytes=0-`): 200, pipe parts in sequence.
  // Browsers send `bytes=0-` to probe a video; we MUST serve the full concat
  // stream, not 416.
  let aborted = false;
  req.on('close', () => { aborted = true; });
  res.writeHead(200, {
    'Content-Type': ctype,
    'Content-Length': total,
    'Accept-Ranges': 'bytes',
  });
  // HEAD: just advertise headers + Content-Length, don't actually stream.
  if (req.method === 'HEAD') { res.end(); return; }
  let i = 0;
  const next = () => {
    if (aborted) return;
    if (i >= parts.length) { res.end(); return; }
    const v = parts[i++];
    const u = new URL(webdavUrlFor(v.webdav_path));
    const upstream = httpRequest({
      hostname: u.hostname, port: u.port || 80, path: u.pathname + u.search,
      method: 'GET', headers: webdavHeaders(), agent: streamAgent, family: 4,
    });
    upstream.on('error', (e) => {
      if (aborted) return;
      console.error('[streamMany] upstream error part', i, ':', e.message);
      try { res.destroy(e); } catch {}
    });
    upstream.on('response', (ures) => {
      if (aborted) { ures.resume(); return; }
      if (ures.statusCode !== 200 && ures.statusCode !== 206) {
        console.error('[streamMany] upstream status', ures.statusCode, 'part', i);
        try { res.destroy(); } catch {}
        return;
      }
      ures.pipe(res, { end: false });
      ures.on('end', next);
      ures.on('error', (e) => {
        if (aborted) return;
        try { res.destroy(e); } catch {}
      });
    });
    upstream.end();
  };
  next();
}

/** Decide how to play a code. Single-part mp4 → 'direct'. Multi-part → 'multipart'
 *  (frontend plays parts sequentially via ?part=N). Non-mp4 → 'unsupported'. */
function getPlayMode(code, query) {
  const r = getVideosForStream(code, query);
  if (!r || !r.parts.length) return { mode: 'notfound' };
  // probe data lives per-video; report the first part's codec
  const head = r.parts[0];
  const mode = r.parts.length > 1
    ? 'multipart'
    : (head.container === 'mp4' ? 'direct' : 'unsupported');
  const result = {
    mode,
    v_codec: head.v_codec,
    a_codec: head.a_codec,
    container: head.container,
    variant: r.variant,
    variants: r.allVariants,
    part: head.part_label ?? null,
    partCount: r.parts.length,
  };
  if (mode === 'multipart') {
    // Frontend uses these to switch <video> src on 'ended'.
    // ?part=N selects the Nth part (1-based) via the legacy single-part path.
    result.parts = r.parts.map((v, i) => ({
      index: i + 1,
      label: v.part_label || String(i + 1),
      streamUrl: `/api/stream/${encodeURIComponent(code)}?variant=${encodeURIComponent(r.variant)}&part=${i + 1}`,
    }));
  }
  return result;
}

/** Generate an .m3u playlist. Lists all parts of the chosen variant in
 *  part_index order so VLC / mpv / IINA plays them sequentially. */
function playlist(req, res, code, query) {
  const r = getVideosForStream(code, query);
  if (!r || !r.parts.length) {
    res.writeHead(404);
    return res.end();
  }
  const m = getMovieRow(db, code) || {};
  const host = req.headers.host || `localhost:${PORT}`;
  const title = m.title_cn || m.title || code;
  const lines = ['#EXTM3U'];
  for (const p of r.parts) {
    const label = p.part_label || `part${p.part_index}`;
    lines.push(`#EXTINF:-1,${title} - ${label}`);
    const qs = new URLSearchParams({ variant: r.variant, part: String(p.part_index) });
    lines.push(`http://${host}/api/stream/${encodeURIComponent(code)}?${qs}`);
  }
  res.writeHead(200, {
    'Content-Type': 'audio/x-mpegurl; charset=utf-8',
    'Content-Disposition': `attachment; filename="${code}.m3u"`,
  });
  res.end(lines.join('\n') + '\n');
}

async function serveStatic(res, pathname) {
  let rel = pathname === '/' ? '/index.html' : pathname;
  const file = path.join(WEB_DIR, rel);
  if (!file.startsWith(WEB_DIR)) {
    res.writeHead(403);
    return res.end();
  }
  try {
    const buf = await readFile(file);
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(buf);
  } catch {
    res.writeHead(404);
    res.end('not found');
  }
}

// ---------- server ----------

/** PATCH /api/videos/:id — body: { variant?: string, part_label?: string|null }. */
async function handlePatchVideo(req, res, id) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  let body;
  try { body = JSON.parse(Buffer.concat(chunks).toString() || '{}'); }
  catch { return json(res, { error: 'bad json' }, 400); }
  const v = getVideo(db, id);
  if (!v) return json(res, { error: 'not found' }, 404);
  if ('variant' in body) updateVideoVariant(db, id, String(body.variant));
  if ('part_label' in body) updateVideoPartLabel(db, id, body.part_label);
  return json(res, getVideo(db, id));
}

/** POST /api/internal/probe/:videoId — run ffprobe on a single video (lazy probe on play). */
async function handleProbeOne(req, res, id) {
  const v = getVideo(db, id);
  if (!v) return json(res, { error: 'not found' }, 404);
  const m = await probeMedia(webdavUrl(config, v.webdav_path), 15000);
  if (m && (m.v_codec || m.width)) {
    applyProbeToVideo(db, id, m);
    return json(res, { ok: true, video: getVideo(db, id) });
  }
  markProbeFailed(db, id, 'ffprobe returned null');
  return json(res, { ok: false, error: 'ffprobe returned null' }, 502);
}

// ---- scan runner: spawn src/scan.js as an isolated child process ----
// Isolation: a scan crash / Recombee hiccup must not take down the server.
// scan.js is the existing incremental CLI (new codes -> Recombee scrape,
// existing -> touchExisting). We capture its stdout progress for the UI.
const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url))); // avlib root (src/..)
const scanState = {
  running: false,
  startedAt: null,
  finishedAt: null,
  exitCode: null,
  pid: null,
  log: [], // ring buffer of stdout/stderr lines
  summary: null, // { scraped, unmatched, error, skipped, movieParts } parsed from tail
};
const SCAN_LOG_MAX = 200;

function scanPushLog(line) {
  scanState.log.push(line);
  if (scanState.log.length > SCAN_LOG_MAX) scanState.log.shift();
}

function scanStatusJson() {
  return {
    running: scanState.running,
    startedAt: scanState.startedAt,
    finishedAt: scanState.finishedAt,
    exitCode: scanState.exitCode,
    pid: scanState.pid,
    log: scanState.log.slice(-30),
    summary: scanState.summary,
  };
}

function startScan() {
  if (scanState.running) return false;
  scanState.running = true;
  scanState.startedAt = Date.now();
  scanState.finishedAt = null;
  scanState.exitCode = null;
  scanState.pid = null;
  scanState.log = [];
  scanState.summary = null;
  scanPushLog(`[scan] spawn: ${process.execPath} src/scan.js (cwd ${ROOT})`);
  const child = spawn(
    process.execPath,
    ['--disable-warning=ExperimentalWarning', 'src/scan.js'],
    { cwd: ROOT, env: { ...process.env } }
  );
  scanState.pid = child.pid;
  let buf = '';
  const onChunk = (data) => {
    buf += data.toString();
    const lines = buf.split('\n');
    buf = lines.pop(); // keep partial last line
    for (const l of lines) scanPushLog(l.replace(/\r$/, ''));
  };
  child.stdout.on('data', onChunk);
  child.stderr.on('data', onChunk);
  child.on('exit', (code, signal) => {
    if (buf) scanPushLog(buf.replace(/\r$/, ''));
    scanState.running = false;
    scanState.finishedAt = Date.now();
    scanState.exitCode = signal ? -1 : code;
    const tail = scanState.log.slice(-12).join('\n');
    const m = tail.match(
      /done\.\s+scraped=(\d+)\s+unmatched=(\d+)\s+error=(\d+)\s+skipped\(existing\)=(\d+)\s+conflicts=(\d+)/
    );
    const vt = tail.match(/videos total:\s*(\d+)/);
    if (m) {
      scanState.summary = {
        scraped: +m[1],
        unmatched: +m[2],
        error: +m[3],
        skipped: +m[4],
        conflicts: +m[5],
        videosTotal: vt ? +vt[1] : null,
      };
    }
    scanPushLog(`[scan] exit code=${scanState.exitCode}`);
  });
  child.on('error', (e) => {
    scanPushLog(`[scan] spawn error: ${e.message}`);
    scanState.running = false;
    scanState.finishedAt = Date.now();
    scanState.exitCode = -1;
  });
  return true;
}

const server = createServer(async (req, res) => {
  const { pathname, query } = parseUrl(req.url);
  try {
    // auth routes (always accessible)
    if (pathname === '/login') return serveStatic(res, '/login.html');
    if (pathname === '/api/login') return await handleLogin(req, res);
    if (pathname === '/api/logout') return handleLogout(res);
    // auth gate
    if (AUTH_PASSWORD && !authOk(req)) {
      if (pathname.startsWith('/api/')) return json(res, { error: 'unauthorized' }, 401);
      res.writeHead(302, { Location: '/login' });
      return res.end();
    }
    if (pathname === '/api/scan' && req.method === 'POST') {
      const ok = startScan();
      return json(res, scanStatusJson(), ok ? 202 : 409);
    }
    if (pathname === '/api/scan/status') return json(res, scanStatusJson());
    if (pathname === '/api/movies') return json(res, listMovies(query));
    if (pathname === '/api/search')
      return json(res, { items: searchMovies(query.q || '', parseInt(query.limit) || 20) });
    if (pathname === '/api/facets') return json(res, facets());
    if (pathname === '/api/review-queue') return json(res, getReviewQueue(db));
    if (pathname === '/api/videos') return json(res, listVideos(db, {
      movieCode: query.movie_code || undefined,
      variant: query.variant, // may be '' (untagged) — listVideos treats undefined differently
      presence: query.presence || undefined,
    }));
    if (pathname.startsWith('/api/videos/')) {
      const idStr = pathname.slice('/api/videos/'.length);
      const id = parseInt(idStr, 10);
      if (!id) return json(res, { error: 'bad id' }, 400);
      if (req.method === 'PATCH') return await handlePatchVideo(req, res, id);
      const v = getVideo(db, id);
      if (v) return json(res, v);
      return json(res, { error: 'not found' }, 404);
    }
    if (pathname.startsWith('/api/internal/probe/')) {
      const idStr = pathname.slice('/api/internal/probe/'.length);
      const id = parseInt(idStr, 10);
      if (!id || req.method !== 'POST') return json(res, { error: 'bad request' }, 400);
      return await handleProbeOne(req, res, id);
    }
    if (pathname.startsWith('/api/movies/')) {
      const code = decodeURIComponent(pathname.slice('/api/movies/'.length));
      const m = getMovie(code);
      if (m) return json(res, m);
      return json(res, { error: 'not found' }, 404);
    }
    if (pathname.startsWith('/api/cover/'))
      return await cover(res, decodeURIComponent(pathname.slice('/api/cover/'.length)));
    if (pathname.startsWith('/api/stream/'))
      return stream(req, res, decodeURIComponent(pathname.slice('/api/stream/'.length)), query);
    if (pathname.startsWith('/api/play/')) {
      const code = decodeURIComponent(pathname.slice('/api/play/'.length));
      return json(res, getPlayMode(code, query));
    }
    if (pathname.startsWith('/api/playlist/')) {
      const code = decodeURIComponent(pathname.slice('/api/playlist/'.length).replace(/\.m3u$/i, ''));
      return playlist(req, res, code, query);
    }
    return await serveStatic(res, pathname);
  } catch (e) {
    console.error(e);
    res.writeHead(500);
    res.end(String(e.message));
  }
});

server.listen(PORT, HOST, () => {
  console.log(`avlib running at http://${HOST}:${PORT}`);
  const movies = db.prepare("SELECT COUNT(*) n FROM movies WHERE scrape_status='scraped'").get().n;
  const videos = db.prepare('SELECT COUNT(*) n FROM videos').get().n;
  console.log(`library: ${movies} scraped movies, ${videos} videos`);
});
