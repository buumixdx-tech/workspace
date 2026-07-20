"""feishu_to_ima_upload_to_ima: 把 TXT 文件上传到 IMA "Stock" KB.

5 步链 (跟 ima-skill 一致):
  0. check_repeated_name  ← 一次性拉全量 KB title, 内存查重 (防止撞名)
  1. create_media           ← 拿 media_id + cos_credential (临时凭证)
  2. COS PUT                ← 用 cos_credential 拼 SHA1 签名, 上传 TXT 到腾讯云 COS
  3. add_knowledge          ← 写进 KB
  4. mark_ima_posted        ← 写本地 db

设计 (2026-06-22 拍板, 2026-07-16 优化):
  - 直接 fetch ima.qq.com OpenAPI, 不走 subprocess
  - 凭证/KB_ID 走 ima_config (集中), 不再读 secrets/feishu_to_ima.env (长期缺失)
  - COS 上传: 复现 ima-skill/knowledge-base/scripts/cos-upload.cjs 的 SHA1 签名算法
    (https://cloud.tencent.com/document/product/436/7778)
  - 查重: upload_to_ima 入口一次性拉 KB 全部 title, upload_one_txt 内存 set 查 (不再每文件翻页)
  - retry: 限流 (429/200001) + 服务器错误 (500/502/503) 走 exp-backoff 5 次, 间隔 5/10/20/40/80s
  - 串行上传 (1 并发), 避免触发 IMA 限速
  - DRY RUN 默认, --real 才真传 (本模块 main() 仍交互确认)
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp

# ---------------------------------------------------------------------------
# 路径 + 凭证 (集中到 ima_config)
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feishu_to_ima_db_writer import (
    connect, get_ima_posted_msg_ids,
    mark_ima_posted, FEISHU_TO_IMA_DB, IMA_TXT_DIR,
    DATA_DIR,
)
from ima_config import (
    IMA_CLIENT_ID, IMA_API_KEY, IMA_KB_ID,
    IMA_BASE_URL, IMA_SKILL_VERSION, IMA_MEDIA_TYPE_TXT,
)

# 限流 + 服务器错误, 都走 exp-backoff 重试 (命名按真实语义: 可重试, 不止限流)
RETRYABLE_CODES = (429, 500, 502, 503, 200001)


# ---------------------------------------------------------------------------
# 腾讯云 COS 上传 (复现 ima-skill cos-upload.cjs 的 SHA1 签名)
# ---------------------------------------------------------------------------
def hmac_sha1(key: bytes, data: str) -> str:
    return hmac.new(key, data.encode("utf-8"), hashlib.sha1).hexdigest()


def sha1(data: str) -> str:
    return hashlib.sha1(data.encode("utf-8")).hexdigest()


def build_cos_authorization(*, secret_id: str, secret_key: str, method: str,
                            pathname: str, headers: dict,
                            start_time: str, expired_time: str) -> str:
    """构造腾讯云 COS PUT Authorization 头.

    参考: https://cloud.tencent.com/document/product/436/7778
    复现 ima-skill/cos-upload.cjs 的 buildAuthorization().
    """
    key_time = f"{start_time};{expired_time}"
    sign_key = hmac_sha1(secret_key.encode("utf-8"), key_time)

    header_keys = sorted(headers.keys())
    http_headers = "&".join(
        f"{k.lower()}={quote(str(headers[k]), safe='')}" for k in header_keys
    ).strip()
    http_string = f"{method.lower()}\n{pathname}\n\n{http_headers}\n"

    string_to_sign = f"sha1\n{key_time}\n{sha1(http_string)}\n"
    signature = hmac_sha1(sign_key.encode("utf-8"), string_to_sign)

    header_list = ";".join(k.lower() for k in header_keys)
    return "&".join([
        "q-sign-algorithm=sha1",
        f"q-ak={secret_id}",
        f"q-sign-time={key_time}",
        f"q-key-time={key_time}",
        f"q-header-list={header_list}",
        "q-url-param-list=",
        f"q-signature={signature}",
    ])


async def cos_put(*, session: aiohttp.ClientSession, cred: dict, cos_key: str,
                  content: bytes, content_type: str = "text/plain",
                  timeout_sec: int = 300) -> int:
    """上传到腾讯云 COS, 返回 HTTP status. 复用调用方传入的 session (连接池).

    cred 来自 create_media.data.cos_credential:
      {token, secret_id, secret_key, start_time, expired_time,
       appid, bucket_name, region, custom_domain, cos_key}
    """
    bucket = cred["bucket_name"]
    region = cred["region"]
    secret_id = cred["secret_id"]
    secret_key = cred["secret_key"]
    token = cred["token"]
    start_time = cred.get("start_time") or str(int(time.time()))
    expired_time = cred.get("expired_time") or str(int(time.time()) + 3600)

    hostname = f"{bucket}.cos.{region}.myqcloud.com"
    pathname = f"/{cos_key}"

    sign_headers = {
        "content-length": str(len(content)),
        "host": hostname,
    }
    authorization = build_cos_authorization(
        secret_id=secret_id,
        secret_key=secret_key,
        method="PUT",
        pathname=pathname,
        headers=sign_headers,
        start_time=start_time,
        expired_time=expired_time,
    )

    url = f"https://{hostname}{pathname}"
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(content)),
        "Authorization": authorization,
        "x-cos-security-token": token,
    }
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    async with session.put(url, data=content, headers=headers, timeout=timeout) as resp:
        text = await resp.text()
        if resp.status not in (200, 204):
            raise RuntimeError(f"COS PUT HTTP {resp.status}: {text[:300]}")
        return resp.status


# ---------------------------------------------------------------------------
# 调 OpenAPI
# ---------------------------------------------------------------------------
async def ima_api(session: aiohttp.ClientSession, api_path: str, body: dict) -> dict:
    """POST IMA OpenAPI. 返回响应 dict (含 code).

    body 合法 JSON 时用其 code; body 非法时用 HTTP status 当 code
    (这样 429/5xx 返回非 JSON 也能被 RETRYABLE_CODES 命中重试).
    """
    url = f"{IMA_BASE_URL}/{api_path}"
    headers = {
        "ima-openapi-clientid": IMA_CLIENT_ID,
        "ima-openapi-apikey": IMA_API_KEY,
        "ima-openapi-ctx": f"skill_version={IMA_SKILL_VERSION}",
        "Content-Type": "application/json",
    }
    async with session.post(url, json=body, headers=headers) as resp:
        text = await resp.text()
        try:
            r = json.loads(text)
            if not isinstance(r, dict):
                return {"code": resp.status, "msg": f"non-dict JSON: {text[:200]}"}
            return r
        except json.JSONDecodeError:
            return {"code": resp.status, "msg": f"non-JSON response (HTTP {resp.status}): {text[:200]}"}


def make_md5(file_path: Path) -> str:
    h = hashlib.md5()
    h.update(file_path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 一次性拉 KB 全部 title (查重用, 替代每文件翻页)
# ---------------------------------------------------------------------------
async def fetch_all_kb_titles(
    session: aiohttp.ClientSession,
    kb_id: str = IMA_KB_ID,
) -> dict[str, str]:
    """翻页拉 KB 全部条目. 返回 {title: media_id}.

    失败 (网络/限流) 返回 {} 并 warn - 调用方会放行所有 (等同不查重), 不阻断上传.
    限速: 200ms/页, 上限 50 页防卡死.
    """
    titles: dict[str, str] = {}
    cursor = ""
    page = 0
    while True:
        page += 1
        try:
            r = await ima_api(
                session,
                "openapi/wiki/v1/get_knowledge_list",
                {"knowledge_base_id": kb_id, "cursor": cursor, "limit": 50},
            )
        except Exception as e:
            print(f"    [warn] fetch_all_kb_titles 第 {page} 页异常: {e}, 已收 {len(titles)} 条, 放行查重")
            return titles

        if r.get("code") != 0:
            print(f"    [warn] fetch_all_kb_titles 第 {page} 页 code={r.get('code')} msg={r.get('msg')}, 放行查重")
            return titles

        data = r.get("data") or {}
        for item in (data.get("knowledge_list") or []):
            t = item.get("title")
            if t:
                titles[t] = item.get("media_id", "")
        cursor = data.get("next_cursor") or ""
        if data.get("is_end") or not cursor:
            break
        if page > 50:
            print(f"    [warn] fetch_all_kb_titles 超 50 页, 截断 (已收 {len(titles)} 条)")
            break
        await asyncio.sleep(0.2)

    return titles


# ---------------------------------------------------------------------------
# 单文件上传: 5 步链
# ---------------------------------------------------------------------------
async def upload_one_txt(
    session: aiohttp.ClientSession,
    txt_path: Path,
    txt_filename: str,
    msg_ids: list[int],
    existing_titles: dict[str, str],
    max_retries: int = 5,
) -> dict:
    """上传一个 TXT 文件, 5 步链:
      0. 内存查重 (existing_titles)  ← 一次性拉的全量 title set
      1. create_media
      2. cos_put (复用 session)
      3. add_knowledge
      4. mark_ima_posted  (由 upload_to_ima 主循环处理)
    串行, 不并发.
    """
    title = txt_filename
    file_size = txt_path.stat().st_size
    md5 = make_md5(txt_path)

    # 节流: 每个 doc 上传前 sleep 0.5s
    await asyncio.sleep(0.5)

    # 0. 内存查重 (防止撞名)
    if title in existing_titles:
        return {
            "ok": False,
            "step": "check_repeated_name",
            "error": f"IMA KB 已存在同名 title='{title}', media_id={existing_titles[title]}",
            "existing_media_id": existing_titles[title],
            "txt": txt_filename,
        }

    # 1. create_media
    payload_step1 = {
        "knowledge_base_id": IMA_KB_ID,
        "media_type": IMA_MEDIA_TYPE_TXT,
        "file_name": title,
        "title": title,
        "content_type": "text/plain",
        "size": file_size,
        "md5": md5,
    }
    media_id = None
    cos_credential = None
    cos_key = None
    for attempt in range(max_retries):
        try:
            r1 = await ima_api(session, "openapi/wiki/v1/create_media", payload_step1)
            if r1.get("code") == 0:
                media_id = r1["data"]["media_id"]
                cos_credential = r1["data"].get("cos_credential")
                # cos_key 可能在外层 data 或 cos_credential 里 (跟 skill 保持一致)
                cos_key = r1["data"].get("cos_key") or (cos_credential or {}).get("cos_key")
                break
            elif r1.get("code") in RETRYABLE_CODES:
                wait = 5 * (2 ** attempt)
                print(f"    [retry {attempt+1}/{max_retries}] create_media retryable (code={r1.get('code')}), 等 {wait}s")
                await asyncio.sleep(wait)
            else:
                return {"ok": False, "step": "create_media", "error": r1, "txt": txt_filename}
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            else:
                return {"ok": False, "step": "create_media", "error": str(e), "txt": txt_filename}
    else:
        return {"ok": False, "step": "create_media", "error": "max retries", "txt": txt_filename}

    if not cos_credential or not cos_key:
        return {"ok": False, "step": "create_media",
                "error": "missing cos_credential or cos_key in response", "txt": txt_filename}

    # 2. COS PUT (用 cos_credential 临时凭证 + 自签 SHA1, 复用 session)
    for attempt in range(max_retries):
        try:
            content = txt_path.read_bytes()
            await cos_put(session=session, cred=cos_credential, cos_key=cos_key,
                          content=content, content_type="text/plain")
            break
        except Exception as e:
            msg = str(e).lower()
            if "limit" in msg or "429" in msg or " 500" in msg or " 502" in msg or " 503" in msg:
                wait = 5 * (2 ** attempt)
                print(f"    [retry {attempt+1}/{max_retries}] cos_put retryable, 等 {wait}s")
                await asyncio.sleep(wait)
            elif attempt < max_retries - 1:
                await asyncio.sleep(1)
            else:
                return {"ok": False, "step": "cos_put", "error": str(e), "txt": txt_filename}
    else:
        return {"ok": False, "step": "cos_put", "error": "max retries", "txt": txt_filename}

    # 3. add_knowledge
    # 必填字段 (api.md 208-216): media_type, title, knowledge_base_id
    # 文件上传还要: media_id + file_info (FileInfo 包含 cos_key/file_size/last_modify_time/file_name)
    last_modify_time = int(txt_path.stat().st_mtime)
    payload_step3 = {
        "knowledge_base_id": IMA_KB_ID,
        "media_type": IMA_MEDIA_TYPE_TXT,
        "media_id": media_id,
        "title": title,
        "file_info": {
            "cos_key": cos_key,
            "file_size": file_size,
            "last_modify_time": last_modify_time,
            "file_name": title,
        },
    }
    for attempt in range(max_retries):
        try:
            r3 = await ima_api(session, "openapi/wiki/v1/add_knowledge", payload_step3)
            if r3.get("code") == 0:
                return {"ok": True, "media_id": media_id, "msg_ids": msg_ids, "txt": txt_filename}
            elif r3.get("code") in RETRYABLE_CODES:
                wait = 5 * (2 ** attempt)
                print(f"    [retry {attempt+1}/{max_retries}] add_knowledge retryable (code={r3.get('code')}), 等 {wait}s")
                await asyncio.sleep(wait)
            else:
                return {"ok": False, "step": "add_knowledge", "error": r3, "txt": txt_filename}
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            else:
                return {"ok": False, "step": "add_knowledge", "error": str(e), "txt": txt_filename}
    return {"ok": False, "step": "add_knowledge", "error": "max retries", "txt": txt_filename}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
async def upload_to_ima(max_concurrent: int = 1) -> dict:
    """拿所有 txt_bucket 表里未上传的, 逐个上传.

    max_concurrent=1 串行 (避开 IMA 限速). 实际 IMA 限速很高, 不要调高.
    查重: 入口一次性拉 KB 全量 title, 每个文件内存查; 上传成功后增量加入.
    """
    con = connect()
    try:
        already_posted = get_ima_posted_msg_ids(con)

        rows = con.execute("""
            SELECT txt_filename, doc_count, msg_ids_json
            FROM txt_bucket
            WHERE posted_at IS NULL OR posted_at = ''
            ORDER BY txt_filename ASC
        """).fetchall()
        print(f"[upload] 待上传 TXT: {len(rows)} 个 (max_concurrent={max_concurrent})")
        if not rows:
            return {"uploaded": 0, "skipped": 0, "failed": 0, "repeated": 0}

        uploaded = 0
        skipped = 0
        failed = 0
        repeated = 0  # 查重命中同名, 跳过
        sem = asyncio.Semaphore(max_concurrent)

        async with aiohttp.ClientSession() as session:
            # 一次性拉 KB 全量 title (查重用), 失败则空 dict -> 放行所有
            print("[upload] 拉 KB 全量 title 做查重...")
            existing_titles = await fetch_all_kb_titles(session)
            print(f"[upload] KB 已有 title: {len(existing_titles)} 个")

            async def _upload_one(txt_filename, doc_count, msg_ids_json):
                nonlocal uploaded, skipped, failed, repeated
                msg_ids = json.loads(msg_ids_json)

                # 二次检查
                if all(mid in already_posted for mid in msg_ids):
                    mark_ima_posted(con, txt_filename, "EXISTING", IMA_KB_ID)
                    skipped += 1
                    print(f"  [skip] {txt_filename}: all {doc_count} msg_ids already in IMA")
                    return

                txt_path = IMA_TXT_DIR / txt_filename
                if not txt_path.exists():
                    print(f"  [WARN] {txt_filename} 物理文件缺失, 跳过")
                    failed += 1
                    return

                print(f"  [upload] {txt_filename} ({doc_count} msg_ids, {txt_path.stat().st_size} bytes)")
                async with sem:
                    r = await upload_one_txt(session, txt_path, txt_filename, msg_ids, existing_titles)
                if r["ok"]:
                    mark_ima_posted(con, txt_filename,
                                    r.get("media_id", "?"), IMA_KB_ID)
                    # 增量加入, 防同批重复上传同名
                    existing_titles[txt_filename] = r.get("media_id", "?")
                    uploaded += 1
                    print(f"  [ok] {txt_filename} -> media_id={r.get('media_id', '?')[:20]}...")
                elif r.get("step") == "check_repeated_name":
                    # IMA KB 已有同名, 跳过本次上传 (不重传, 不重命名, 让用户决定怎么处理)
                    repeated += 1
                    mid = r.get('existing_media_id') or '?'
                    print(f"  [repeated] {txt_filename}: IMA KB 已存在同名, mid={mid[:20]}...")
                else:
                    print(f"  [FAIL] {r.get('txt')}: {r.get('error')}")
                    failed += 1

            tasks = [_upload_one(fn, dc, mj) for fn, dc, mj in rows]
            await asyncio.gather(*tasks)

        con.commit()
        return {"uploaded": uploaded, "skipped": skipped, "failed": failed, "repeated": repeated}
    finally:
        con.close()


def main():
    print(f"=== feishu_to_ima upload_to_ima ===\n")
    print(f"IMA_BASE_URL: {IMA_BASE_URL}")
    print(f"IMA_KB_ID: {IMA_KB_ID}")
    print(f"ClientID loaded: {bool(IMA_CLIENT_ID)}")
    print(f"APIKey loaded: {bool(IMA_API_KEY)}")
    print(f"ima_txt 目录: {IMA_TXT_DIR}\n")

    confirm = input(">>> 这将真传 IMA, 确认? (y/N): ")
    if confirm.lower() != "y":
        print("取消")
        return

    stats = asyncio.run(upload_to_ima())
    print()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
