"""单独对指定 msg_id 重新执行 LLM extract（使用当前 prompt），验证分类结果。

用法:
    python scripts/re_extract_msg.py 49358
"""
import sys, os, json, sqlite3
from datetime import datetime, timezone, timedelta

# --- paths ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from prompts.loader import load_prompt
from prompts.schemas import LLMInput, InputItem

DB = os.path.join(ROOT, "data", "preprocess.db")
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-c5a451bf49e14da4929a0fc722242e13")
MODEL = "qwen3.5-flash"


def main():
    if len(sys.argv) < 2:
        print("用法: python re_extract_msg.py <msg_id>")
        sys.exit(1)

    msg_id = int(sys.argv[1])

    # 1. 读消息
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT id, ts, kind, content FROM messages WHERE id = ?", (msg_id,)
    ).fetchone()
    con.close()

    if row is None:
        print(f"msg_id={msg_id} 不存在于 messages 表")
        sys.exit(1)

    mid, ts, kind, text = row
    print(f"[{mid}] ts={ts} kind={kind}")
    print(f"content (first 300 chars): {text[:300]!r}")

    # 2. 构造 LLMInput
    items = [InputItem(idx=1, ts=ts, text=text, orig_len=len(text))]
    payload = LLMInput(count=1, items=items)

    # 3. 加载当前 prompt
    system, user, fm = load_prompt("historical", payload)
    print(f"\n[prompt] mode=historical model={fm.get('model')}")
    print(f"[prompt] system chars={len(system)}, user chars={len(user)}")

    # 4. 调用 LLM
    from openai import OpenAI
    client = OpenAI(api_key=DASHSCOPE_KEY, base_url=DASHSCOPE_BASE)
    resp = client.chat.completions.create(
        model=fm["model"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        extra_body={"enable_thinking": False},
    )
    raw = resp.choices[0].message.content or ""
    print(f"\n[llm raw output]:\n{raw}")

    # 5. 解析并展示
    from prompts.schemas import LLMOutput
    result = LLMOutput.model_validate_json(raw)
    for r in result.results:
        print(f"\n[result] task_id={r.task_id}")
        print(f"  info_type: {r.info_type}")
        print(f"  category:  {r.category}")
        print(f"  stocks:    {r.involved_stocks}")
        print(f"  terms:     {r.core_tech_terms}")
        print(f"  summary:   {r.summary}")


if __name__ == "__main__":
    main()
