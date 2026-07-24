// missav scraper module
// Metadata via Recombee backend (not Cloudflare-protected). Cover via fourhoi CDN.
// Zero dependencies: uses Node global fetch + node:crypto.
//
// Mechanism reverse-engineered from missav's frontend (see EchterAlsFake/unofficial-api-for-missav).
// If Recombee ever returns 401/403, the PUBLIC_TOKEN has rotated - re-extract from
// missav.ws page JS (search for the long token string) and update it here.

import crypto from 'node:crypto';

const RECOMBEE_HOST = 'client-rapi-missav.recombee.com';
const DATABASE_ID = 'missav-default';
const PUBLIC_TOKEN = 'Ikkg568nlM51RHvldlPvc2GzZPE9R4XGzaH9Qj4zK9npbbbTly1gj9K4mgRn0QlV';

const HEADERS = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
  Origin: 'https://missav.ws',
  Referer: 'https://missav.ws/',
};

// Reproduce missav's _signUrl: HMAC-SHA1 over "/{db}{path}?frontend_timestamp=unix" with the public token.
function signPath(path) {
  const ts = Math.floor(Date.now() / 1000);
  let unsigned = `/${DATABASE_ID}${path}`;
  unsigned += (unsigned.includes('?') ? '&' : '?') + `frontend_timestamp=${ts}`;
  const sig = crypto.createHmac('sha1', PUBLIC_TOKEN).update(unsigned, 'utf8').digest('hex');
  return unsigned + `&frontend_sign=${sig}`;
}

/** Free-text search (code / actress / title fragment, any language). Returns array of {id, ...props}. */
export async function search(query, { count = 10, signal } = {}) {
  const userId = `anon_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
  const path = `/search/users/${encodeURIComponent(userId)}/items/`;
  const url = `https://${RECOMBEE_HOST}${signPath(path)}`;
  const body = { searchQuery: String(query).trim(), count, cascadeCreate: true, returnProperties: true };
  const resp = await fetch(url, {
    method: 'POST',
    headers: HEADERS,
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    const hint = (resp.status === 401 || resp.status === 403)
      ? ' [PUBLIC_TOKEN likely rotated - re-extract from missav.ws JS]'
      : '';
    throw new Error(`Recombee search ${resp.status}: ${text.slice(0, 200)}${hint}`);
  }
  const data = await resp.json();
  return (data.recomms || []).map((r) => ({ id: r.id, ...r.values }));
}

/** Normalize a code: lowercase, insert hyphen if missing, strip -uncensored-leak (default = censored). */
export function normalizeCode(code) {
  let c = String(code).trim().toLowerCase();
  c = c.replace(/[-_\s]?uncensored[-_\s]?leak\b/g, '').trim();
  c = c.replace(/^([a-z]{2,5})[-_\s]?(\d{2,5})$/, '$1-$2');
  return c;
}

/** Cover URL on fourhoi CDN (not Cloudflare-protected; 7/7 reliable in testing). */
export function coverUrl(id) {
  return `https://fourhoi.com/${id}/cover-n.jpg`;
}

/**
 * Find a movie by AV code. Prefers the exact censored id, falls back to the
 * -uncensored-leak variant if that's all there is, else the top search hit.
 * Returns null if nothing matches.
 */
export async function findByCode(code, { signal } = {}) {
  const norm = normalizeCode(code);
  const results = await search(norm, { count: 10, signal });
  const match =
    results.find((r) => r.id === norm) ||
    results.find((r) => r.id === `${norm}-uncensored-leak`) ||
    results[0];
  if (!match) return null;
  return toMovie(match);
}

/** Shape a raw Recombee item into a cleaner movie object (keeps raw too). */
export function toMovie(item) {
  const releasedAt = item.released_at ? new Date(item.released_at * 1000) : null;
  return {
    id: item.id,
    code: item.id,
    title: item.title ?? null,           // Japanese original
    title_zh: item.title_zh ?? null,     // traditional
    title_cn: item.title_cn ?? null,     // simplified
    title_en: item.title_en ?? null,
    actresses: item.actresses ?? [],
    actors: item.actors ?? [],
    directors: item.directors ?? [],
    labels: item.labels ?? [],           // publisher
    markers: item.markers ?? [],         // maker / brand
    genres: item.genres ?? [],
    series: item.series ?? [],
    tags: item.tags ?? [],
    released_at: item.released_at ?? null,
    released_date: releasedAt ? releasedAt.toISOString().slice(0, 10) : null,
    duration_sec: item.duration ?? null,
    is_uncensored_leak: item.is_uncensored_leak ?? false,
    type: item.type ?? null,
    cover_url: coverUrl(item.id),
    raw: item,
  };
}
