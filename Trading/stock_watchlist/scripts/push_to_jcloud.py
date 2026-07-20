"""批量推多个文件到 jcloud, 旧文件备份到 .bak_pre_2026_07_07."""
import os
import sys
import hashlib
import paramiko
import json

CFG = r"C:\Users\buumi\.claude\skills\jcloud\scripts\config.json"
BAK_SUFFIX = ".bak_pre_2026_07_07_v3"

# 任务 #209 + #210-213: 全套 + 模块化拆分新增
FILES = [
    # Python 后端
    "app.py",
    "routes.py",
    "src/indices_cache.py",
    "src/cache_invalidator.py",
    "src/errors.py",
    "src/db.py",
    "src/quote_cache.py",
    "src/profile_cache.py",
    "src/sector_aggregator.py",
    "src/yf_cache.py",
    # 前端 + 模板 (任务 #210-213 模块化拆分)
    "static/util.js",
    "static/chart.js",
    "static/sector.js",        # 新建
    "static/stocklist.js",     # 新建
    "static/notes.js",         # 新建
    "static/modal.js",         # 新建
    "static/app.js",
    "static/style.css",
    "templates/index.html",
]

LOCAL_ROOT = r"D:\WorkSpace\Trading\stock_watchlist"
REMOTE_ROOT = "/opt/stock_watchlist"

with open(CFG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    hostname=cfg["host"],
    port=cfg.get("port", 22),
    username=cfg["username"],
    key_filename=cfg.get("key_file"),
    timeout=30,
)
sftp = client.open_sftp()

# 先在远端建可能不存在的子目录
for rel in FILES:
    d = os.path.dirname(rel)
    if d:
        try:
            sftp.stat(f"{REMOTE_ROOT}/{d}")
        except FileNotFoundError:
            print(f"远端创建目录: {d}")
            sftp.mkdir(f"{REMOTE_ROOT}/{d}")

ok = 0
fail = 0
for rel in FILES:
    local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
    remote = f"{REMOTE_ROOT}/{rel}"
    if not os.path.exists(local):
        print(f"[SKIP] {rel} 本地不存在")
        continue
    local_size = os.path.getsize(local)
    with open(local, "rb") as f:
        local_md5 = hashlib.md5(f.read()).hexdigest()

    # 备份(如果远端已存在)
    try:
        sftp.stat(remote)
        sftp.rename(remote, remote + BAK_SUFFIX)
    except FileNotFoundError:
        pass

    # 上传
    sftp.put(local, remote)

    # 校验
    remote_size = sftp.stat(remote).st_size
    stdin, stdout, _ = client.exec_command(f"md5sum {remote}")
    remote_md5 = stdout.read().decode().split()[0]

    size_ok = local_size == remote_size
    md5_ok = local_md5 == remote_md5
    mark = "OK" if (size_ok and md5_ok) else "FAIL"
    if mark == "OK":
        ok += 1
    else:
        fail += 1
    print(f"[{mark}] {rel:40s} {local_size:>7} {local_md5[:8]}  vs  {remote_md5[:8]}")

print(f"\n汇总: {ok} ok / {fail} fail")

sftp.close()
client.close()
