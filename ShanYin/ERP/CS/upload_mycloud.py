import paramiko
import io

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('111.228.51.56', username='root', password='pUUkenQ^', timeout=10)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>MyCloud</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#1a1a2e;--card:#16213e;--accent:#0ea5e9;--text:#e2e8f0;--dim:#94a3b8;--border:#334155}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:16px;padding-bottom:80px}
header{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border);margin-bottom:16px}
h1{font-size:1.2rem}
select{background:var(--card);color:var(--text);border:1px solid var(--border);padding:8px 12px;border-radius:8px}
.tabs{display:flex;gap:4px;margin-bottom:16px}
.tab{flex:1;padding:10px;background:var(--card);border:none;color:var(--dim);border-radius:8px;cursor:pointer}
.tab.active{background:var(--accent);color:#fff}
.input-area{background:var(--card);border-radius:12px;padding:16px;margin-bottom:16px}
textarea{width:100%;min-height:200px;background:transparent;border:none;color:var(--text);font-size:1rem;resize:none;outline:none}
textarea::placeholder{color:var(--dim)}
.preview{min-height:200px;font-size:1rem;line-height:1.6;display:none}
.preview.active{display:block}
.preview h1,.preview h2,.preview h3{margin:12px 0 8px}
.preview p{margin:8px 0}
.preview code{background:#0f172a;padding:2px 6px;border-radius:4px}
.preview pre{background:#0f172a;padding:12px;border-radius:8px;overflow-x:auto}
.preview ul,.preview ol{padding-left:20px}
.preview blockquote{border-left:3px solid var(--accent);padding-left:12px;color:var(--dim)}
.toolbar{display:flex;gap:8px;padding-top:12px}
.toolbar button{width:48px;height:48px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:1.1rem;cursor:pointer}
.send-btn{flex:1;background:var(--accent);border:none;border-radius:8px;color:#fff;font-size:1rem;font-weight:600}
.send-btn:active{opacity:0.8}
.files{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.file{position:relative;width:56px;height:56px;background:var(--bg);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.6rem;text-align:center;padding:4px;border:1px solid var(--border)}
.file .x{position:absolute;top:-5px;right:-5px;width:16px;height:16px;background:#ef4444;border-radius:50%;font-size:0.6rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
.records{margin-top:16px}
.record{background:var(--card);border-radius:12px;padding:14px;margin-bottom:10px}
.record-header{font-size:0.75rem;color:var(--dim);margin-bottom:6px;display:flex;justify-content:space-between}
.record-cat{background:var(--accent);color:#fff;padding:1px 6px;border-radius:4px;font-size:0.65rem}
.record-content{font-size:0.9rem;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.toast{position:fixed;bottom:90px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:10px 20px;border-radius:6px;font-size:0.85rem;opacity:0;transition:opacity 0.3s}
.toast.show{opacity:1}
input[type=file]{display:none}
.loading{text-align:center;padding:40px;color:var(--dim)}
</style>
</head>
<body>
<header><h1>MyCloud</h1><select id="cat"><option value="stock">Stock</option><option value="life">Life</option><option value="funny">Funny</option></select></header>
<div class="tabs"><button class="tab active" data-t="edit">Edit</button><button class="tab" data-t="records">Records</button></div>
<div id="input">
<div class="input-area">
<div id="editor"><textarea id="txt" placeholder="paste text or MD..."></textarea><div class="files" id="files"></div></div>
<div class="preview" id="preview"></div>
</div>
<div class="toolbar"><button onclick="pickFile()">F</button><button onclick="pickFile('image/*')">I</button><button onclick="pickFile('.pdf,.doc,.xls')">D</button><button class="send-btn" onclick="send()">SEND</button></div>
</div>
<div id="list"></div>
<div id="toast" class="toast"></div>
<input type="file" id="fi" multiple>
<script>
const A="/api";let cur="edit",fs=[];
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");cur=b.dataset.t;document.getElementById("input").style.display=cur=="edit"?"block":"none";document.getElementById("list").style.display=cur=="records"?"block":"none";if(cur=="records")load();}));
document.getElementById("preview").addEventListener("click",()=>{const p=document.getElementById("preview");if(p.classList.contains("active")){document.getElementById("editor").style.display="block";p.classList.remove("active");}else{const c=document.getElementById("txt").value.trim();if(c){p.innerHTML=DOMPurify.sanitize(marked.parse(c));document.getElementById("editor").style.display="none";p.classList.add("active");}}});
function pickFile(a){const i=document.getElementById("fi");i.accept=a||"*/*";i.onchange=()=>{Array.from(i.files).forEach(f=>{fs.push(f);const d=document.createElement("div");d.className="file";d.innerHTML='<span>'+f.name.slice(0,8)+'</span><span class="x" onclick="rm(this)">x</span>';document.getElementById("files").appendChild(d);});i.value="";};i.click();}
function rm(e){fs=fs.filter(f=>f!==e.parentElement.dataset.name);e.parentElement.remove();}
async function send(){const c=document.getElementById("txt").value.trim(),x=document.getElementById("cat").value;if(!c&&fs.length===0){toast("empty");return;}const btn=document.querySelector(".send-btn");btn.textContent="...";btn.disabled=true;try{if(c)await fetch(A+"/records",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({type:"text",category:x,content:c})});for(const f of fs){const fd=new FormData();fd.append("category",x);fd.append("file",f);await fetch(A+"/files",{method:"POST",body:fd});}document.getElementById("txt").value="";fs=[];document.getElementById("files").innerHTML="";toast("ok");}catch(e){toast("err:"+e.message);}finally{btn.textContent="SEND";btn.disabled=false;}}
async function load(){const x=document.getElementById("cat").value,l=document.getElementById("list");l.innerHTML='<div class="loading">...</div>';try{const[r,f]=await Promise.all([fetch(A+"/records?category="+x),fetch(A+"/files?category="+x)]);const rs=await r.json(),fs=await f.json();if(rs.length===0&&fs.length===0){l.innerHTML='<div class="loading">empty</div>';return;}let h='<div class="records">';rs.forEach(r=>{const m=r.content&&(r.content.includes("#")||r.content.includes("**"));h+='<div class="record"><div class="record-header"><span class="record-cat">'+r.category+'</span><span>'+new Date(r.created_at).toLocaleString()+'</span></div><div class="record-content">'+(m?DOMPurify.sanitize(marked.parse(r.content)):r.content)+'</div></div>';});fs.forEach(f=>{h+='<div class="record"><div class="record-header"><span class="record-cat">'+f.category+'</span><span>'+f.original_name+'</span><span>'+(f.file_size/1024).toFixed(1)+'KB</span></div></div>';});l.innerHTML=h+'</div>';}catch(e){l.innerHTML='<div class="loading">failed</div>';}}
function toast(m){const t=document.getElementById("toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2000);}
</script>
</body>
</html>
"""

sftp = client.open_sftp()
sftp.open('/opt/mycloud/static/index.html', 'w').write(html.encode('utf-8'))
sftp.close()
print("HTML uploaded")

# Also fix the main.py - need to correct webdav upload
main_py = """import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse
import aiosqlite
import webdav3.client as wc
import io

app = FastAPI(title="MyCloud")

DB_PATH = "/opt/mycloud/mycloud.db"
WEBDAV_URL = "http://localhost:19800/dav"
WEBDAV_USER = "cd2baidu"
WEBDAV_PASS = "xdxis1234"
CATEGORIES = ["stock", "life", "funny"]

def get_client():
    return wc.Client({
        "webdav_hostname": WEBDAV_URL,
        "webdav_login": WEBDAV_USER,
        "webdav_password": WEBDAV_PASS
    })

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL,
            category TEXT NOT NULL, title TEXT, content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
            original_name TEXT NOT NULL, stored_name TEXT NOT NULL,
            webdav_path TEXT NOT NULL, file_size INTEGER, mime_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        await db.commit()
        try:
            client = get_client()
            for cat in CATEGORIES:
                if not client.check(cat):
                    client.mkdir(cat)
            if not client.check("backup"):
                client.mkdir("backup")
        except Exception as e:
            print(f"WebDAV init error: {e}")

@app.post("/api/records")
async def create_record(data: dict):
    if data["category"] not in CATEGORIES:
        raise HTTPException(400, "Invalid category")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO records (type, category, title, content) VALUES (?, ?, ?, ?)",
            (data["type"], data["category"], data.get("title"), data["content"]))
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        row_id = await cur.fetchone()
    return {"id": row_id[0], "status": "ok"}

@app.post("/api/files")
async def upload_file(category: str = Form(...), file: UploadFile = Form(...)):
    if category not in CATEGORIES:
        raise HTTPException(400, "Invalid category")
    ext = Path(file.filename).suffix or ""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    webdav_path = f"{category}/{stored_name}"
    content = await file.read()
    try:
        client = get_client()
        client.upload(webdav_path, io.BytesIO(content))
    except Exception as e:
        raise HTTPException(500, f"WebDAV error: {e}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO files (category, original_name, stored_name, webdav_path, file_size, mime_type) VALUES (?, ?, ?, ?, ?, ?)",
            (category, file.filename, stored_name, webdav_path, len(content), file.content_type))
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        row_id = await cur.fetchone()
    return {"id": row_id[0], "path": webdav_path, "status": "ok"}

@app.get("/api/records")
async def get_records(category: Optional[str] = None, limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            cur = await db.execute("SELECT * FROM records WHERE category=? ORDER BY created_at DESC LIMIT ?", (category, limit))
        else:
            cur = await db.execute("SELECT * FROM records ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/files")
async def get_files(category: Optional[str] = None, limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            cur = await db.execute("SELECT * FROM files WHERE category=? ORDER BY created_at DESC LIMIT ?", (category, limit))
        else:
            cur = await db.execute("SELECT * FROM files ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/categories")
async def get_categories():
    return CATEGORIES

@app.post("/api/backup")
async def backup_db():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM records")
        records = await cur.fetchall()
        cur = await db.execute("SELECT * FROM files")
        files = await cur.fetchall()
    backup = {"backup_at": datetime.now().isoformat(), "records": [dict(r) for r in records], "files": [dict(f) for f in files]}
    backup_name = f"backup/records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        client = get_client()
        client.upload(backup_name, io.BytesIO(json.dumps(backup, ensure_ascii=False, indent=2).encode("utf-8")))
    except Exception as e:
        raise HTTPException(500, f"WebDAV error: {e}")
    return {"status": "ok", "path": backup_name}

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("/opt/mycloud/static/index.html", "r", encoding="utf-8").read()

@app.on_event("startup")
async def startup():
    await init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
"""

sftp.open('/opt/mycloud/app/main.py', 'w').write(main_py.encode('utf-8'))
sftp.close()
print("main.py uploaded")

# Install requirements
stdin, stdout, stderr = client.exec_command('cd /opt/mycloud && pip install -r requirements.txt 2>&1 | tail -5')
print("Requirements:", stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace'))

# Start the app
stdin, stdout, stderr = client.exec_command('cd /opt/mycloud && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > /tmp/mycloud.log 2>&1 &')
print("Start:", stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace'))

# Check if running
stdin, stdout, stderr = client.exec_command('sleep 3 && ps aux | grep uvicorn | grep -v grep')
print("Status:", stdout.read().decode('utf-8', errors='replace'))

client.close()
print("Done!")
