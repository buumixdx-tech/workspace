# feishu_to_ima 手动运行指南

## 状态

**2026-07-04 起无 Task Scheduler**（`Feishu_To_Ima_10m` 已删除），全手动触发。
跑前先看水位，没数据时跑也是空操作但会起 IMA 鉴权（小事）。

## 路径

```
D:\WorkSpace\Trading\Recourse\
├── feishu_ext\            # feishu_preprocess 替代品 + preprocess.db (上游)
├── feishu_ima\            # 本目录
│   ├── data\
│   │   ├── feishu_to_ima.db   # 水位 + IMA posted 状态 (45 TXT, 2065 msg_ids)
│   │   └── ima_txt\           # 已拼好的 TXT (上传前在, 上传后保留)
│   ├── scripts\
│   │   ├── run_real.ps1   # REAL RUN (传 IMA)
│   │   └── run_dry.ps1    # DRY RUN (只看水位 + 拼 TXT, 不上传)
│   ├── feishu_to_ima.py   # 主入口
│   └── ...
└── mycloud_ima\           # mycloud_preprocess (独立)
```

## 手动跑

```powershell
# DRY RUN (默认, 安全, 不上传)
powershell -ExecutionPolicy Bypass -File D:\WorkSpace\Trading\Recourse\feishu_ima\scripts\run_dry.ps1

# REAL RUN (真上传, 注意 IMA 限流 code 200005)
powershell -ExecutionPolicy Bypass -File D:\WorkSpace\Trading\Recourse\feishu_ima\scripts\run_real.ps1
```

输出末尾会打印：
- `watermark: (last_ts, last_msg_id), bucket_seq=N` — 累计水位
- `unbatched: 0` — 没新数据就这个 = 不需要跑
- `uploaded msg_ids: N` — IMA 已传累计
- `txt_bucket 文件数: N` — 拼了多少 TXT
- `pending uploads: 0` — 待上传（永远是 0 因为是手动）

## 限流注意

**IMA 每日上限** (code 200005) — 一旦触发，等次日 0 点 (Asia/Shanghai) 重置。
建议每天手动跑 1 次，**别多次**。txt_bucket 是断点设计，下次跑会从水位继续。

## 故障排除

| 现象 | 原因 | 修复 |
|---|---|---|
| `FileNotFoundError: 上游 feishu_preprocess.db 不存在` | db_writer 默认路径指向旧 D:\workspace\LightRAG | 已修，新默认 `D:\WorkSpace\Trading\Recourse\feishu_ext\data\preprocess.db` |
| IMA 401 / 403 | client_id / api_key 失效 | 检查 `~/.config/ima/{client_id,api_key}` |
| IMA 200005 | 触每日上限 | 等明天 |
| TXT upload OK 但 lightrag 端没有 | feishu_to_ima 不直接调 lightrag，那是 feishu_preprocess.py 干的 (走 feishu_ext) | 跑 feishu_ext 的 preprocess.py |