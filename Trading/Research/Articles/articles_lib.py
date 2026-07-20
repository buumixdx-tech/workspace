"""articles_lib — 核心逻辑(CLI 和 Flask 都 import 这个)

对外函数:
- build_article(url, translate, output_dir, docx_path=None) → Path
    拉 X article + 下载图片 + (可选)翻译 + 写 HTML
- list_articles(output_dir) → list[dict]
    扫描 output_dir/article_*.html 返回元数据列表
- RENDERED_HTML_TEMPLATE
    文章 HTML 模板(供 build_article 和独立用)
"""
from __future__ import annotations
import os, re, sys, json, shutil, urllib.request, threading
from pathlib import Path
from datetime import date

# ============================================================
# 1. 拉 X article
# ============================================================
def fetch_x_article(url: str) -> dict:
    """通过 fxtwitter API 拉 X article。返回 dict 含 title/blocks/entity_map/media_list/author/status_id/original_url"""
    m = re.search(r'x\.com/([^/]+)/status/(\d+)', url)
    if not m:
        raise ValueError(f'无法解析 X URL: {url}')
    user, sid = m.group(1), m.group(2)
    fx_api = f'https://api.fxtwitter.com/{user}/status/{sid}'
    with urllib.request.urlopen(fx_api, timeout=30) as r:
        fx = json.loads(r.read())
    art = fx['tweet']['article']
    title = art['title']
    content = art['content']
    blocks = content['blocks']
    em = content['entityMap']
    if isinstance(em, dict):
        ent_map = {int(k): v for k, v in em.items()}
    else:
        ent_map = {i: e.get('value', e) for i, e in enumerate(em)}
    return {
        'title': title,
        'blocks': blocks,
        'ent_map': ent_map,
        'media_list': art['media_entities'],
        'author': user,
        'status_id': sid,
        'original_url': url,
    }


# ============================================================
# 2. 下载图片
# ============================================================
def download_images(media_list: list, sid: str, output_dir: Path) -> dict:
    """下载所有图片到 output_dir/assets/<sid>/,返回 {media_id: filename}"""
    assets_dir = output_dir / 'assets' / sid
    assets_dir.mkdir(parents=True, exist_ok=True)
    img_files = {}
    for i, m in enumerate(media_list, 1):
        src = m['media_info']['original_img_url']
        dst = assets_dir / f'img_{i:02d}.jpg'
        if not dst.exists():
            req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                dst.write_bytes(r.read())
        img_files[m['media_id']] = dst.name
    return img_files


# ============================================================
# 3. 翻译(可选,默认开)
# ============================================================
def translate_x_article(blocks: list, title: str, model: str = None) -> tuple[str, list]:
    """调 MiniMax M3 把 blocks + title 翻成中文。返回 (new_title, new_blocks)。失败时保留原文。"""
    if not model:
        model = os.environ.get('ANTHROPIC_MODEL', 'MiniMax-M3')
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ['ANTHROPIC_AUTH_TOKEN'],
        base_url=os.environ['ANTHROPIC_BASE_URL'],
    )
    BATCH = 10
    MAX_TOKENS = 8192

    def _extract_text(resp) -> str:
        parts = []
        for blk in resp.content:
            if getattr(blk, 'type', None) == 'text' or hasattr(blk, 'text'):
                t = getattr(blk, 'text', None)
                if t:
                    parts.append(t)
        return '\n'.join(parts).strip()

    # 翻译 title
    new_title = title
    try:
        r = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            messages=[{'role': 'user', 'content':
                f'把下面这个英文标题译为简体中文。要求:股票代码、ticker、产品名、人名不译(NVDA、AMD、康宁、Absolics 等);只输出译文,不加任何前言。\n\n{title}'}],
        )
        cn = _extract_text(r).strip('"\'「」')
        if cn:
            new_title = cn
    except Exception as e:
        print(f'    ⚠️ title 翻译失败: {e}')

    # 翻译 blocks
    texts = [b.get('text', '') for b in blocks]
    translated = list(texts)
    total = len(texts)
    for i in range(0, total, BATCH):
        batch = texts[i:i+BATCH]
        numbered = '\n'.join(
            f'[{j+1}]{" /EMPTY/" if not t.strip() else " " + t}'
            for j, t in enumerate(batch)
        )
        prompt = (
            '你是专业财经/科技翻译。把下列编号英文段逐一译为简体中文。\n'
            '规则:\n'
            '- 保留 ticker、股票代码、产品名、人名、公司名不译(NVDA、AMD、Broadcom、Absolics、Corning、康宁、Taiwan、US 等)\n'
            '- 保留 emoji 不动\n'
            '- 保留 URL、markdown 链接不译\n'
            '- 输出 /EMPTY/ 表示原段是空行(保留为空)\n'
            '- 直接逐行输出译文,不加任何编号或前言\n\n'
            f'Input:\n{numbered}\n\nOutput:'
        )
        ok = False
        for attempt in (1, 2):
            try:
                r = client.messages.create(
                    model=model, max_tokens=MAX_TOKENS,
                    messages=[{'role': 'user', 'content': prompt}],
                )
                out_text = _extract_text(r)
                out_lines = [l for l in out_text.split('\n') if l.strip()]
                n_match = min(len(out_lines), len(batch))
                if n_match > 0:
                    for j in range(n_match):
                        line = out_lines[j].strip()
                        translated[i+j] = '' if line == '/EMPTY/' else line
                    print(f'    ✓ batch {i+1}-{min(i+BATCH,total)} / {total}')
                    ok = True
                    break
            except Exception as e:
                print(f'    ⚠️ batch {i+1} attempt {attempt} 错误: {e}')
        if not ok:
            print(f'    ✗ batch {i+1}-{min(i+BATCH,total)} 两次都失败,保留英文')
    new_blocks = [{**b, 'text': translated[k]} for k, b in enumerate(blocks)]
    return new_title, new_blocks


# ============================================================
# 4. blocks → HTML
# ============================================================
def blocks_to_html(blocks: list, ent_map: dict, img_files: dict, sid: str) -> str:
    """Draft.js blocks 转 HTML 字符串"""
    def render_md_table(md: str) -> str:
        lines = [l.strip() for l in md.strip().split('\n') if l.strip()]
        if len(lines) < 3: return md
        headers = [c.strip() for c in lines[0].strip('|').split('|')]
        rows = [[c.strip() for c in l.strip('|').split('|')] for l in lines[2:]]
        h = '<table><thead><tr>' + ''.join(f'<th>{c}</th>' for c in headers) + '</tr></thead><tbody>'
        for row in rows:
            h += '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
        return h + '</tbody></table>'

    def block_to_html(b: dict) -> str:
        t = b.get('text', '')
        btype = b.get('type', 'unstyled')
        entity_html = []
        for er in (b.get('entityRanges') or []):
            ent = ent_map.get(er['key'])
            if not ent: continue
            ent = ent.get('value', ent) if isinstance(ent, dict) else ent
            etype = ent.get('type')
            if etype == 'MEDIA':
                mid = ent.get('data', {}).get('mediaItems', [{}])[0].get('mediaId')
                if mid and mid in img_files:
                    entity_html.append(f'<img src="assets/{sid}/{img_files[mid]}" alt="配图" loading="lazy">')
            elif etype == 'MARKDOWN':
                entity_html.append(render_md_table(ent.get('data', {}).get('markdown', '')))
            elif etype == 'TWEMOJI':
                emoji_url = ent.get('data', {}).get('url', '')
                entity_html.append(f'<img class="emoji" src="{emoji_url}">')
            elif etype == 'DIVIDER':
                entity_html.append('<hr class="x-divider">')

        if btype == 'atomic':
            return ''.join(entity_html)
        if not t.strip():
            return ''
        if t.strip() and entity_html and not any(c.isalnum() and ord(c) < 128 for c in t):
            return ''.join(entity_html)
        if entity_html:
            inline_emojis = ''.join(e for e in entity_html if 'emoji' in e)
            block_imgs = ''.join(e for e in entity_html if 'emoji' not in e)
            t_with_emoji = t + inline_emojis if inline_emojis else t
            if block_imgs:
                return f'<p>{t_with_emoji}</p>\n{block_imgs}'
            return f'<p>{t_with_emoji}</p>'
        if t.startswith('http'):
            return f'<p class="quote-link">🔗 <a href="{t}">{t}</a></p>'
        m = re.match(r'^(\d+)/ (.+)$', t)
        if m and len(t) < 60:
            return f'<h2>{m.group(1)}/{m.group(2)}</h2>'
        if t == '一句话总结':
            return f'<h3 class="summary-title">{t}</h3>'
        return f'<p>{t}</p>'

    parts = []
    for b in blocks:
        h = block_to_html(b)
        if h: parts.append(h)
    return '\n'.join(parts)


# ============================================================
# 5. 模板
# ============================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
:root {{
  --bg: #0e1116; --bg-card: #181c25; --text: #e8eaed; --text-dim: #9aa0a6;
  --border: rgba(255,255,255,0.08); --accent: #5e72e4; --green: #10b981;
  --shadow: 0 10px 40px rgba(0,0,0,0.4);
}}
*,*::before,*::after {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at 15% 5%, rgba(94,114,228,0.10), transparent 40%),
    radial-gradient(circle at 85% 95%, rgba(255,107,107,0.06), transparent 40%),
    var(--bg);
  color: var(--text); line-height: 1.75; min-height: 100vh;
}}
.container {{ max-width: 920px; margin: 0 auto; padding: 48px 24px; }}
header.hero {{ text-align: center; padding: 40px 0 32px; border-bottom: 1px solid var(--border); margin-bottom: 40px; }}
header.hero h1 {{
  font-size: 38px; margin: 0 0 12px;
  background: linear-gradient(135deg, #5e72e4 0%, #ff6b6b 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px; font-weight: 800; line-height: 1.3;
}}
header.hero .meta {{ color: var(--text-dim); font-size: 14px; margin-top: 12px; }}
header.hero .meta a {{ color: var(--accent); text-decoration: none; }}
section {{ margin-bottom: 48px; }}
section.x-article {{ background: var(--bg-card); padding: 36px; border-radius: 16px; border: 1px solid var(--border); box-shadow: var(--shadow); }}
.section-title {{
  display: inline-block; font-size: 13px; color: var(--accent);
  background: rgba(94,114,228,0.12); padding: 4px 12px; border-radius: 6px;
  margin-bottom: 16px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;
}}
h2 {{ font-size: 24px; margin: 36px 0 16px; color: var(--accent); border-left: 4px solid var(--accent); padding-left: 14px; font-weight: 700; }}
h3 {{ font-size: 20px; margin: 24px 0 12px; color: #f5a623; }}
p {{ margin: 14px 0; font-size: 16px; }}
img {{ max-width: 100%; height: auto; border-radius: 10px; margin: 20px 0; box-shadow: 0 6px 24px rgba(0,0,0,0.4); display: block; }}
img.emoji {{ display: inline; height: 1em; margin: 0 2px; box-shadow: none; }}
hr.x-divider {{ border: 0; border-top: 1px solid var(--border); margin: 32px auto; width: 60%; }}
table {{ width: 100%; border-collapse: collapse; margin: 24px 0; font-size: 14px; background: rgba(255,255,255,0.02); border-radius: 8px; overflow: hidden; }}
th, td {{ padding: 12px 14px; text-align: left; border: 1px solid var(--border); }}
th {{ background: rgba(94,114,228,0.18); color: var(--text); font-weight: 700; font-size: 13px; text-transform: uppercase; }}
td {{ color: var(--text-dim); }}
@media (max-width: 600px) {{
  .container {{ padding: 24px 16px; }}
  header.hero h1 {{ font-size: 26px; }}
  section.x-article {{ padding: 20px; }}
}}
</style>
</head>
<body>
<div class="container">
<header class="hero">
  <h1>{title}</h1>
  <div class="meta">
    来源 <a href="{original_url}" target="_blank">@{author} on X</a>
    · 编入于 {date_iso}
  </div>
</header>
<section class="x-article">
  <span class="section-title">{section_label}</span>
  {x_body}
</section>
</div>
</body>
</html>
"""


# ============================================================
# 6. 编排:build_article
# ============================================================
def build_article(url: str, translate: bool, output_dir: Path, docx_path: str = None) -> dict:
    """完整流程:fetch → download → (translate) → render → write

    返回 {'path': Path, 'title': str, 'sid': str, 'author': str, 'translated': bool}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = fetch_x_article(url)
    sid, author, title = data['status_id'], data['author'], data['title']
    blocks, ent_map, media_list = data['blocks'], data['ent_map'], data['media_list']

    img_files = download_images(media_list, sid, output_dir)

    if translate:
        title, blocks = translate_x_article(blocks, title)

    x_body = blocks_to_html(blocks, ent_map, img_files, sid)

    section_label = '🤖 X 原文 AI 翻译' if translate else "📰 X 原文 (Author's Original)"
    html = HTML_TEMPLATE.format(
        title=title, original_url=url, author=author,
        date_iso=date.today().isoformat(),
        section_label=section_label, x_body=x_body,
    )

    out_file = output_dir / f'article_{sid}.html'
    out_file.write_text(html, encoding='utf-8')
    return {
        'path': out_file,
        'title': title,
        'sid': sid,
        'author': author,
        'translated': translate,
        'image_count': len(media_list),
    }


# ============================================================
# 7. 列表(从文件系统扫)
# ============================================================
def list_articles(output_dir: Path) -> list[dict]:
    """扫描 output_dir/article_*.html,提取元数据"""
    output_dir = Path(output_dir)
    items = []
    for f in sorted(output_dir.glob('article_*.html'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            content = f.read_text(encoding='utf-8')
        except Exception:
            continue
        sid = f.stem.replace('article_', '')
        m_title = re.search(r'<title>([^<]+)</title>', content)
        m_author = re.search(r'@(\w+) on X', content)
        m_date = re.search(r'编入于 (\d{4}-\d{2}-\d{2})', content)
        translated = 'AI 翻译' in content
        # 是否有图片
        has_images = 'assets/' in content and '<img' in content
        items.append({
            'sid': sid,
            'title': m_title.group(1) if m_title else '(无标题)',
            'author': m_author.group(1) if m_author else '?',
            'date': m_date.group(1) if m_date else '',
            'translated': translated,
            'has_images': has_images,
            'url': f'/articles/article_{sid}.html',
            'mtime': f.stat().st_mtime,
        })
    return items
