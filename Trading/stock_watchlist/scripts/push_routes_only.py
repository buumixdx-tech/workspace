"""Targeted: push only routes.py + restart stock-watchlist service."""
import paramiko, json, hashlib, os

CFG = r"C:\Users\buumi\.claude\skills\jcloud\scripts\config.json"
LOCAL = r"D:\WorkSpace\Trading\stock_watchlist\routes.py"
REMOTE = "/opt/stock_watchlist/routes.py"
TS = "2026_07_08"

with open(CFG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    hostname=cfg["host"], port=cfg.get("port", 22),
    username=cfg["username"], key_filename=cfg.get("key_file"), timeout=30,
)
sftp = client.open_sftp()

# backup on remote (only if exists)
try:
    sftp.stat(REMOTE)
    bak = f"{REMOTE}.bak_pre_body300_{TS}"
    try:
        sftp.stat(bak)
        print(f'backup {bak} already exists, skip')
    except FileNotFoundError:
        sftp.rename(REMOTE, bak)
        print(f'backup -> {bak}')
except FileNotFoundError:
    print(f'remote {REMOTE} does not exist (unexpected)')

# upload
sftp.put(LOCAL, REMOTE)

# verify
local_md5 = hashlib.md5(open(LOCAL, 'rb').read()).hexdigest()
sin, sout, _ = client.exec_command(f"md5sum {REMOTE}")
remote_md5 = sout.read().decode().split()[0]
print(f'  local  md5: {local_md5[:12]}')
print(f'  remote md5: {remote_md5[:12]}')
assert local_md5 == remote_md5, 'md5 mismatch!'
print('OK: routes.py deployed and md5 matches')

# restart watchlist service
print('\n--- restart stock-watchlist.service ---')
sin, sout, serr = client.exec_command(
    "bash -lc 'systemctl restart stock-watchlist.service; sleep 2; systemctl is-active stock-watchlist.service'",
    timeout=30,
)
print(sout.read().decode().strip())

# verify HTTP still up
import urllib.request, base64
auth = base64.b64encode(b'buumi:xdxis1234').decode()
try:
    req = urllib.request.Request('https://buumicloud.com.cn/watchlist/api/notes?stock_code=000001',
                                 headers={'Authorization': f'Basic {auth}'})
    r = urllib.request.urlopen(req, timeout=10)
    print(f'  /api/notes: {r.status}')
except Exception as e:
    print(f'  /api/notes: ERR {e}')

# smoke test: post a 250-char note (should succeed now, would have failed before with "200 字" error)
print('\n--- smoke test: post 250-char note body ---')
import json as _json
big_body = 'A' * 250  # 250 chars
test_code = '000001'  # use an existing code; if not present, we'll see "stock not found" instead
payload = _json.dumps({"title": "300字测试", "body": big_body, "tags": []}).encode()
try:
    req = urllib.request.Request(
        f'https://buumicloud.com.cn/watchlist/api/stocks/{test_code}/notes',
        data=payload, headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json',
        }, method='POST')
    r = urllib.request.urlopen(req, timeout=10)
    print(f'  POST 250-char note: {r.status} {r.read().decode()[:200]}')
except urllib.error.HTTPError as e:
    print(f'  POST 250-char note: HTTP {e.code} {e.read().decode()[:200]}')
except Exception as e:
    print(f'  POST 250-char note: ERR {e}')

# also test 350-char note (should fail with new "300 字" message)
print('\n--- smoke test: post 350-char note body (should be rejected with new 300 limit) ---')
too_big = 'B' * 350
payload = _json.dumps({"title": "300字测试", "body": too_big, "tags": []}).encode()
try:
    req = urllib.request.Request(
        f'https://buumicloud.com.cn/watchlist/api/stocks/{test_code}/notes',
        data=payload, headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json',
        }, method='POST')
    r = urllib.request.urlopen(req, timeout=10)
    print(f'  POST 350-char note: {r.status} (UNEXPECTED success)')
except urllib.error.HTTPError as e:
    body_text = e.read().decode()
    print(f'  POST 350-char note: HTTP {e.code}')
    print(f'    body: {body_text[:300]}')
    assert '300' in body_text, f'error message should mention 300 字, got: {body_text[:200]}'
    print('    PASS: error mentions 300 字')
except Exception as e:
    print(f'  POST 350-char note: ERR {e}')

sftp.close(); client.close()
print('[done]')