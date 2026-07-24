// ffprobe-based technical metadata probe. Shared by server.js (lazy, on play)
// and scan.js (batch, at scan time). One ffprobe call fetches all fields.
//
// Zero deps: uses node:child_process spawn + JSON output from ffprobe.

import { spawn } from 'node:child_process';

/** Build a WebDAV URL with embedded basic auth, path segments URL-encoded. ffmpeg/ffprobe HTTP-GET it. */
export function webdavUrl(config, webdavPath) {
  const base = config.webdav.baseUrl;
  const m = base.match(/^(https?:\/\/)(.+)$/);
  const auth = `${encodeURIComponent(config.webdav.username)}:${encodeURIComponent(config.webdav.password)}@`;
  const pathEnc = webdavPath.split('/').map(encodeURIComponent).join('/');
  return `${m[1]}${auth}${m[2]}${pathEnc}`;
}

function parseFps(r) {
  if (!r) return null;
  const parts = r.split('/').map(Number);
  if (parts.length === 1) return parts[0] || null;
  const [n, d] = parts;
  if (!n || !d) return null;
  return Math.round((n / d) * 1000) / 1000;
}

/**
 * Probe a remote media URL via ffprobe. Returns a flat object of technical fields
 * (codecs, resolution, fps, bitrate, duration, audio/subtitle tracks) or null on
 * failure / timeout. Default 15s timeout -- moov-at-tail mp4s over slow WebDAV can
 * take minutes; we'd rather leave null than stall scan/playback.
 */
export function probeMedia(url, timeoutMs = 15000) {
  return new Promise((resolve) => {
    const child = spawn('ffprobe', [
      '-v', 'error',
      '-show_entries',
      'stream=codec_name,codec_type,width,height,r_frame_rate,profile,bit_rate,channels:stream_tags=language,title',
      '-show_entries', 'format=duration,bit_rate',
      '-of', 'json',
      url,
    ], { windowsHide: true });
    let out = '';
    const to = setTimeout(() => { try { child.kill('SIGKILL'); } catch {} }, timeoutMs);
    child.stdout.on('data', (d) => (out += d.toString()));
    child.on('error', () => { clearTimeout(to); resolve(null); });
    child.on('close', () => {
      clearTimeout(to);
      try {
        const j = JSON.parse(out);
        const streams = j.streams || [];
        const v = streams.find((s) => s.codec_type === 'video');
        const audios = streams.filter((s) => s.codec_type === 'audio');
        const subs = streams.filter((s) => s.codec_type === 'subtitle');
        const fmt = j.format || {};
        const audioTracks = audios.map((a) => ({
          codec: a.codec_name || null,
          lang: a.tags?.language || null,
          channels: a.channels ? Number(a.channels) : null,
          title: a.tags?.title || null,
        }));
        const subTracks = subs.map((s) => ({
          codec: s.codec_name || null,
          lang: s.tags?.language || null,
          title: s.tags?.title || null,
        }));
        resolve({
          v_codec: v?.codec_name || null,
          a_codec: audios[0]?.codec_name || null,
          width: v?.width ? Number(v.width) : null,
          height: v?.height ? Number(v.height) : null,
          fps: parseFps(v?.r_frame_rate),
          video_bitrate: v?.bit_rate ? Number(v.bit_rate) : null,
          video_profile: v?.profile || null,
          duration_real: fmt.duration ? Math.round(Number(fmt.duration)) : null,
          audio_tracks: audioTracks.length ? JSON.stringify(audioTracks) : null,
          subtitle_tracks: subTracks.length ? JSON.stringify(subTracks) : null,
        });
      } catch {
        resolve(null);
      }
    });
  });
}

/** Write probed metadata onto a single video row (per-file probe).
 *  See db.js applyProbeToVideo for the canonical implementation; this thin
 *  wrapper exists so callers can `import { applyProbeToVideo } from './probe.js'`. */
export { applyProbeToVideo } from './db.js';
