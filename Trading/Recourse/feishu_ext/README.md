# feishu_ext

飞书消息 → LLM 提取 → 写入 SQLite（本地）→ Dashboard 展示的完整预处理管道。

---

## 系统架构

```
飞书群
  │
  ▼
jcloud feishu_sync                              [每分钟/每小时自动运行]
  │ /root/feishu/
  │ /var/log/feishu_sync.log
  ▼
jcloud messages_proxy (127.0.0.1:9622)          [HTTP API，供本地增量拉取]
  │ /root/messages_proxy/messages_proxy.py
  │ GET /sync/messages/incremental             [增量拉消息]
  │ GET /sync/status                            [feishu_sync 状态]
  ▼
本地 feishu_ext
  │ feishu_preprocess.py                       [主 pipeline]
  │ run_wrapper.py                             [wrapper: 锁 + push dashboard]
  │ _scheduler.py                              [Python 后台调度器，替代 Task Scheduler]
  │ data/preprocess.db                         [messages + extracted 3表]
  │ data/heartbeat.json                        [最近一次运行状态]
  │
  ├─► feishu_ima (feishu_to_ima.py)           [→ IMA 推送]
  │    data/feishu_to_ima.db
  │
  └─► jcloud rag_dashboard (https://buumicloud.com.cn/state/)
       4 卡片: Feishu Extract | jcloud Feishu Sync | Feishu to IMA | MyCloud to IMA
```

---

## 数据表结构

### messages 表
镜像自 jcloud feishu_sync 的原始消息（通过 messages_proxy HTTP API 同步）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，AUTOINCREMENT，永不复用 |
| ts | INTEGER | 毫秒时间戳（飞书服务器时间） |
| kind | TEXT | `'t'`=文字，`'i'`=图片 |
| content | TEXT | 消息原文 |
| content_hash | TEXT | 内容哈希 |

### extracted 表
LLM 提取的结构化记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| msg_id | INTEGER | 主键，对应 messages.id |
| ts | INTEGER | 毫秒时间戳 |
| info_type | INTEGER | 消息类型（1-10，见下方） |
| category | TEXT | 分类 |
| summary | TEXT | LLM 提取的摘要 |
| created_at | TEXT | 写入时间，UTC ISO 格式 |

### extracted_stocks 表
每条消息涉及的股票列表。

| 字段 | 类型 | 说明 |
|------|------|------|
| msg_id | INTEGER | 主键引用 messages.id |
| stock | TEXT | 股票代码 |

### extracted_terms 表
每条消息涉及的核心技术词。

| 字段 | 类型 | 说明 |
|------|------|------|
| msg_id | INTEGER | 主键引用 messages.id |
| term | TEXT | 技术词 |

### info_type 类型定义

| 值 | 类型名 |
|----|--------|
| 1 | 个股点评 |
| 2 | 行业板块点评 |
| 3 | 产业点评 |
| 4 | 盘前消息汇总 |
| 5 | 盘后总结 |
| 6 | 周报 |
| 7 | 盘中提示 |
| 8 | 时政新闻 |
| 9 | 段子 |
| 10 | 其他 |

---

## 文件索引

| 文件 | 作用 |
|------|------|
| `feishu_preprocess.py` | 主 pipeline，7步处理流程 |
| `feishu_db_writer.py` | 数据库操作：sync、upsert、schema 管理 |
| `run_wrapper.py` | wrapper：环境变量、锁文件防重入、push dashboard |
| `_scheduler.py` | Python 后台调度器，替代 Windows Task Scheduler |
| `feishu_web_ui.py` | 浏览器控制台（可选） |
| `prompts/` | LLM prompt 模板和 schema 定义 |
| `data/preprocess.db` | 生产数据库（messages + extracted 3表） |
| `data/heartbeat.json` | 最近一次 pipeline 运行状态 |
| `data/last_run.json` | wrapper 最近执行时间（用于晚间/周末频率控制） |
| `scripts/` | 独立工具脚本 |

---

## 定时任务

### 调度器

- **方式**：Python `_scheduler.py` 后台进程（替代 Windows Task Scheduler）
- **进程**：`pythonw D:\workspace\Trading\Recourse\feishu_ext\_scheduler.py`
- **频率**：每 5 分钟触发一次 `run_wrapper.py`
- **自启**：需在 Windows 启动文件夹或注册表添加快捷方式

### wrapper 执行频率控制（run_wrapper.py 内部逻辑）

- **工作日 08:00–19:00**：每次都真正执行 pipeline
- **晚间/周末**：每次触发，但距上次执行 < 3600s 则跳过（减少空跑）

### 锁文件防重入

- 锁文件：`data/.locks/feishu_preprocess.lock`
- Windows：`msvcrt.locking(LK_LOCK)` OS 级排他锁
- POSIX：`fcntl.flock(LOCK_EX)`
- **注意**：必须保持锁 fd 打开直到 pipeline 结束；Windows 关闭 fd 即释放锁

---

## 环境变量

### 核心密钥

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 阿里 DashScope API Key（qwen3.5-flash） |

### feishu_preprocess 控制

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FEISHU_PREPROCESS_MODE` | `historical` | 运行模式 |
| `FEISHU_PREPROCESS_MAX_TOTAL_CHARS` | `50000` | 批次总原文字符上限 |
| `FEISHU_PREPROCESS_SAFETY_MAX_ITEMS` | `500` | 单批最多条数兜底 |

### 同步源配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REMOTE_FEISHU_MESSAGES_URL` | `https://buumicloud.com.cn/rag-messages-api` | jcloud messages_proxy |
| `REMOTE_FEISHU_MESSAGES_USER` | `buumi` | 认证用户 |
| `REMOTE_FEISHU_MESSAGES_PASS` | `xdxis1234` | 认证密码 |
| `SYNC_MESSAGES_DB` | `/root/feishu/data/.../messages.db` | 本地同步路径（仅 USE_REMOTE=False 时用） |

### Dashboard

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FEISHU_EXT_DASHBOARD_URL` | `https://buumicloud.com.cn/state/push` | push 目标 |
| `FEISHU_EXT_DASHBOARD_USER` | `buumi` | 认证用户 |
| `FEISHU_EXT_DASHBOARD_PASS` | `xdxis1234` | 认证密码 |

---

## 7步处理流程（feishu_preprocess.py）

1. **init** — 初始化 SQLite 表结构（messages + extracted 3表）
2. **sync** — 从 jcloud messages_proxy 增量同步 messages 到本地（HTTP API）
3. **fetch** — 增量获取待处理消息（水位：`extracted.max(ts)`）
4. **extract** — 批量调用 qwen3.5-flash 做 info_type 分类 + 字段提取
5. **align** — 将 msg_id 对齐回 LLM 输出
6. **write** — 写入 extracted 表（含 stocks/terms 子表）
7. **heartbeat** — 写入 heartbeat.json + 4个产物文件

---

## Dashboard

访问：https://buumicloud.com.cn/state/

### 4 个卡片

| 卡片 | 数据来源 | 说明 |
|------|----------|------|
| **Feishu Extract** | `run_wrapper.py` push | 本地 feishu_ext 状态 |
| **jcloud Feishu Sync** | `run_wrapper.py` 调 `/sync/status` | jcloud feishu_sync 状态 |
| **Feishu to IMA** | `run_wrapper.py` 读 `feishu_ima.db` | feishu→IMA 推送状态 |
| **MyCloud to IMA** | `mycloud_ima_wrapper` push | MyCloud→IMA 状态 |

### push 时序

1. `_scheduler.py` 每 5 分钟触发 `run_wrapper.py`
2. wrapper 从 `feishu_ima.db` 读 Feishu to IMA 状态
3. wrapper 调 `https://buumicloud.com.cn/rag-messages-api/sync/status` 拿 jcloud sync 状态
4. 合并为 `{feishu, feishu_ima, jcloud_sync}` push 到 dashboard

---

## jcloud feishu_sync（上游数据源）

| 项目 | 值 |
|------|----|
| 代码目录 | `/root/feishu/` |
| 消息数据库 | `/root/feishu/data/oc_8121f1662983563a46a6b3c818631ddc/messages.db` |
| 同步 wrapper | `/root/feishu_sync_wrapper.sh` |
| 日志文件 | `/var/log/feishu_sync.log` |

### 同步规则

- **工作日 08:30–15:30**：每分钟执行（TRADING 模式）
- **其他时间**：每小时整点执行（HOURLY 模式）
- 每次执行增量拉取飞书消息，写入 messages.db

### messages_proxy 接口

| 接口 | 说明 |
|------|------|
| `GET /health` | 健康检查 + messages 统计 |
| `GET /sync/messages/incremental?since_id=N&limit=M` | 增量拉消息 |
| `GET /sync/status` | feishu_sync 状态（log 解析 + db 水位） |

---

## 手动操作

### 触发一次 wrapper
```bash
cd D:\workspace\Trading\Recourse\feishu_ext
python run_wrapper.py
```

### 触发一次 pipeline（绕过调度器）
```bash
python feishu_preprocess.py
```

### 手动 push dashboard
```bash
python -c "
from run_wrapper import _push_state_to_dashboard, _get_db_stats, _read_heartbeat
_push_state_to_dashboard(_read_heartbeat(), _get_db_stats())
"
```

### 重启调度器
```bash
# 杀掉旧的
taskkill //F //IM pythonw.exe

# 重新启动
start pythonw D:\workspace\Trading\Recourse\feishu_ext\_scheduler.py
```

---

## 查询命令

### 查看运行状态
```bash
# wrapper 日志
tail -20 D:\workspace\Trading\Recourse\logs\feishu_ext_wrapper.log

# scheduler 日志
tail -5 D:\workspace\Trading\Recourse\logs\feishu_scheduler.log

# heartbeat
cat D:\workspace\Trading\Recourse\feishu_ext\data\heartbeat.json
```

### 查看水位差距
```python
import sqlite3
from datetime import datetime, timezone, timedelta

db = r'D:\workspace\Trading\Recourse\feishu_ext\data\preprocess.db'
tz = timezone(timedelta(hours=8))
con = sqlite3.connect(db)

msg_ts = con.execute('SELECT MAX(ts) FROM messages').fetchone()[0]
ext_ts = con.execute('SELECT MAX(ts) FROM extracted').fetchone()[0]
ima_ts = con.execute('SELECT last_ts FROM bucket_state WHERE id=1').fetchone()[0]

print('messages:  ', datetime.fromtimestamp(msg_ts/1000, tz).strftime('%Y-%m-%d %H:%M:%S'))
print('extracted: ', datetime.fromtimestamp(ext_ts/1000, tz).strftime('%Y-%m-%d %H:%M:%S'))
print('feishu_ima:', datetime.fromtimestamp(ima_ts/1000, tz).strftime('%Y-%m-%d %H:%M:%S'))
con.close()
```

### 查看 jcloud feishu_sync 状态（HTTP）
```bash
curl https://buumicloud.com.cn/rag-messages-api/sync/status -u buumi:xdxis1234
```

---

## 故障排查

### "skip: lock held by another process" 持续出现

- **原因**：`msvcrt.locking()` 成功返回 `None` 被误判为失败，锁 fd 未正确保存，导致锁被 OS 持续拒绝
- **修复**：改用异常捕获判断成功/失败（`try: msvcrt.locking() except OSError: return False`）
- **临时处理**：删掉 `data/.locks/feishu_preprocess.lock`，杀掉残留 Python 进程

### 调度器没触发

- 检查 `_scheduler.py` 进程是否存活：`tasklist | findstr pythonw`
- 检查日志：`tail D:\workspace\Trading\Recourse\logs\feishu_scheduler.log`

### dashboard 无数据（fetch failed）

- 检查 `/state/latest` 返回 200：`curl https://buumicloud.com.cn/state/latest -u buumi:xdxis1234`
- 检查 wrapper push 是否成功：`tail logs/feishu_ext_wrapper.log`

### messages 水位正常但 extracted 不增加

- 检查 `DASHSCOPE_API_KEY` 是否正确
- 检查 pipeline 日志是否有 LLM 调用记录
- 检查 `MAX_TOTAL_CHARS=50000` 是否足够——如果字符数不够一批，不会触发 LLM

---

## 相关项目

| 项目 | 路径 |
|------|------|
| feishu_ima | `D:\workspace\Trading\Recourse\feishu_ima\` |
| jcloud messages_proxy | `/root/messages_proxy/messages_proxy.py`（jcloud） |
| jcloud rag_dashboard | `/opt/rag_dashboard/dashboard.py`（jcloud） |
| feishu_sync | `/root/feishu/`（jcloud） |
