import os, json, uuid, io, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import jwt
import requests
from requests.auth import HTTPBasicAuth
from fastapi import FastAPI, UploadFile, Form, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
import aiosqlite

app = FastAPI(title="MyCloud")

DB_PATH = "/opt/mycloud/mycloud.db"
WEBDAV_URL = "http://localhost:19800/dav"
WEBDAV_USER = "cd2baidu"
WEBDAV_PASS = "xdxis1234"
CATEGORIES = ["stock", "life", "funny"]
JWT_SECRET = "mycloud_secret_key_2026"
JWT_EXPIRE_HOURS = 24 * 30

def make_token(username):
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def wd_upload(path, data):
    url = f"{WEBDAV_URL}/{path}"
    r = requests.put(url, data=data, auth=HTTPBasicAuth(WEBDAV_USER, WEBDAV_PASS))
    if r.status_code not in (200, 201, 204):
        raise Exception(f"WebDAV error: {r.status_code}")

def wd_mkdir(path):
    url = f"{WEBDAV_URL}/{path}"
    r = requests.request("MKCOL", url, auth=HTTPBasicAuth(WEBDAV_USER, WEBDAV_PASS))
    if r.status_code not in (200, 201, 204, 405):
        raise Exception(f"WebDAV mkdir error: {r.status_code}")

def wd_exists(path):
    url = f"{WEBDAV_URL}/{path}"
    r = requests.head(url, auth=HTTPBasicAuth(WEBDAV_USER, WEBDAV_PASS))
    return r.status_code == 200

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
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
        cur = await db.execute("SELECT id FROM users WHERE username='admin'")
        if not await cur.fetchone():
            await db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                ("admin", hash_password("admin123")))
            await db.commit()
        try:
            for cat in CATEGORIES:
                if not wd_exists(cat):
                    wd_mkdir(cat)
            if not wd_exists("backup"):
                wd_mkdir("backup")
        except Exception as e:
            print(f"WebDAV init error: {e}")

@app.post("/api/login")
async def login(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        raise HTTPException(400, "Username and password required")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE username=?", (username,))
        user = await cur.fetchone()
    if not user or user["password"] != hash_password(password):
        raise HTTPException(401, "Invalid credentials")
    token = make_token(username)
    return {"token": token, "username": username}

@app.post("/api/records")
async def create_record(data: dict, username: str = Depends(verify_token)):
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
async def upload_file(category: str = Form(...), file: UploadFile = Form(...), username: str = Depends(verify_token)):
    if category not in CATEGORIES:
        raise HTTPException(400, "Invalid category")
    ext = Path(file.filename).suffix or ""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    webdav_path = f"{category}/{stored_name}"
    content = await file.read()
    try:
        wd_upload(webdav_path, content)
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
async def get_records(category: Optional[str] = None, limit: int = 100, username: str = Depends(verify_token)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            cur = await db.execute("SELECT * FROM records WHERE category=? ORDER BY created_at DESC LIMIT ?", (category, limit))
        else:
            cur = await db.execute("SELECT * FROM records ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/files")
async def get_files(category: Optional[str] = None, limit: int = 100, username: str = Depends(verify_token)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            cur = await db.execute("SELECT * FROM files WHERE category=? ORDER BY created_at DESC LIMIT ?", (category, limit))
        else:
            cur = await db.execute("SELECT * FROM files ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/categories")
async def get_categories(username: str = Depends(verify_token)):
    return CATEGORIES

@app.post("/api/backup")
async def backup_db(username: str = Depends(verify_token)):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM records")
        records = await cur.fetchall()
        cur = await db.execute("SELECT * FROM files")
        files = await cur.fetchall()
    backup = {"backup_at": datetime.now().isoformat(), "records": [dict(r) for r in records], "files": [dict(f) for f in files]}
    backup_name = f"backup/records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        wd_upload(backup_name, json.dumps(backup, ensure_ascii=False, indent=2).encode("utf-8"))
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
