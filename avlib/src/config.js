import { readFileSync } from 'node:fs';

// Env vars (if set) override config.json. Useful for keeping secrets out of
// the repo: WEBDAV_USERNAME / WEBDAV_PASSWORD are commonly sourced from
// deployment env (systemd EnvironmentFile, docker --env, .bashrc, etc).
const ENV_OVERRIDES = {
  'webdav.username':  ['WEBDAV_USERNAME', 'WEBDAV_USER'],
  'webdav.password':  ['WEBDAV_PASSWORD', 'WEBDAV_PASS'],
  'webdav.baseUrl':   ['WEBDAV_BASE_URL', 'WEBDAV_URL'],
};

/** Return the first non-empty value among the named env vars, else undefined.
 *  Empty string is treated as "not set" so `WEBDAV_PASSWORD= ` won't wipe a
 *  real value from config.json. */
function envFirst(names) {
  for (const n of names) {
    const v = process.env[n];
    if (v !== undefined && v !== '') return v;
  }
  return undefined;
}

export function loadConfig(path = './config.json') {
  const cfg = JSON.parse(readFileSync(path, 'utf8'));
  cfg.webdav ||= {};
  for (const [dotted, names] of Object.entries(ENV_OVERRIDES)) {
    const v = envFirst(names);
    if (v !== undefined) {
      const [k1, k2] = dotted.split('.');
      cfg[k1][k2] = v;
    }
  }
  return cfg;
}
