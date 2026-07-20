#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重写窗口内第一条 (msg_id=49947 长鑫存储 30亿美元) — 用 v4 prompt 跑"""
import sys, os, json, datetime, sqlite3
# 2026-07-04 迁移: 路径更新
sys.path.insert(0, r"D:\WorkSpace\Trading\Recourse\feishu_ext")

# 拿原文
# 2026-07-04 迁移: 路径更新
con = sqlite3.connect(r"D:\WorkSpace\Trading\Recourse\feishu_ext\data\preprocess.db")
old = con.execute("SELECT summary, info_type FROM extracted WHERE msg_id=49947").fetchone()
text = con.execute("SELECT content FROM messages WHERE id=49947").fetchone()[0]
ts = con.execute("SELECT ts FROM messages WHERE id=49947").fetchone()[0]
con.close()

TZ = datetime.timezone(datetime.timedelta(hours=8))
dt = datetime.datetime.fromtimestamp(ts/1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
print("=" * 70)
print(f"msg_id=49947  {dt}  orig_len={len(text)}  old_info_type={old[1]}")
print("=" * 70)
print("OLD summary (v3):")
print(f"  [{old[0]}]  (len={len(old[0])})")
print()
print("ORIGINAL:")
print(text)
print()

# 跑 v4 prompt
from prompts.schemas import LLMInput, InputItem
from prompts.loader import load_prompt

item = InputItem(idx=1, ts=ts, text=text, orig_len=len(text))
payload = LLMInput(count=1, items=[item])
system, user, fm = load_prompt("historical", payload)
print(f"--- v4 prompt (frontmatter version={fm.get('version')}) ---")
print(f"system chars: {len(system)}, user chars: {len(user)}")
print()

# 调 LLM
os.environ["DASHSCOPE_API_KEY"] = "sk-c5a451bf49e14da4929a0fc722242e13"
from openai import OpenAI
client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
resp = client.chat.completions.create(
    model="qwen3.5-flash",
    messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ],
    response_format={"type": "json_object"},
    temperature=0.0,
    extra_body={"enable_thinking": False},
)
content = resp.choices[0].message.content
data = json.loads(content)
r = data["results"][0]
print("=" * 70)
print("v4 OUTPUT:")
print(f"  info_type: {r['info_type']}")
print(f"  category: [{r.get('category','')}]")
print(f"  involved_stocks: {r.get('involved_stocks',[])}")
print(f"  core_tech_terms: {r.get('core_tech_terms',[])}")
print(f"  summary: [{r['summary']}]  (len={len(r['summary'])})")
print("=" * 70)

# 末尾标点检查 (完整句)
last_char = r['summary'].rstrip()[-1] if r['summary'] else ''
complete = last_char in "。;!?…"
print(f"\n末尾标点: '{last_char}'  完整句: {'[OK]' if complete else '[WARN 看起来被截]'}")
print(f"长度: 旧={len(old[0])} → 新={len(r['summary'])}")

# 关键信息保留度 (原文核心关键词)
kw = ["长鑫存储", "腾讯", "30亿", "DRAM"]
missing = [k for k in kw if k not in r['summary'] and not any(part in r['summary'] for part in [k[:2]])]
print(f"\n关键实体保留:")
for k in kw:
    print(f"  {k}: {'[OK]' if k in r['summary'] else '[MISS]'}")
print(f"missing: {missing}")