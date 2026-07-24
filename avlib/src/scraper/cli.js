// CLI: node src/scraper/cli.js <code> [--save-cover[=dir]] [--json]
// Prints the scraped metadata as JSON. Optionally downloads the cover.

import { findByCode } from './missav.js';
import { writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const argv = process.argv.slice(2);
const code = argv.find((a) => !a.startsWith('-'));
const saveCoverIdx = argv.indexOf('--save-cover');
const saveCover = saveCoverIdx !== -1;
const coverDir = (saveCover && argv[saveCoverIdx + 1] && !argv[saveCoverIdx + 1].startsWith('-'))
  ? argv[saveCoverIdx + 1]
  : '.';

if (!code) {
  console.error('Usage: node src/scraper/cli.js <code> [--save-cover[=dir]]');
  console.error('Example: node src/scraper/cli.js ABP-001 --save-cover');
  process.exit(1);
}

try {
  const movie = await findByCode(code);
  if (!movie) {
    console.error(`No match for code: ${code}`);
    process.exit(2);
  }
  console.log(JSON.stringify(movie, null, 2));

  if (saveCover) {
    const resp = await fetch(movie.cover_url);
    if (!resp.ok) throw new Error(`cover fetch ${resp.status}`);
    const buf = Buffer.from(await resp.arrayBuffer());
    await mkdir(coverDir, { recursive: true });
    const out = path.join(coverDir, `${movie.id}.jpg`);
    await writeFile(out, buf);
    console.error(`cover saved -> ${out} (${(buf.length / 1024).toFixed(0)} KB)`);
  }
} catch (err) {
  console.error('scrape failed:', err.message);
  process.exit(3);
}
