// SQLite storage via node:sqlite.
//
// Schema (since 2026-07-22 refactor):
//   movies  — 1 row per movie code, scrape metadata + provenance
//   videos  — 1 row per FILE, file metadata + probe metadata + variant/part
//
// Multi-part playback: SELECT videos WHERE movie_code=? AND variant=? ORDER BY part_index
// streams N files sequentially via the API layer (no `video_parts` table).

import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const SCHEMA = `
CREATE TABLE IF NOT EXISTS movies (
  code              TEXT PRIMARY KEY,

  title             TEXT,  title_zh TEXT,  title_cn TEXT,  title_en TEXT,
  actresses         TEXT,  actors    TEXT,  directors  TEXT,
  labels            TEXT,  markers   TEXT,  genres     TEXT,
  series            TEXT,  tags      TEXT,
  released_at       INTEGER,  released_date TEXT,  duration_sec INTEGER,
  has_chinese_subtitle   INTEGER,
  has_english_subtitle   INTEGER,
  is_uncensored_leak     INTEGER,
  type              TEXT,
  cover_url         TEXT,
  raw_json          TEXT,

  scrape_status     TEXT NOT NULL DEFAULT 'pending',
  scrape_error      TEXT,
  scrape_fetched_at INTEGER,
  scrape_added_at   INTEGER,
  scrape_ms         INTEGER,  scrape_http INTEGER,
  scrape_etag       TEXT,     scrape_url  TEXT,
  scrape_version    TEXT,

  video_count       INTEGER NOT NULL DEFAULT 0,

  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_movies_scrape_status ON movies(scrape_status);
CREATE INDEX IF NOT EXISTS idx_movies_added_at      ON movies(scrape_added_at);
CREATE INDEX IF NOT EXISTS idx_movies_released_at   ON movies(released_at);

CREATE TABLE IF NOT EXISTS videos (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  webdav_path       TEXT NOT NULL UNIQUE,
  movie_code        TEXT REFERENCES movies(code) ON DELETE SET NULL,

  variant           TEXT NOT NULL DEFAULT '',
  part_index        INTEGER NOT NULL,
  part_label        TEXT,
  conflict_reason   TEXT,

  filename          TEXT NOT NULL,
  container         TEXT,
  size_bytes        INTEGER NOT NULL,
  mtime_ms          INTEGER,

  probe_status      TEXT NOT NULL DEFAULT 'pending',
  probed_at         INTEGER,
  probe_ms          INTEGER,
  v_codec           TEXT, a_codec           TEXT,
  width             INTEGER, height         INTEGER,
  fps               REAL, duration_real    INTEGER,
  video_bitrate     INTEGER, video_profile  TEXT,
  audio_tracks      TEXT, subtitle_tracks  TEXT,

  presence          TEXT NOT NULL DEFAULT 'present',

  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL,

  UNIQUE(movie_code, variant, part_index)
);
CREATE INDEX IF NOT EXISTS idx_videos_movie_code   ON videos(movie_code);
CREATE INDEX IF NOT EXISTS idx_videos_probe_status ON videos(probe_status);
CREATE INDEX IF NOT EXISTS idx_videos_presence     ON videos(presence);
`;

export function openDb(dbPath) {
  mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode=WAL;');
  db.exec(SCHEMA);
  return db;
}

const J = (v) => JSON.stringify(v || []);

// ─── movies ────────────────────────────────────────────────────────────

/** Insert/replace a successfully scraped movie. If the row already exists,
 *  scrape metadata is overwritten; video_count is recomputed. */
export function upsertScraped(db, file, movie, now) {
  db.prepare(`
    INSERT INTO movies (
      code, title, title_zh, title_cn, title_en,
      actresses, actors, directors, labels, markers, genres, series, tags,
      released_at, released_date, duration_sec,
      has_chinese_subtitle, has_english_subtitle, is_uncensored_leak,
      type, cover_url, raw_json,
      scrape_status, scrape_error, scrape_fetched_at, scrape_added_at,
      scrape_ms, scrape_http, scrape_etag, scrape_url, scrape_version,
      video_count, created_at, updated_at
    ) VALUES (
      @code, @title, @title_zh, @title_cn, @title_en,
      @actresses, @actors, @directors, @labels, @markers, @genres, @series, @tags,
      @released_at, @released_date, @duration_sec,
      @has_chinese_subtitle, @has_english_subtitle, @is_uncensored_leak,
      @type, @cover_url, @raw_json,
      'scraped', NULL, @now, @now,
      NULL, NULL, NULL, NULL, NULL,
      0, @now, @now
    )
    ON CONFLICT(code) DO UPDATE SET
      title = excluded.title,
      title_zh = excluded.title_zh,
      title_cn = excluded.title_cn,
      title_en = excluded.title_en,
      actresses = excluded.actresses,
      actors = excluded.actors,
      directors = excluded.directors,
      labels = excluded.labels,
      markers = excluded.markers,
      genres = excluded.genres,
      series = excluded.series,
      tags = excluded.tags,
      released_at = excluded.released_at,
      released_date = excluded.released_date,
      duration_sec = excluded.duration_sec,
      has_chinese_subtitle = excluded.has_chinese_subtitle,
      has_english_subtitle = excluded.has_english_subtitle,
      is_uncensored_leak = excluded.is_uncensored_leak,
      type = excluded.type,
      cover_url = excluded.cover_url,
      raw_json = excluded.raw_json,
      scrape_status = 'scraped',
      scrape_error = NULL,
      scrape_fetched_at = excluded.scrape_fetched_at,
      scrape_added_at = COALESCE(movies.scrape_added_at, excluded.scrape_added_at),
      updated_at = excluded.updated_at
  `).run({
    code: file.code,
    title: movie.title ?? null,
    title_zh: movie.title_zh ?? null,
    title_cn: movie.title_cn ?? null,
    title_en: movie.title_en ?? null,
    actresses: J(movie.actresses),
    actors: J(movie.actors),
    directors: J(movie.directors),
    labels: J(movie.labels),
    markers: J(movie.markers),
    genres: J(movie.genres),
    series: J(movie.series),
    tags: J(movie.tags),
    released_at: movie.released_at ?? null,
    released_date: movie.released_date ?? null,
    duration_sec: movie.duration_sec ?? null,
    has_chinese_subtitle: 0,            // 2026-07-22: 字段废弃, 永远写 0, 不读不显示
    has_english_subtitle: 0,            // 同上
    is_uncensored_leak: movie.is_uncensored_leak ? 1 : 0,
    type: movie.type ?? null,
    cover_url: movie.cover_url ?? null,
    raw_json: JSON.stringify(movie.raw ?? null),
    now,
  });
}

/** Insert a row for a file whose code is known but scrape had no match / errored.
 *  Preserves any prior title if one was scraped. */
export function upsertUnmatched(db, file, status, errorMsg, now) {
  const existing = db.prepare('SELECT title FROM movies WHERE code = ?').get(file.code);
  db.prepare(`
    INSERT INTO movies (
      code, scrape_status, scrape_error, scrape_added_at,
      scrape_fetched_at, created_at, updated_at
    ) VALUES (
      @code, @status, @error, @added_at,
      NULL, @now, @now
    )
    ON CONFLICT(code) DO UPDATE SET
      scrape_status = excluded.scrape_status,
      scrape_error  = excluded.scrape_error,
      scrape_added_at = CASE WHEN movies.scrape_added_at IS NULL THEN excluded.scrape_added_at ELSE movies.scrape_added_at END,
      updated_at = excluded.updated_at
  `).run({
    code: file.code,
    status,
    error: errorMsg ?? null,
    added_at: existing ? null : now,
    now,
  });
}

/** Read a movie row by code (or null). */
export function getMovie(db, code) {
  return db.prepare('SELECT * FROM movies WHERE code = ?').get(code) ?? null;
}

// ─── videos ────────────────────────────────────────────────────────────

/** Insert or update a single file. UNIQUE(webdav_path) handles re-scans of
 *  the same file (path/size/mtime refreshed; variant + probe data preserved).
 *  UNIQUE(movie_code, variant, part_index) conflict means two different files
 *  claim the same playback slot — caller must catch and skip (see scan.js). */
export function upsertVideo(db, v) {
  const now = Date.now();
  db.prepare(`
    INSERT INTO videos (
      webdav_path, movie_code, variant, part_index, part_label,
      filename, container, size_bytes, mtime_ms,
      conflict_reason,
      created_at, updated_at
    ) VALUES (
      @webdav_path, @movie_code, @variant, @part_index, @part_label,
      @filename, @container, @size_bytes, @mtime_ms,
      NULL,
      @now, @now
    )
    ON CONFLICT(webdav_path) DO UPDATE SET
      movie_code = excluded.movie_code,
      part_index = excluded.part_index,
      part_label = excluded.part_label,
      filename   = excluded.filename,
      container  = excluded.container,
      size_bytes = excluded.size_bytes,
      mtime_ms   = excluded.mtime_ms,
      updated_at = excluded.updated_at
      -- variant, probe_*, presence, conflict_reason, created_at NOT touched
  `).run({
    webdav_path: v.webdav_path,
    movie_code: v.movie_code ?? null,
    variant: v.variant ?? '',
    part_index: v.part_index ?? 1,
    part_label: v.part_label ?? null,
    filename: v.filename,
    container: v.container ?? null,
    size_bytes: v.size_bytes,
    mtime_ms: v.mtime_ms ?? null,
    now,
  });
  recomputeVideoCount(db, v.movie_code);
}

/** UI: change a video's variant label. Empty string = untagged. */
export function updateVideoVariant(db, videoId, variant) {
  db.prepare('UPDATE videos SET variant = ?, updated_at = ? WHERE id = ?').run(
    variant ?? '',
    Date.now(),
    videoId
  );
}

/** UI: change part_label (cosmetic only; doesn't reorder playback). */
export function updateVideoPartLabel(db, videoId, partLabel) {
  db.prepare('UPDATE videos SET part_label = ?, updated_at = ? WHERE id = ?').run(
    partLabel || null,
    Date.now(),
    videoId
  );
}

/** Probe: write ffprobe metadata onto the video row. */
export function applyProbeToVideo(db, videoId, m) {
  if (!m) return false;
  const r = db.prepare(`
    UPDATE videos SET
      probe_status = 'probed',
      probed_at = ?,
      probe_ms  = ?,
      v_codec = ?, a_codec = ?,
      width = ?, height = ?, fps = ?, duration_real = ?,
      video_bitrate = ?, video_profile = ?,
      audio_tracks = ?, subtitle_tracks = ?,
      updated_at = ?
    WHERE id = ?
  `).run(
    Date.now(), m.probe_ms ?? null,
    m.v_codec, m.a_codec,
    m.width, m.height, m.fps, m.duration_real,
    m.video_bitrate, m.video_profile,
    m.audio_tracks, m.subtitle_tracks,
    Date.now(),
    videoId
  );
  return r.changes > 0;
}

/** Probe: mark a video as failed. */
export function markProbeFailed(db, videoId, errMsg) {
  db.prepare(`
    UPDATE videos SET probe_status = 'failed', updated_at = ?
    WHERE id = ?
  `).run(Date.now(), videoId);
}

/** Read all videos for a movie code, ordered by variant priority then part_index. */
export function getVideosByMovie(db, code) {
  return db.prepare(`
    SELECT id, webdav_path, movie_code, variant, part_index, part_label,
           filename, container, size_bytes, mtime_ms,
           probe_status, probed_at, probe_ms,
           v_codec, a_codec, width, height, fps, duration_real,
           video_bitrate, video_profile, audio_tracks, subtitle_tracks,
           presence, conflict_reason,
           created_at, updated_at
    FROM videos
    WHERE movie_code = ?
    ORDER BY
      CASE variant WHEN 'censored' THEN 0 WHEN 'leak' THEN 1 WHEN '' THEN 2 ELSE 3 END,
      part_index ASC
  `).all(code);
}

/** Read a single video by id. */
export function getVideo(db, videoId) {
  return db.prepare('SELECT * FROM videos WHERE id = ?').get(videoId) ?? null;
}

/** List videos with optional filters. */
export function listVideos(db, { movieCode, variant, presence } = {}) {
  const where = [];
  const params = [];
  if (movieCode) { where.push('movie_code = ?'); params.push(movieCode); }
  if (variant !== undefined) { where.push('variant = ?'); params.push(variant); }
  if (presence) { where.push('presence = ?'); params.push(presence); }
  const sql = `SELECT * FROM videos ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY id LIMIT 200`;
  return db.prepare(sql).all(...params);
}

/** Movies that need user review: only those whose multi-video state can't be
 *  fully resolved by filename parsing. Clean multi-parts (e.g. CD1+CD2, A+B)
 *  whose every file has a distinct, parseable part_label are NOT queued —
 *  those are handled by scanner.parsePart() and don't need user input.
 *
 *  Queue triggers (any of):
 *    ① multi-video but ≥1 file has no parseable part_label
 *    ② multi-video but ≥2 files share the same part_label (collision)
 *    ③ any video has an explicit conflict_reason flag (future-proof)
 *
 *  Returns array of { code, title, title_cn, video_count, videos: [...] }. */
export function getReviewQueue(db) {
  return db.prepare(`
    SELECT m.code, m.title, m.title_cn, m.title_zh,
           m.video_count,
           m.scrape_status,
           (SELECT COUNT(DISTINCT variant) FROM videos WHERE movie_code = m.code) AS variant_count,
           (SELECT COUNT(*) FROM videos WHERE movie_code = m.code AND variant = '') AS untagged_count,
           (SELECT COUNT(*) FROM videos WHERE movie_code = m.code AND conflict_reason IS NOT NULL) AS conflict_count
    FROM movies m
    WHERE
      (m.video_count > 1 AND (
        EXISTS (SELECT 1 FROM videos v
                WHERE v.movie_code = m.code
                  AND (v.part_label IS NULL OR v.part_label = ''))
        OR EXISTS (
          SELECT 1 FROM videos v
          WHERE v.movie_code = m.code
            AND v.part_label IS NOT NULL AND v.part_label != ''
          GROUP BY v.part_label
          HAVING COUNT(*) > 1
        )
      ))
      OR EXISTS (SELECT 1 FROM videos v
                 WHERE v.movie_code = m.code AND v.conflict_reason IS NOT NULL)
    ORDER BY m.scrape_added_at DESC NULLS LAST
  `).all().map((row) => ({
    ...row,
    videos: db.prepare(`
      SELECT id, webdav_path, filename, variant, part_index, part_label,
             size_bytes, container, conflict_reason
      FROM videos WHERE movie_code = ?
      ORDER BY
        CASE variant WHEN 'censored' THEN 0 WHEN 'leak' THEN 1 WHEN '' THEN 2 ELSE 3 END,
        part_index ASC
    `).all(row.code),
  }));
}

/** Recompute movies.video_count for one movie. Called by upsertVideo. */
export function recomputeVideoCount(db, code) {
  if (!code) return;
  const n = db.prepare('SELECT COUNT(*) n FROM videos WHERE movie_code = ?').get(code).n;
  db.prepare('UPDATE movies SET video_count = ?, updated_at = ? WHERE code = ?')
    .run(n, Date.now(), code);
}

/** Probe queue: videos with probe_status='pending' and presence='present'. */
export function getPendingProbes(db, limit = 0) {
  const sql = `
    SELECT id, webdav_path, filename, container, size_bytes
    FROM videos
    WHERE probe_status = 'pending' AND presence = 'present'
    ORDER BY created_at ASC
    ${limit ? 'LIMIT ' + Number(limit) : ''}
  `;
  return db.prepare(sql).all();
}