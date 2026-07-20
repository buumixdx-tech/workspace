"""
query_ima.py — 批量从 IMA 知识库查询公司简介
用法: python query_ima.py
读取 gm.xlsx 的 B列(name) → 逐个查 IMA → 结果写入 R 列(第18列)
"""

import json
import os
import subprocess
import sys
import time
import random
import pandas as pd

# ── IMA 配置 ────────────────────────────────────────────────────────────────
IMA_SKILL_DIR = os.path.join(os.path.dirname(__file__), ".claude", "skills", "ima-skill")
IMA_API_CJS  = os.path.join(IMA_SKILL_DIR, "ima_api.cjs")
IMA_CFG_DIR  = os.path.join(os.path.expanduser("~"), ".config", "ima")
KB_ID        = "hCx6uC-_z2qJOV0ieth8TCLb5wbWT8gZoVh7UIAmnos="

SKILL_VERSION = "1.1.7"


def load_ima_credentials() -> dict:
    """加载 IMA 凭证"""
    client_id = None
    api_key   = None
    # 环境变量优先
    client_id = os.environ.get("IMA_OPENAPI_CLIENTID") or os.environ.get("IMA_CLIENT_ID")
    api_key   = os.environ.get("IMA_OPENAPI_APIKEY")   or os.environ.get("IMA_API_KEY")
    if client_id and api_key:
        return {"clientId": client_id, "apiKey": api_key}
    # 读配置文件
    cfg_dir = os.environ.get("IMA_HOME", IMA_CFG_DIR)
    client_id_path = os.path.join(cfg_dir, "client_id")
    api_key_path   = os.path.join(cfg_dir, "api_key")
    if os.path.exists(client_id_path):
        with open(client_id_path, encoding="utf-8") as f:
            client_id = f.read().strip()
    if os.path.exists(api_key_path):
        with open(api_key_path, encoding="utf-8") as f:
            api_key = f.read().strip()
    if not client_id or not api_key:
        raise RuntimeError("IMA 凭证未找到，请检查 ~/.config/ima/ 或环境变量")
    return {"clientId": client_id, "apiKey": api_key}


def ima_api(api_path: str, body: dict, cred: dict) -> dict:
    """调用 IMA OpenAPI"""
    opts_json = json.dumps(cred, ensure_ascii=False)
    # 构造命令行参数（JSON 转义）
    cmd = [
        "node", IMA_API_CJS,
        api_path,
        json.dumps(body, ensure_ascii=False),
        opts_json,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"code": -1, "msg": "API 调用超时"}
    except Exception as e:
        return {"code": -1, "msg": str(e)}

    # stderr 有结构化错误
    if result.returncode != 0:
        try:
            err = json.loads(result.stderr.strip())
            return err
        except Exception:
            return {"code": -100, "msg": result.stderr.strip()[:200]}

    # stdout 是 JSON 响应
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"code": -1, "msg": f"非 JSON 响应: {result.stdout[:200]}"}


def search_kb(query: str, cred: dict, limit: int = 5) -> list:
    """搜索 IMA 知识库，返回匹配条目列表"""
    body = {
        "knowledge_base_id": KB_ID,
        "query": query,
        "limit": limit,
    }
    r = ima_api("openapi/wiki/v1/search_knowledge", body, cred)
    if r.get("code") != 0:
        return []
    data = r.get("data") or {}
    return data.get("knowledge_list", [])


def get_media_info(media_id: str, cred: dict) -> dict:
    """获取知识库条目的媒体信息"""
    r = ima_api("openapi/wiki/v1/get_media_info", {
        "knowledge_base_id": KB_ID,
        "media_id": media_id,
    }, cred)
    if r.get("code") != 0:
        return {}
    return r.get("data", {})


def get_doc_content(media_id: str, cred: dict) -> str:
    """获取笔记类型媒体的正文内容"""
    r = ima_api("openapi/doc/v1/get_doc_content", {
        "media_id": media_id,
    }, cred)
    if r.get("code") != 0:
        return ""
    data = r.get("data") or {}
    return data.get("content", "")


def query_company(company_name: str, cred: dict) -> str:
    """
    查询公司信息，返回简介文本。
    策略：在 KB 中搜索公司名称，取相关性最高的条目。
    如果是笔记类型(media_type=11)，尝试获取正文。
    """
    results = search_kb(company_name, cred, limit=3)
    if not results:
        return "没有"

    # 取第一条（相关性最高）
    best = results[0]
    title   = best.get("title", "")
    media_id = best.get("media_id", "")
    media_type = best.get("media_type", 0)

    # 简单判断：标题明显不相关则跳过
    skip_words = ["ST", "退市", "公告", "年报", "半年报", "季报", "招股"]
    if any(w in title for w in skip_words):
        # 看第二条
        if len(results) > 1:
            best = results[1]
            title = best.get("title", "")
            media_id = best.get("media_id", "")
            media_type = best.get("media_type", 0)
            if any(w in title for w in skip_words):
                return "没有"
        else:
            return "没有"

    # 如果是笔记类型，获取正文
    if media_type == 11 and media_id:
        content = get_doc_content(media_id, cred)
        if content:
            # 截取前 600 字作为简介
            return content[:600].strip()

    # 否则用标题+摘要
    summary = best.get("summary", "") or best.get("content", "") or ""
    if summary:
        return summary[:600].strip()

    return f"标题：{title}"


# ── 主流程 ────────────────────────────────────────────────────────────────
def main():
    xlsx_path = os.path.join(os.path.dirname(__file__), "gm.xlsx")
    out_path  = os.path.join(os.path.dirname(__file__), "gm_output.xlsx")

    print("读取 gm.xlsx ...")
    df = pd.read_excel(xlsx_path)
    print(f"  共 {len(df)} 行, 列数: {len(df.columns)}")

    # 列名可能有编码问题，用位置取 B 列（第2列，index=1）
    name_col = df.columns[1]   # B 列
    print(f"  股票名称列: {name_col}")

    # 初始化 R 列（如果没有）
    r_col = "查询结果"
    while r_col in df.columns:
        r_col = "_" + r_col
    df[r_col] = ""

    # 加载 IMA 凭证
    print("加载 IMA 凭证 ...")
    cred = load_ima_credentials()
    print(f"  ClientID: {cred['clientId'][:8]}...")

    total = len(df)
    for i, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name == "nan":
            continue

        current = df.at[i, r_col]
        if isinstance(current, str) and current.strip():
            print(f"  [{i+1}/{total}] {name} — 已查询过，跳过")
            continue

        print(f"  [{i+1}/{total}] 查询: {name}", end="", flush=True)
        result = query_company(name, cred)
        df.at[i, r_col] = result

        if result == "没有":
            print(" → 没有")
        else:
            print(f" → 找到 ({len(result)}字)")

        # 节流：避免高频请求
        time.sleep(random.uniform(0.3, 0.8))

    # 保存
    print(f"\n保存到 {out_path} ...")
    df.to_excel(out_path, index=False, engine="openpyxl")
    print("完成！")


if __name__ == "__main__":
    main()
