// WebDAV scanner: walks root + one level of subdirectories, extracts AV codes
// and multi-part labels from filenames, groups by code.
//
// Rules (see agreed spec):
//  1. Legal filename = starts with a code (hyphen optional). FC2-PPV-xxxx is a code.
//  2. After the code, the first token (sep - _ space) may be a part marker:
//     single letter A-D, number 1-99, 上/下/前/后/前篇/后篇/上集/下集/正片,
//     or CD1/DISC1/DISK1/DVD1/PART1/PT1. `-A` and `- A` are both part A.
//  3. Anything else after the code (1080p, uncensored-leak, HEVC, ...) is NOT a part.
//  4. Each unique webdav_path is kept (NOT deduped by part label) — so
//     `achj-040.mp4 + achj-040-leak.mp4` both surface for variant review.
//  5. Folder depth max 1.

const VIDEO_EXT = new Set([
  'mp4', 'mkv', 'avi', 'wmv', 'flv', 'mov', 'm4v', 'mpg', 'mpeg',
  'ts', 'm2ts', 'mts', 'vob', 'webm', 'rmvb', 'rm', 'iso', '3gp',
]);

const CN_PARTS = ['上', '下', '前', '后', '前篇', '后篇', '上集', '下集', '正片'];
const CN_FIRST = ['上', '前', '前篇', '上集', '正片']; // part_index 1
const CN_SECOND = ['下', '后', '后篇', '下集']; // part_index 2

/** Detect a part label from the suffix following the code. Returns label or null. */
function parsePart(suffix) {
  if (!suffix) return null;
  const s = suffix.replace(/^[-_\s]+/, ''); // strip leading separators
  if (!s) return null;
  const token = s.split(/[-_\s]/)[0]; // first token only
  if (!token) return null;
  if (/^[A-Da-d]$/.test(token)) return token.toUpperCase();
  if (/^\d{1,2}$/.test(token)) return token;
  if (CN_PARTS.includes(token)) return token;
  if (/^(cd|disc|disk|dvd|part|pt)\d{1,2}$/i.test(token)) return token;
  return null;
}

/** Normalized sort order for a part label (1-based). Unknown/missing => 1 (single-file default). */
export function sortOrder(part) {
  if (!part) return 1;
  if (/^[A-D]$/.test(part)) return part.charCodeAt(0) - 64; // A=1..D=4
  if (/^\d{1,2}$/.test(part)) return parseInt(part, 10);
  if (CN_FIRST.includes(part)) return 1;
  if (CN_SECOND.includes(part)) return 2;
  const m = part.match(/^(?:cd|disc|disk|dvd|part|pt)(\d{1,2})$/i);
  if (m) return parseInt(m[1], 10);
  return 1; // unknown label — keep insertion order, treat as single
}

/** Extract { code, part } from a filename, or null if it doesn't start with a code. */
export function extractCodeAndPart(filename) {
  const base = filename.replace(/\.[^.]+$/, ''); // strip extension
  // FC2 short form: FC2-506923 (community shorthand, no PPV).
  // Must come before the PPV rule since both start with FC2.
  let m = base.match(/^FC2[-_\s]?(\d{4,8})(.*)/i);
  if (m) return { code: 'fc2-' + m[1], part: parsePart(m[2]) };
  m = base.match(/^FC2[-_\s]?PPV[-_\s]?(\d{4,8})(.*)/i);
  if (m) return { code: 'fc2-ppv-' + m[1], part: parsePart(m[2]) };
  // General, prefer pure-letter prefix: avoids "juq-426" being misread as "juq4-26"
  // when mixed-prefix regex would greedily eat digits into the prefix.
  m = base.match(/^([A-Za-z]{2,8})[-_\s]?(\d{2,8})(.*)/);
  if (m) return { code: (m[1] + '-' + m[2]).toLowerCase(), part: parsePart(m[3]) };
  // Fallback: mixed letter+digit prefix for codes like T28-123, H4610-001, A2C-12.
  // Must still START with a letter (avoids pure-digit false matches).
  m = base.match(/^([A-Za-z][A-Za-z0-9]{1,7})[-_\s]?(\d{2,8})(.*)/);
  if (m) return { code: (m[1] + '-' + m[2]).toLowerCase(), part: parsePart(m[3]) };
  return null;
}

/** Parse part label from filename. Returns label string or null. */
export function parsePartLabel(filename) {
  return extractCodeAndPart(filename)?.part ?? null;
}

/** Parse part index from filename. Returns 1-based integer; defaults to 1 for files
 *  with no parseable part marker (single-file case). */
export function parsePartIndex(filename) {
  const cp = extractCodeAndPart(filename);
  return sortOrder(cp?.part ?? null);
}

/** Back-compat wrapper: just the code. */
export function extractCode(filename) {
  return extractCodeAndPart(filename)?.code ?? null;
}

export function isVideo(filename) {
  const parts = filename.split('.');
  if (parts.length < 2) return false;
  return VIDEO_EXT.has(parts.pop().toLowerCase());
}

function isLeak(filename) {
  return /uncensored[-_\s]?leak/i.test(filename);
}

/** When two files claim the same (code, part) slot (rare; legacy dedup case),
 *  prefer non-leak, then larger size. */
function pickBetter(a, b) {
  const aLeak = isLeak(a.filename);
  const bLeak = isLeak(b.filename);
  if (aLeak !== bLeak) return aLeak ? b : a;
  return (b.size || 0) > (a.size || 0) ? b : a;
}

function entryFrom(item, part) {
  return {
    part,
    sort_order: sortOrder(part),
    webdav_path: item.filename,
    filename: item.basename,
    size: item.size || 0,
    container: item.basename.includes('.') ? item.basename.split('.').pop().toLowerCase() : null,
  };
}

/**
 * Scan WebDAV (root + 1 level). Returns array of:
 *   { code, isMulti, files: [{part, sort_order, webdav_path, filename, size, container}] }
 * files is sorted by sort_order. Each unique webdav_path gets its own entry;
 * multi-variant files (e.g. `code.mp4 + code-leak.mp4` both untagged) both surface.
 */
export async function scanWebDAV(client) {
  const byCode = new Map(); // code -> Map(webdav_path, entry)

  function collect(item) {
    const cp = extractCodeAndPart(item.basename);
    if (!cp) return;
    const entry = entryFrom(item, cp.part);
    if (!byCode.has(cp.code)) byCode.set(cp.code, new Map());
    const existing = byCode.get(cp.code).get(item.filename);
    byCode.get(cp.code).set(item.filename, existing ? pickBetter(existing, entry) : entry);
  }

  const root = await client.getDirectoryContents('/');
  for (const item of root) {
    if (item.type === 'file' && isVideo(item.basename)) collect(item);
  }
  for (const item of root) {
    if (item.type !== 'directory') continue;
    let contents;
    try {
      contents = await client.getDirectoryContents(item.filename);
    } catch (e) {
      console.error(`  skip dir ${item.filename}: ${e.message}`);
      continue;
    }
    for (const sub of contents) {
      if (sub.type === 'file' && isVideo(sub.basename)) collect(sub);
    }
  }

  const result = [];
  for (const [code, pathMap] of byCode) {
    const files = [...pathMap.values()].sort((a, b) => a.sort_order - b.sort_order);
    result.push({ code, isMulti: files.length > 1, files });
  }
  return result;
}