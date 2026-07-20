"""Flask 主入口：路由 + 流式视频 + 静态文件。"""
import os, re, time, threading
from flask import (
    Flask, request, jsonify, render_template, send_file,
    abort, Response, redirect, url_for
)
from werkzeug.middleware.shared_data import SharedDataMiddleware

import db, worker

ROOT = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(ROOT, "media")
THUMB_DIR = os.path.join(ROOT, "thumbs")
app = Flask(__name__, static_folder="static", template_folder="templates")

# 让 /media/<path> 直接通过 Flask serve (不暴露文件系统)
@app.route("/media/<path:relpath>")
def serve_media(relpath):
    # 防穿越
    full = os.path.normpath(os.path.join(MEDIA_DIR, relpath))
    if not full.startswith(MEDIA_DIR) or not os.path.exists(full):
        abort(404)
    return send_file(full, conditional=True)


@app.route("/thumbs/<path:relpath>")
def serve_thumb(relpath):
    full = os.path.normpath(os.path.join(THUMB_DIR, relpath))
    if not full.startswith(THUMB_DIR) or not os.path.exists(full):
        abort(404)
    resp = send_file(full, mimetype="image/webp")
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


# ---- 页面 ----
@app.route("/")
def index():
    hero = db.list_videos(limit=5)
    sections = db.recent_sections(per_source=12)
    cont = db.continue_watching()
    return render_template("index.html",
                           hero=hero, sections=sections, continue_watching=cont)


@app.route("/download")
def download_page():
    stats = db.stats()
    active = db.list_tasks(active_only=True)
    recent = db.list_tasks(active_only=False, limit=20)
    return render_template("download.html",
                           stats=stats, active=active, recent=recent)


@app.route("/history")
def history_page():
    items = db.history_videos(limit=300)
    return render_template("history.html", items=items)


@app.route("/w/<int:vid>")
def watch_page(vid):
    v = db.get_video(vid)
    if not v:
        abort(404)
    # 同一来源的相关视频 (排除自己)
    related = db.list_videos(source=v["source"], limit=12)
    related = [r for r in related if r["id"] != vid][:12]
    return render_template("watch.html", v=v, related=related)


# ---- API ----
@app.route("/api/health")
def api_health():
    s = db.stats()
    # D 盘剩余
    try:
        import shutil
        _, _, free = shutil.disk_usage("D:\\")
        s["disk_free_gb"] = round(free / 2**30, 1)
    except Exception:
        s["disk_free_gb"] = None
    return jsonify({"status": "ok", **s})


@app.route("/api/videos")
def api_videos():
    source = request.args.get("source") or None
    q = request.args.get("q") or None
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    items = db.list_videos(source=source, q=q, limit=limit, offset=offset)
    return jsonify({"items": items, "limit": limit, "offset": offset})


@app.route("/api/videos/<int:vid>")
def api_video_get(vid):
    v = db.get_video(vid)
    if not v:
        abort(404, "not found")
    return jsonify(v)


@app.route("/api/videos/<int:vid>", methods=["DELETE"])
def api_video_delete(vid):
    v = db.get_video(vid)
    if not v:
        abort(404)
    # 删文件 (留 .info.json 留底排查)
    for rel in (v.get("file_path"),):
        if rel:
            p = os.path.join(ROOT, rel)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
    # 字幕
    base = os.path.splitext(p)[0] if v.get("file_path") else None
    if base:
        for ext in (".zh.vtt", ".en.vtt"):
            q = base + ext
            if os.path.exists(q):
                try: os.remove(q)
                except OSError: pass
    # 缩略图
    if v.get("thumb_path"):
        p = os.path.join(ROOT, v["thumb_path"])
        if os.path.exists(p):
            try: os.remove(p)
            except OSError: pass
    db.delete_video(vid)
    return jsonify({"ok": True})


@app.route("/api/enqueue", methods=["POST"])
def api_enqueue():
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()
    quality = (data.get("quality") or "720p").strip()
    audio_only = str(data.get("audio_only", "")).lower() in ("1", "true", "yes", "on")
    if not url:
        return jsonify({"error": "url is required"}), 400
    if quality not in worker.QUALITY_HEIGHT and quality != "audio":
        return jsonify({"error": f"invalid quality: {quality}"}), 400
    tid = db.enqueue_task(url, quality, audio_only)
    return jsonify({"task_id": tid})


@app.route("/api/tasks")
def api_tasks():
    active = request.args.get("active") == "1"
    return jsonify({"items": db.list_tasks(active_only=active, limit=50)})


@app.route("/api/tasks/<int:tid>")
def api_task_get(tid):
    t = db.get_task(tid)
    if not t:
        abort(404)
    return jsonify(t)


@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
def api_task_delete(tid):
    t = db.get_task(tid)
    if not t:
        abort(404)
    if t["status"] in ("queued",):
        db.update_task(tid, status="canceled", finished_at=int(time.time()))
        return jsonify({"ok": True, "canceled": True})
    # 正在跑的 — 标记 cancel, worker 不会中断 yt-dlp,但下一次循环不会再拉
    db.update_task(tid, error="用户取消 (将在当前阶段结束后停止)")
    return jsonify({"ok": True, "note": "任务正在执行,yt-dlp 完成后将自动停止后续任务"})


# ---- 播放端点 ----
@app.route("/api/stream/<int:vid>")
def api_stream(vid):
    v = db.get_video(vid)
    if not v or not v.get("file_path"):
        abort(404)
    full = os.path.join(ROOT, v["file_path"])
    if not os.path.exists(full):
        abort(404)
    # 标记已观看 + 续播位置
    pos = float(request.args.get("t", 0))
    db.mark_watched(vid, position_sec=pos)
    return send_file(full, conditional=True)


@app.route("/api/position/<int:vid>", methods=["POST"])
def api_position(vid):
    """前端每 5s 报一次当前播放位置。"""
    data = request.get_json(silent=True) or request.form
    pos = int(float(data.get("t", 0)))
    v = db.get_video(vid)
    if not v:
        abort(404)
    # 只在播放到 30s 后才记入续播
    if pos >= 30:
        db.update_video(vid, last_position_sec=pos)
    # 看完 (剩余 < 30s) — 清掉续播位置,让它从「继续观看」消失
    if v.get("duration_sec") and (v["duration_sec"] - pos) < 30:
        db.update_video(vid, last_position_sec=0)
    return jsonify({"ok": True})


@app.route("/api/history/clear", methods=["POST"])
def api_history_clear():
    db.clear_history()
    return jsonify({"ok": True})


# ---- main ----
# ---- Jinja 过滤器 ----
import datetime as _dt

def _human_time(ts):
    if not ts:
        return ""
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return str(ts)
    if ts < 1e9:
        return ""
    now = int(time.time())
    diff = now - ts
    if diff < 0: return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    if diff < 60: return f"{diff} 秒前"
    if diff < 3600: return f"{diff // 60} 分钟前"
    if diff < 86400: return f"{diff // 3600} 小时前"
    if diff < 86400 * 7: return f"{diff // 86400} 天前"
    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

def _human_bytes(n):
    if not n: return "0 B"
    n = float(n)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

app.jinja_env.filters["humantime"] = _human_time
app.jinja_env.filters["humanbytes"] = _human_bytes


def main():
    db.init()
    worker.start()
    # 局域网 0.0.0.0:7890
    app.run(host="0.0.0.0", port=7890, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()