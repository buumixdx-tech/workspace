# -*- coding: utf-8 -*-
"""build_browser.py — 生成 gm_browser.html（左侧公司列表 + 右侧详情面板）"""
import pandas as pd, os

# ── 读取 xlsx ─────────────────────────────────────────────────────────────
src = os.path.join(os.path.dirname(__file__), "gm.xlsx")
df = pd.read_excel(src)

# 用索引访问（避免列名乱码）
# [0]code [1]name [3]industry_em [7]毛利率_2026Q1 [11]毛利率_2025A [15]毛利率_2024A [16]市值 [17]市值亿元

records = []
for _, row in df.iterrows():
    name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
    if not name:
        continue
    code = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
    industry = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

    def gm(idx):
        v = row.iloc[idx]
        if pd.isna(v) or str(v).strip() in ("", "nan"):
            return "—"
        try:
            return f"{float(v):.1f}%"
        except (ValueError, TypeError):
            return str(v)

    gm26q = gm(7)   # 2026Q1
    gm25a = gm(11)  # 2025A
    gm24a = gm(15)  # 2024A

    mc = str(row.iloc[16]).strip() if pd.notna(row.iloc[16]) else ""

    # code 带前缀
    if code.startswith(("6", "9")):
        code_prefix = "sh." + code
    else:
        code_prefix = "sz." + code

    records.append({
        "name": name,
        "code": code,
        "code_prefix": code_prefix,
        "industry": industry,
        "gm26q": gm26q,
        "gm25a": gm25a,
        "gm24a": gm24a,
        "mc": mc,
    })

print(f"读取 {len(records)} 条记录")

# ── 行业颜色 ────────────────────────────────────────────────────────────
INDUSTRY_COLOR = {
    "半导体": "#FF6B6B",
    "通信设备": "#748AFC",
    "通用设备": "#3D5A80",
    "电力": "#52B788",
    "电子": "#9D4EDD",
    "计算机设备": "#6366f1",
    "IT服务Ⅱ": "#8b5cf6",
    "军工": "#2D3047",
    "环保": "#52796F",
    "消费": "#E07A5F",
    "光通信": "#45B7D1",
    "资源/能源": "#52796F",
    "食品饮料": "#f59e0b",
    "家电": "#f97316",
    "医药": "#10b981",
    "其他": "#888",
}
INDUSTRY_DEFAULT = "#999"

def ind_color(ind):
    for k, c in INDUSTRY_COLOR.items():
        if k in ind:
            return c
    return INDUSTRY_DEFAULT

def ind_bg(ind):
    c = ind_color(ind)
    r, g, b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
    return f"rgba({r},{g},{b},0.12)"

def gm_color(gm_str):
    try:
        v = float(gm_str.replace("%",""))
        if v >= 40: return "#16a34a"
        if v >= 20: return "#d97706"
        return "#dc2626"
    except: return "#888"

# ── 生成 HTML ────────────────────────────────────────────────────────────
JS_DATA = ",\n  ".join(
    f'''{{name:{r["name"]!r}, code:{r["code"]!r}, industry:{r["industry"]!r},
    gm24a:{r["gm24a"]!r}, gm25a:{r["gm25a"]!r}, gm26q:{r["gm26q"]!r},
    gm24_color:{gm_color(r["gm24a"])!r}, gm25_color:{gm_color(r["gm25a"])!r}, mc:{r["mc"]!r}'''
    for r in records
)

# industry chips
from collections import Counter
cnt = Counter(r["industry"] for r in records)
chip_html = f'<span class="chip active" data-g="all">全部 {len(records)}</span>'
for ind, c in sorted(cnt.items(), key=lambda x: -x[1]):
    chip_html += f'<span class="chip" data-g="{ind}">{ind} {c}</span>'

# list items
item_html = ""
for r in records:
    color = ind_color(r["industry"])
    bg = ind_bg(r["industry"])
    tag_html = f'<span class="tag" style="background:{bg};color:{color}">{r["industry"]}</span>'
    gm_c = gm_color(r["gm25a"])
    item_html += f'''<div class="item" data-g="{r["industry"]}" data-code="{r["code"]}" onclick="show(this.dataset.code)">
  <div>
    <div class="item-name">{r["name"]}</div>
    <div class="item-code">{r["code_prefix"]}</div>
    <div class="item-tags">{tag_html}</div>
  </div>
  <div class="item-gm" style="color:{gm_c}">{r["gm25a"]}</div>
</div>'''

# avg stats
gm_vals = []
for r in records:
    try: gm_vals.append(float(r["gm25a"].replace("%","")))
    except: pass
avg_gm = f"{sum(gm_vals)/len(gm_vals):.1f}%" if gm_vals else "—"

HTML = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>高毛利率公司 {len(records)}家</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;overflow:hidden}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f7fa;color:#1a1a2e;display:flex;flex-direction:column}}
header{{background:#1a1a2e;color:#fff;padding:10px 20px;display:flex;align-items:center;gap:12px;flex-shrink:0;font-size:13px}}
header h1{{font-size:15px;font-weight:600;white-space:nowrap;color:#fff}}
.hdr-stats{{margin-left:auto;display:flex;gap:16px;color:rgba(255,255,255,0.55);font-size:12px}}
.hdr-stats strong{{color:#fff}}
.layout{{display:flex;flex:1;overflow:hidden;height:calc(100vh-44px)}}
.sidebar{{width:272px;flex-shrink:0;background:#fff;border-right:1px solid #e4e7eb;display:flex;flex-direction:column;overflow:hidden}}
.s-top{{padding:8px 12px;background:#fafafa;border-bottom:1px solid #f0f1f5;position:sticky;top:0;z-index:2}}
.sbox{{width:100%;padding:6px 10px;border:1px solid #ddd;border-radius:7px;font-size:13px;outline:none;caret-color:#6366f1}}
.sbox:focus{{border-color:#6366f1}}
.chips{{display:flex;flex-wrap:wrap;gap:4px;padding:6px 10px;border-bottom:1px solid #f0f1f5;background:#fafafa;position:sticky;top:38px;z-index:1}}
.chip{{font-size:11px;padding:1px 7px;border-radius:20px;border:1px solid #ddd;cursor:pointer;color:#555;transition:all .15s;white-space:nowrap}}
.chip:hover{{border-color:#6366f1;color:#6366f1}}
.chip.active{{background:#6366f1;border-color:#6366f1;color:#fff}}
.lst{{flex:1;overflow-y:auto}}
.item{{padding:9px 12px;border-bottom:1px solid #f3f4f8;cursor:pointer;display:flex;align-items:center;transition:background .15s}}
.item:hover{{background:#f0f1ff}}
.item.on{{background:#eef0ff;border-left:3px solid #6366f1;padding-left:9px}}
.item-name{{font-size:13px;font-weight:600;color:#1a1a2e}}
.item-code{{font-size:10px;color:#aaa;font-family:ui-monospace}}
.item-tags{{display:flex;gap:3px;margin-top:3px;flex-wrap:wrap}}
.tag{{font-size:10px;padding:1px 5px;border-radius:4px;font-weight:500}}
.item-gm{{margin-left:auto;font-size:12px;font-weight:700;white-space:nowrap}}
.main{{flex:1;overflow-y:auto;background:#f8fafc}}
.empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#c8cdd8;font-size:14px;gap:8px}}
.empty::before{{font-size:22px;content:"👈";display:block;text-align:center}}
.dtl{{padding:20px 28px;max-width:860px}}
.dhdr{{display:flex;align-items:flex-start;gap:16px;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #e4e9f0;flex-wrap:wrap}}
.dname{{font-size:20px;font-weight:700;color:#1a1a2e}}
.dcode{{font-size:12px;color:#999;font-family:ui-monospace;margin-top:3px}}
.dtags{{display:flex;gap:5px;margin-top:8px;flex-wrap:wrap;align-items:center}}
.dpills{{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding-top:4px}}
.dpill{{border:1px solid #e4e9f0;border-radius:8px;padding:6px 12px;text-align:center;background:#fff;min-width:68px}}
.dpill-lbl{{font-size:10px;color:#999}}
.dpill-val{{font-size:15px;font-weight:700;margin-top:2px}}
.sec{{margin-bottom:18px}}
.sec-t{{font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.07em;font-weight:600;margin-bottom:7px;padding-bottom:5px;border-bottom:1px solid #f0f1f5}}
.sec-b{{font-size:14px;line-height:1.85;color:#333}}
.tag{{display:inline-block}}
::-webkit-scrollbar{{width:5px}}::-webkit-scrollbar-thumb{{background:#d4d8e0;border-radius:3px}}
@media(max-width:660px){{.layout{{flex-direction:column;height:auto;overflow:auto}}
.sidebar{{width:100%;max-height:220px;border-right:none;border-bottom:1px solid #e4e7eb;overflow-y:auto}}
.main{{height:calc(100vh-270px);overflow-y:auto}}
.dtl{{padding:14px 16px}}
.dpills{{margin-left:0}}
</style></head>
<body>
<header><h1>高毛利率上市公司</h1><span style="color:rgba(255,255,255,.45);font-size:11px">精选 {len(records)}家</span>
<div class="hdr-stats"><span>均值毛利率 <strong>{avg_gm}</strong></span></div>
</header>
<div class="layout">
<aside class="sidebar">
<div class="s-top"><input class="sbox" placeholder="搜索…" oninput="flt(this.value)"></div>
<div class="chips">{chip_html}</div>
<div class="lst" id="L">{item_html}</div>
</aside>
<main class="main" id="M"><div class="empty">选择左侧公司查看详情</div></main>
</div>
<script>
const D=[{JS_DATA}];
const C=document.getElementById("L"),M=document.getElementById("M");
function show(code){{C.querySelectorAll(".item").forEach(e=>e.classList.toggle("on",e.dataset.code===code));
  const c=D.find(x=>x.code===code)||D[0];if(!c)return;
  M.innerHTML=`<div class=dtl>
<div class=dhdr><div><div class=dname>${{c.name}}<div class=dcode>${{c.code}} · ${{c.industry}}</div><div class=dtags><span class=tag style=background:${{ind_bg(c.industry)}};color:${{ind_color(c.industry)}}>${{c.industry}}</span></div></div>
<div class=dpills><div class=dpill><div class=dpill-lbl>2024年报</div><div class=dpill-val style=color:${{c.gm24_color}}>${{c.gm24a}}</div></div>
<div class=dpill><div class=dpill-lbl>2025年报</div><div class=dpill-val style=color:${{c.gm25_color}}>${{c.gm25a}}</div></div>
<div class=dpill><div class=dpill-lbl>2026一季</div><div class=dpill-val>${{c.gm26q}}</div></div></div></div>
<div class=sec><div class=sec-t>公司概况</div><div class=sec-b>⚠️ 暂无介绍数据<br><br>可结合行业知识和财报数据自行分析，或通过 IMA 知识库查询公司介绍。</div></div></div>`;}}
function flt(q){{q=q.toLowerCase();C.querySelectorAll(".item").forEach(e=>{{const n=e.querySelector(".item-name").textContent.toLowerCase(),c=e.querySelector(".item-code").textContent.toLowerCase();e.style.display=(!q||n.includes(q)||c.includes(q))?"":"none"}})}}
document.querySelectorAll(".chip").forEach(ch=>{{ch.addEventListener("click",()=>{{document.querySelectorAll(".chip").forEach(c=>c.classList.remove("active"));ch.classList.add("active");const g=ch.dataset.g;C.querySelectorAll(".item").forEach(e=>e.style.display=(g==="all"||e.dataset.g===g)?"":"none")}})}});
</script></body></html>'''

out = os.path.join(os.path.dirname(__file__), "gm_browser.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"✓ 生成: {out}  ({len(records)} 家公司)")
