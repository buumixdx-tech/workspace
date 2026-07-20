# YTLocal — 局域网私人视频库

类似 TMDB 风格的 yt-dlp Web 前端。下载 → 元数据入库 → HTML5 流式播放。
所有操作在浏览器完成。运行在 buumipc，监听 `0.0.0.0:7890`。

## 路由

| 路径 | 说明 |
|---|---|
| `/` | 浏览页 (Hero 轮播 + 继续观看 + 各来源章节) |
| `/download` | 下载操作页 + 任务队列 |
| `/w/<id>` | 播放页 (HTML5 video + 字幕 + 续播) |
| `/history` | 观看历史 |
| `/api/health` | 健康检查 |
| `/api/videos` | 视频列表 (`?source=&q=&limit=&offset=`) |
| `/api/enqueue` | POST `{url, quality, audio_only}` |
| `/api/tasks[/<id>]` | 任务状态 / DELETE 取消 |
| `/api/stream/<id>` | Range 流式 mp4 |
| `/api/position/<id>` | POST 上报播放进度 |
| `/media/...` `/thumbs/...` | 静态产物 |

## 启动

```powershell
# 开发模式
cd D:\workspace\ytlocal
python app.py

# 或后台 (nssm 安装为服务)
nssm install YTLocal "C:\Users\buumi\AppData\Local\Programs\Python\Python313\python.exe" "D:\workspace\ytlocal\app.py"
nssm set YTLocal AppDirectory D:\workspace\ytlocal
nssm start YTLocal
```

## 访问

```
http://<buumipc 局域网 IP>:7890
```

例：`http://192.168.x.x:7890` （手机/电脑同一 WiFi）

## 目录

- `app.py` — Flask 入口
- `worker.py` — yt-dlp 后台 worker
- `db.py` — SQLite 封装
- `ytlocal.db` — 元数据
- `media/<site>/<title> [<id>].{mp4,zh.vtt,en.vtt,info.json}`
- `thumbs/<id>.webp`
- `static/app.css`, `templates/*.html`

## 升级 yt-dlp

```powershell
python -m pip install -U yt-dlp
```