// Scan orchestrator: walk WebDAV → group by code → for each new code scrape
// Recombee → store. Videos are 1 row per FILE; multi-part playback is handled
// by the API layer ordering by part_index. Variant is user-driven (never set
// from filename); UI sets it via PATCH /api/videos/:id.
//
// Usage:
//   node src/scan.js                # full incremental scan
//   node src/scan.js --limit 10     # scrape at most 10 new codes (testing)
//   node src/scan.js --rescan       # force re-scrape even if already scraped
//   node src/scan.js --scan-only    # just walk WebDAV + print counts, no scrape
//   node src/scan.js --probe-only   # skip WebDAV + scrape, just run ffprobe batch
//   node src/scan.js --covers-only  # skip WebDAV + scrape, just backfill missing covers
//   node src/scan.js --variant-set <videoId>=<variant>  # debug: tag a video

import { createClient } from 'webdav';
import { loadConfig } from './config.js';
import { scanWebDAV, parsePartLabel, parsePartIndex } from './scanner.js';
import {
  openDb,
  upsertScraped,
  upsertUnmatched,
  upsertVideo,
  getMovie,
  getPendingProbes,
  applyProbeToVideo,
  markProbeFailed,
  updateVideoVariant,
  recomputeVideoCount,
} from './db.js';
import { probeMedia, webdavUrl } from './probe.js';
import { findByCode } from './scraper/missav.js';
import { writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const limitIdx = argv.indexOf('--limit');
const limit = limitIdx !== -1 ? parseInt(argv[limitIdx + 1], 10) || 0 : 0;
const flags = new Set(argv);
const rescan = flags.has('--rescan');
const scanOnly = flags.has('--scan-only');
const probeOnly = flags.has('--probe-only');
const coversOnly = flags.has('--covers-only');

const variantSetIdx = argv.indexOf('--variant-set');
const variantSet = variantSetIdx !== -1 ? argv[variantSetIdx + 1] : null; // "id=variant"

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const nowSec = () => Math.floor(Date.now() / 1000);

const config = loadConfig();
const client = createClient(config.webdav.baseUrl, {
  username: config.webdav.username,
  password: config.webdav.password,
});
const db = openDb(config.db.path);

// Cover cache: same path as server.js (data/covers/). Scraped covers are
// persisted here immediately so the UI is instant on first browse, instead of
// paying CDN latency on the first /api/cover/:code request.
const COVER_CACHE = path.join(path.dirname(config.db.path), 'covers');

/** Download a cover from its CDN URL into COVER_CACHE/{code}.jpg.
 *  Idempotent: skips if the file already exists. Throws on fetch/IO error. */
async function downloadCover(code, coverUrl) {
  const cacheFile = path.join(COVER_CACHE, code + '.jpg');
  if (existsSync(cacheFile)) return { skipped: true };
  const r = await fetch(coverUrl);
  if (!r.ok) throw new Error('upstream ' + r.status);
  const buf = Buffer.from(await r.arrayBuffer());
  await mkdir(COVER_CACHE, { recursive: true });
  await writeFile(cacheFile, buf);
  return { ok: true, size: buf.length };
}

// ─── debug: --variant-set id=variant ───
if (variantSet) {
  const [idStr, variant] = variantSet.split('=');
  const id = parseInt(idStr, 10);
  if (!id || variant === undefined) {
    console.error('--variant-set expects <videoId>=<variant>');
    process.exit(1);
  }
  updateVideoVariant(db, id, variant);
  console.log(`video id=${id} → variant='${variant}'`);
  db.close();
  process.exit(0);
}

// ─── probe-only mode: just run ffprobe on pending videos ───
if (probeOnly) {
  const toProbe = getPendingProbes(db, limit);
  console.log(`probe-only: ${toProbe.length} videos to probe (15s timeout each)${limit ? ' (limited)' : ''}`);
  let ok = 0, fail = 0;
  for (const v of toProbe) {
    const m = await probeMedia(webdavUrl(config, v.webdav_path));
    if (m && (m.v_codec || m.width)) {
      applyProbeToVideo(db, v.id, m);
      ok++;
    } else {
      markProbeFailed(db, v.id, 'ffprobe returned null');
      fail++;
      console.log(`  [probe fail] video id=${v.id} ${v.webdav_path}`);
    }
    if ((ok + fail) % 10 === 0) console.log(`  probe: ${ok + fail}/${toProbe.length} (ok=${ok} fail=${fail})`);
  }
  console.log(`\nprobe done. ok=${ok} fail=${fail}`);
  db.close();
  process.exit(0);
}

// ─── covers-only mode: backfill missing covers for already-scraped movies ───
if (coversOnly) {
  await mkdir(COVER_CACHE, { recursive: true });
  const rows = db.prepare(
    `SELECT code, cover_url FROM movies WHERE scrape_status='scraped' AND cover_url IS NOT NULL`
  ).all();
  console.log(`covers-only: ${rows.length} scraped movies (cache: ${COVER_CACHE})`);
  let ok = 0, skip = 0, fail = 0;
  for (const m of rows) {
    try {
      const r = await downloadCover(m.code, m.cover_url);
      if (r.skipped) { skip++; continue; }
      ok++;
      console.log(`  [cover] ${m.code} (${(r.size / 1024).toFixed(0)} KB)`);
    } catch (e) {
      fail++;
      console.log(`  [cover fail] ${m.code}: ${e.message}`);
    }
    await sleep(100); // light pacing for the CDN
    if ((ok + skip + fail) % 10 === 0 && ok + skip + fail > 0)
      console.log(`  progress: ok=${ok} skip=${skip} fail=${fail}`);
  }
  console.log(`\ncovers done. ok=${ok} skip=${skip} fail=${fail}`);
  db.close();
  process.exit(0);
}

const rateMs = config.scrape?.rateLimitMs ?? 300;

console.log(`scanning WebDAV ${config.webdav.baseUrl} (depth <= 1) ...`);
const groups = await scanWebDAV(client);
const multiCount = groups.filter((g) => g.isMulti).length;
const totalFiles = groups.reduce((n, g) => n + g.files.length, 0);
console.log(`found ${groups.length} codes (${multiCount} multi-part, ${totalFiles} files total)`);

if (scanOnly) {
  const sample = groups.filter((g) => g.isMulti).slice(0, 10);
  for (const g of sample) {
    console.log(`  ${g.code}  parts: ` + g.files.map((f) => `${f.part || '-'}/${f.filename}`).join(' | '));
  }
  // also: single-part codes with potentially multiple files (variant candidates)
  const multiUntagged = groups.filter((g) => g.isMulti && g.files.every((f) => !f.part));
  if (multiUntagged.length) {
    console.log(`\n  ⚠ ${multiUntagged.length} code(s) have multiple files with no part marker (variant candidates):`);
    for (const g of multiUntagged.slice(0, 20)) {
      console.log(`    ${g.code}  files: ` + g.files.map((f) => f.filename).join(' | '));
    }
  }
  process.exit(0);
}

let scraped = 0, unmatched = 0, errored = 0, skipped = 0, newCount = 0, conflicts = 0;

for (const g of groups) {
  const existing = getMovie(db, g.code);

  // skip scrape if already scraped (touchExisting-style; videos still upserted below)
  const needScrape = rescan || !existing || existing.scrape_status !== 'scraped';

  if (needScrape) {
    if (limit && newCount >= limit) {
      console.log(`--limit ${limit} reached, stopping.`);
      break;
    }
    newCount++;
    try {
      const movie = await findByCode(g.code);
      if (!movie) {
        upsertUnmatched(db, { code: g.code }, 'unmatched', null, nowSec());
        unmatched++;
        console.log(`  [unmatched] ${g.code}`);
      } else {
        upsertScraped(db, { code: g.code }, movie, nowSec());
        scraped++;
        // Persist cover immediately: scrape-time download avoids first-browse CDN latency.
        if (movie.cover_url) {
          try {
            const r = await downloadCover(g.code, movie.cover_url);
            if (r.ok) console.log(`  [cover] ${g.code} (${(r.size / 1024).toFixed(0)} KB)`);
          } catch (e) {
            console.log(`  [cover fail] ${g.code}: ${e.message}`);
          }
        }
        if (g.isMulti) console.log(`  [multi ${g.files.length}p] ${g.code}`);
      }
    } catch (e) {
      upsertUnmatched(db, { code: g.code }, 'error', String(e.message).slice(0, 500), nowSec());
      errored++;
      console.error(`  [error] ${g.code}: ${e.message}`);
    }
  } else {
    skipped++;
  }

  // upsert each file → 1 row in videos
  for (const f of g.files) {
    const partLabel = parsePartLabel(f.filename);
    const partIndex = parsePartIndex(f.filename);
    try {
      upsertVideo(db, {
        webdav_path: f.webdav_path,
        movie_code: g.code,
        variant: '', // user-driven; UI sets via PATCH
        part_index: partIndex,
        part_label: partLabel,
        filename: f.filename,
        container: f.container,
        size_bytes: f.size,
        mtime_ms: null, // WebDAV client doesn't expose mtime; left null
      });
    } catch (e) {
      if (!String(e.message).includes('UNIQUE constraint failed')) throw e;
      // Conflict: another file already holds the (movie_code, '', part_index) slot.
      // Persist a sentinel row so the Review Queue surfaces it — silent drops
      // leave the user with no signal that two real files share one playback slot.
      // variant='__conflict__' is a reserved value (filtered by getVideosForStream)
      // that frees the uniqueness triple so this row can coexist with the winner.
      conflicts++;
      const reason = `scanner conflict on (movie_code='${g.code}', variant='', part_index=${partIndex}); another file already holds this slot — resolve via Review Queue (delete, rename, or assign variant)`;
      console.log(`  [conflict] ${g.code} ${f.filename}: ${reason}`);
      try {
        db.prepare(`
          INSERT INTO videos (
            webdav_path, movie_code, variant, part_index, part_label,
            filename, container, size_bytes, mtime_ms, conflict_reason,
            created_at, updated_at
          ) VALUES (
            @webdav_path, @movie_code, '__conflict__', @part_index, NULL,
            @filename, @container, @size_bytes, @mtime_ms, @reason,
            @now, @now
          )
          ON CONFLICT(webdav_path) DO UPDATE SET
            conflict_reason = excluded.conflict_reason,
            updated_at      = excluded.updated_at
        `).run({
          webdav_path: f.webdav_path,
          movie_code: g.code,
          part_index: partIndex,
          filename: f.filename,
          container: f.container,
          size_bytes: f.size,
          mtime_ms: null,
          reason,
          now: Date.now(),
        });
      } catch (e2) {
        console.error(`  [conflict unrecoverable] ${g.code} ${f.filename}: ${e2.message}`);
      }
    }
  }

  if ((scraped + unmatched + errored) % 10 === 0 && scraped + unmatched + errored > 0) {
    console.log(`  progress: scraped=${scraped} unmatched=${unmatched} error=${errored} skipped=${skipped} conflicts=${conflicts}`);
  }
  if (needScrape) await sleep(rateMs);
}

console.log(`\ndone. scraped=${scraped} unmatched=${unmatched} error=${errored} skipped(existing)=${skipped} conflicts=${conflicts}`);
const movieCounts = db.prepare(`SELECT scrape_status, COUNT(*) n FROM movies GROUP BY scrape_status ORDER BY n DESC`).all();
console.log('movies:', movieCounts.map((r) => `${r.scrape_status}=${r.n}`).join('  '));
const videoCounts = db.prepare(`SELECT probe_status, COUNT(*) n FROM videos GROUP BY probe_status ORDER BY n DESC`).all();
console.log('videos:', videoCounts.map((r) => `${r.probe_status}=${r.n}`).join('  '));
console.log(`videos total: ${db.prepare('SELECT COUNT(*) n FROM videos').get().n}`);

// ─── probe phase: ffprobe videos with probe_status='pending' ───
const toProbe = getPendingProbes(db);
if (toProbe.length) {
  console.log(`\nprobing ${toProbe.length} videos for technical metadata (15s timeout each)...`);
  let ok = 0, fail = 0;
  for (const v of toProbe) {
    const m = await probeMedia(webdavUrl(config, v.webdav_path));
    if (m && (m.v_codec || m.width)) {
      applyProbeToVideo(db, v.id, m);
      ok++;
    } else {
      markProbeFailed(db, v.id, 'ffprobe returned null');
      fail++;
    }
    if ((ok + fail) % 10 === 0) console.log(`  probe: ${ok + fail}/${toProbe.length} (ok=${ok} fail=${fail})`);
  }
  console.log(`probe done. ok=${ok} fail=${fail}`);
} else {
  console.log('\nprobe: all videos already probed, skipping.');
}

db.close();