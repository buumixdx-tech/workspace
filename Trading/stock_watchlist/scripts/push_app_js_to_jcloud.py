"""单文件 sftp 传输: 本地 → jcloud 远端, 不重启 service."""
import os
import sys
import paramiko

LOCAL = r"D:\WorkSpace\Trading\stock_watchlist\static\app.js"
REMOTE = "/opt/stock_watchlist/static/app.js"
REMOTE_BAK = "/opt/stock_watchlist/static/app.js.bak_pre_2026_07_07"

# 读 config
CFG = r"C:\Users\buumi\.claude\skills\jcloud\scripts\config.json"
import json
with open(CFG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    hostname=cfg["host"],
    port=cfg.get("port", 22),
    username=cfg["username"],
    password=cfg["password"],
    timeout=30,
)
sftp = client.open_sftp()

# 1. 备份远端旧文件
try:
    sftp.stat(REMOTE)
    print(f"备份 {REMOTE} -> {REMOTE_BAK}")
    sftp.rename(REMOTE, REMOTE_BAK)
except FileNotFoundError:
    print(f"远端 {REMOTE} 不存在, 跳过备份")

# 2. 上传新文件
print(f"上传 {LOCAL} -> {REMOTE}")
sftp.put(LOCAL, REMOTE)

# 3. 校验大小
local_size = os.path.getsize(LOCAL)
remote_size = sftp.stat(REMOTE).st_size
print(f"本地 {local_size} bytes / 远端 {remote_size} bytes / 匹配={local_size == remote_size}")

# 4. 校验 md5
import hashlib
with open(LOCAL, "rb") as f:
    local_md5 = hashlib.md5(f.read()).hexdigest()

# 远端 md5
stdin, stdout, stderr = client.exec_command(f"md5sum {REMOTE}")
remote_md5 = stdout.read().decode().split()[0]
print(f"本地 md5: {local_md5}")
print(f"远端 md5: {remote_md5}")
print(f"md5 匹配={local_md5 == remote_md5}")

sftp.close()
client.close()
print("完成")
