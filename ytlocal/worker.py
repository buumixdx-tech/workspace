"""yt-dlp 后台 worker — 单线程串行，处理队列。"""
import os, re, threading, time, traceback, unicodedata
import yt_dlp
from PIL import Image

import db

ROOT = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(ROOT, "media")
THUMB_DIR = os.path.join(ROOT, "thumbs")
COOKIES_PATH = os.path.join(ROOT, "cookies.txt")

QUALITY_HEIGHT = {
    "2160p": 2160, "1440p": 1440, "1080p": 1080,
    "720p": 720,  "480p": 480,  "360p": 360,  "144p": 144,
}


def safe_name(s: str, max_len: int = 80) -> str:
    """文件系统安全的名字：去非法字符、限长。"""
    if not s:
        return "untitled"
    s = unicodedata.normalize("NFKC", s).strip()
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", " ", s)
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s or "untitled"


def classify_site(url: str, info: dict) -> tuple[str, str]:
    """返回 (source, source_id)。"""
    extractor = info.get("extractor") or "unknown"
    sid = info.get("id") or ""
    # 把 twitter/x/nitter、bili 之类归一
    site_map = {
        "youtube": "YouTube",
        "twitter": "Twitter",
        "x": "Twitter",
        "bilibili": "B站",
        "bitchute": "BitChute",
        "vimeo": "Vimeo",
        "tiktok": "TikTok",
        "soundcloud": "SoundCloud",
        "reddit": "Reddit",
    }
    source = site_map.get(extractor, extractor.capitalize())
    if not sid and info.get("webpage_url"):
        sid = hashlib_md5(info["webpage_url"])[:11]
    return source, sid


def hashlib_md5(s: str) -> str:
    import hashlib
    return hashlib.md5(s.encode()).hexdigest()


def ytdlp_format_string(quality: str, audio_only: bool) -> str:
    if audio_only:
        return "bestaudio[ext=m4a]/bestaudio/best"
    h = QUALITY_HEIGHT.get(quality, 720)
    # 优先 mp4 视频 + m4a 音频，合并成 mp4；不行就单文件
    return (
        f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={h}]+bestaudio/"
        f"best[height<={h}][ext=mp4]/"
        f"best[height<={h}]/best"
    )


def progress_hook(tid: int):
    def hook(d):
        try:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes", 0)
                pct = int(done * 100 / total) if total else 0
                db.update_task(tid, status="downloading", progress_pct=pct,
                               error=f"{human_bytes(done)}/{human_bytes(total) if total else '?'}")
            elif d.get("status") == "finished":
                db.update_task(tid, status="postproc", progress_pct=99,
                               error="合并/转封装…")
            elif d.get("status") == "error":
                db.update_task(tid, status="failed", error=str(d.get("error") or "未知错误"),
                               finished_at=int(time.time()))
        except Exception:
            pass
    return hook


def human_bytes(n: int) -> str:
    if not n:
        return "0 B"
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def run_one(tid: int) -> bool:
    """处理一个任务。成功返回 True。"""
    task = db.get_task(tid)
    if not task:
        return False
    url = task["url"]; quality = task["quality"]; audio_only = bool(task["audio_only"])
    db.update_task(tid, status="downloading", progress_pct=0, error="抓取元数据…")

    try:
        # 先抓元数据 (不下载) — 需要同 opts, 避免 YouTube bot 检测在元数据阶段触发
        meta_opts = {"quiet": True, "no_warnings": True}
        if os.path.exists(COOKIES_PATH):
            meta_opts["cookiefile"] = COOKIES_PATH
            meta_opts["remote_components"] = ["ejs:github"]
            meta_opts["js_runtimes"] = {"node": {}}
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise RuntimeError("无法抓取元数据")
        # 可能是 playlist — 只取第一个视频
        if "entries" in info and info["entries"]:
            info = info["entries"][0]
        source, sid = classify_site(url, info)
        title = info.get("title") or "untitled"
        channel = info.get("uploader") or info.get("channel") or info.get("creator") or ""
        duration = info.get("duration")
        webpage = info.get("webpage_url") or url

        # 去重
        existing = db.find_by_source(source, sid)
        if existing:
            db.update_task(tid, status="done", progress_pct=100,
                           error=f"已在库: {existing['title']}",
                           video_id=existing["id"], finished_at=int(time.time()))
            return True

        # 组织路径
        site_dir = os.path.join(MEDIA_DIR, safe_name(source))
        os.makedirs(site_dir, exist_ok=True)
        out_template = os.path.join(site_dir, f"{safe_name(title)} [{sid}].%(ext)s")

        opts = {
            "quiet": True, "no_warnings": True, "noprogress": True,
            "outtmpl": out_template,
            "format": ytdlp_format_string(quality, audio_only),
            "merge_output_format": "mp4",
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh-Hans", "zh-Hant", "zh", "en"],
            "subtitlesformat": "vtt",
            "writeinfojson": True,
            "writethumbnail": True,
            "concurrent_fragment_downloads": 4,
            "retries": 3,
            "progress_hooks": [progress_hook(tid)],
        }
        # YouTube 反爬绕过 — 有 cookies.txt 就挂上
        if os.path.exists(COOKIES_PATH):
            opts["cookiefile"] = COOKIES_PATH
            # JS challenge 求解 (YouTube SABR / n-challenge)
            opts["remote_components"] = ["ejs:github"]
            opts["js_runtimes"] = {"node": {}}

        db.update_task(tid, error=f"下载: {title}")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([webpage])

        # 找产物文件
        base_no_ext = os.path.join(site_dir, f"{safe_name(title)} [{sid}]")
        mp4 = None
        for ext in ("mp4", "mkv", "webm", "m4a", "mp3"):
            p = base_no_ext + "." + ext
            if os.path.exists(p):
                mp4 = p; break
        if not mp4:
            raise RuntimeError("下载完成但找不到产物文件")

        size = os.path.getsize(mp4)

        # 字幕
        zh_vtt = base_no_ext + ".zh.vtt"
        en_vtt = base_no_ext + ".en.vtt"
        # yt-dlp 实际文件是 .zh-Hans.vtt / .zh.vtt / .en.vtt，统一软链/重命名
        for fname in os.listdir(site_dir):
            if not fname.startswith(os.path.basename(base_no_ext)):
                continue
            full = os.path.join(site_dir, fname)
            if fname.endswith(".zh-Hans.vtt") or fname.endswith(".zh-Hant.vtt") or fname.endswith(".zh.vtt"):
                if not os.path.exists(zh_vtt):
                    try:
                        os.rename(full, zh_vtt)
                    except OSError:
                        pass
            elif fname.endswith(".en.vtt"):
                if not os.path.exists(en_vtt):
                    try:
                        os.rename(full, en_vtt)
                    except OSError:
                        pass
        has_zh = int(os.path.exists(zh_vtt))
        has_en = int(os.path.exists(en_vtt))

        # 缩略图 → webp
        thumb_src = None
        for ext in ("jpg", "jpeg", "png", "webp"):
            p = base_no_ext + "." + ext
            if os.path.exists(p):
                thumb_src = p; break
        thumb_rel = None
        if thumb_src:
            os.makedirs(THUMB_DIR, exist_ok=True)
            thumb_dst = os.path.join(THUMB_DIR, f"{sid}.webp")
            try:
                with Image.open(thumb_src) as im:
                    im.convert("RGB").save(thumb_dst, "WEBP", quality=80, method=6)
                thumb_rel = os.path.relpath(thumb_dst, ROOT).replace("\\", "/")
                try:
                    os.remove(thumb_src)
                except OSError:
                    pass
            except Exception:
                pass

        # 入库
        file_rel = os.path.relpath(mp4, ROOT).replace("\\", "/")
        zh_rel = os.path.relpath(zh_vtt, ROOT).replace("\\", "/") if has_zh else None
        en_rel = os.path.relpath(en_vtt, ROOT).replace("\\", "/") if has_en else None
        # 把字幕相对路径存到 task 里临时用,后面统一进 videos 表
        db.update_task(tid, error=f"入库: {title}")
        vid = db.insert_video(
            source=source, source_id=sid, url=webpage, title=title,
            channel=channel, duration_sec=duration,
            thumb_path=thumb_rel, file_path=file_rel, size_bytes=size,
            has_zh_sub=has_zh, has_en_sub=has_en, status="ready",
        )
        db.update_task(tid, status="done", progress_pct=100,
                       error="", video_id=vid, finished_at=int(time.time()))
        # 字幕路径写到 note... 没字段, 先这样, 播放器用规则直接拼路径
        return True

    except Exception as e:
        db.update_task(tid, status="failed",
                       error=f"{type(e).__name__}: {e}",
                       finished_at=int(time.time()))
        return False


class Worker(threading.Thread):
    """单线程循环 worker。"""
    daemon = True

    def __init__(self):
        super().__init__(name="ytlocal-worker")
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                t = db.next_queued_task()
                if not t:
                    time.sleep(2.0); continue
                run_one(t["id"])
            except Exception:
                traceback.print_exc()
                time.sleep(2.0)


_worker: Worker | None = None


def start():
    global _worker
    if _worker and _worker.is_alive():
        return
    _worker = Worker()
    _worker.start()


def stop():
    global _worker
    if _worker:
        _worker.stop(); _worker.join(timeout=5)
        _worker = None