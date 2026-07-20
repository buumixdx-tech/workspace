#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_to_docx.py — Substack 文章下载 + 转换 docx / pdf / md

免费文章: 直接抓
付费文章: --cookies cookies.txt (Netscape 格式 / 简单 "k=v" 每行)
t.co 短链: 先用 HEAD/GET 展开, 再抓真实 URL

输出:    <out>/<publication>/<slug>.{md,docx,pdf}
         默认 <out> = HERE/output (脚本所在目录/output)

用法:
  python fetch_to_docx.py --url "https://xxx.substack.com/p/some-post"
  python fetch_to_docx.py --url "https://xxx.substack.com/p/some-post" --cookies cookies.txt
  python fetch_to_docx.py --url "https://t.co/AApOwRrrE2"  # 自动展开
  python fetch_to_docx.py --url "https://..." --format md   # 只输出 md
  python fetch_to_docx.py --url "https://..." --out D:\workspace\Substack\output
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# 脚本所在目录的父目录 = skill 根 (脚本在 <skill>/scripts/ 下)
# 用 os.path.abspath 而非 Path.resolve() — 后者在 Windows NTFS 上会
# 大小写不敏感地把驱动器大写化 (D:\workspace -> D:\WorkSpace)
import os as _os
HERE = Path(_os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..")))
OUTPUT = HERE / "output"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


# ---------- t.co 短链展开 ----------
def expand_tco(url: str) -> str:
    if "t.co/" not in url:
        return url
    print(f"  [tco] expanding {url}...")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15, allow_redirects=True)
        final = r.url
        if final != url:
            print(f"  [tco] -> {final}")
            return final
        m = re.search(r'URL=([^"\']+)', r.text, re.IGNORECASE)
        if m:
            target = unescape(m.group(1))
            print(f"  [tco] -> {target}")
            return target
    except Exception as e:
        print(f"  [tco] expand failed: {e}, using original")
    return url


# ---------- Cookie 加载 ----------
def load_cookies(path: str) -> dict:
    jar = {}
    p = Path(path)
    if not p.exists():
        sys.exit(f"[!] cookies file not found: {path}")
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("http://", "https://")) and "\t" in line:
            parts = line.split("\t")
            if len(parts) >= 7:
                jar[parts[5]] = parts[6]
        elif "=" in line and not line.startswith("//"):
            k, v = line.split("=", 1)
            jar[k.strip()] = v.strip()
    return jar


# ---------- 抓取 ----------
def fetch(url: str, cookies: dict) -> str:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    if cookies:
        s.cookies.update(cookies)
    r = s.get(url, timeout=30, allow_redirects=True)
    r.raise_for_status()
    return r.text


# ---------- 付费墙探测 ----------
def is_paywalled(html_str: str) -> bool:
    soup = BeautifulSoup(html_str, "html.parser")
    if soup.find(class_=re.compile(r"paywall|locked", re.I)):
        return True
    text = soup.get_text(" ", strip=True)[:5000].lower()
    if "subscribe to continue" in text or "this post is for paid subscribers" in text:
        return True
    return False


# ---------- 状态数据提取 ----------
def _extract_window_preloads(html_str: str) -> dict | None:
    """Substack 把数据埋在 window._preloads = JSON.parse("...") 里
       这是最可靠的主路径 (2025+ 几乎所有 publication 都用这个)"""
    idx = html_str.find('window._preloads')
    if idx < 0:
        return None
    # 找 JSON.parse("  之后
    marker = 'JSON.parse("'
    start = html_str.find(marker, idx)
    if start < 0:
        return None
    start += len(marker)
    # 手动反解 JS 字符串, 找结束引号 (跳过 \")
    i = start
    while i < len(html_str):
        c = html_str[i]
        if c == '\\':
            i += 2
            continue
        if c == '"':
            break
        i += 1
    raw = html_str[start:i]
    # 反转义 \" -> ", \\ -> \
    unescaped = raw.replace('\\"', '"').replace('\\/', '/').replace('\\\\', '\\')
    try:
        return json.loads(unescaped)
    except Exception as e:
        print(f"  [!] window._preloads parse failed: {e}")
        return None


def _extract_preloaded_state_script(html_str: str) -> dict | None:
    """旧版 Substack: <script id="preloaded-state">{...}</script>"""
    m = re.search(r'<script[^>]*id=["\']?preloaded-?state["\']?[^>]*>(.+?)</script>',
                  html_str, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception as e:
        print(f"  [!] preloaded-state script parse failed: {e}")
        return None


def _extract_state(html_str: str) -> dict | None:
    """先试 window._preloads, 再试 preloaded-state script"""
    s = _extract_window_preloads(html_str)
    if s:
        return s
    return _extract_preloaded_state_script(html_str)


# ---------- 字段 fallback ----------
def _extract_author_from_state(state: dict, post: dict) -> str:
    """多层 fallback 拿作者名"""
    # 1. post.user.name
    user = post.get("user") or {}
    for k in ("name", "public_name", "display_name"):
        v = (user.get(k) or "").strip() if isinstance(user, dict) else ""
        if v:
            return v
    # 2. post.author / byline
    for k in ("author", "byline", "display_author", "author_name"):
        v = (post.get(k) or "").strip()
        if v:
            return v
    # 3. post.publishedBylines[0].name  ← 2025+ 主要走这里
    bylines = post.get("publishedBylines") or post.get("bylines") or []
    if isinstance(bylines, list) and bylines:
        first = bylines[0]
        if isinstance(first, dict):
            v = (first.get("name") or first.get("display_name") or "").strip()
            if v:
                return v
    # 4. 顶层 state.user
    state_user = state.get("user") or {}
    if isinstance(state_user, dict):
        for k in ("name", "public_name"):
            v = (state_user.get(k) or "").strip()
            if v:
                return v
    return ""


def _extract_date_from_state(post: dict) -> str:
    for k in ("post_date", "published_at", "first_published_at",
              "audience_at", "created_at", "publish_date"):
        v = post.get(k)
        if v:
            return str(v).strip()
    return ""


def _extract_publication(state: dict) -> str:
    """拿 publication 名: pub.name > publisher.name > publication.name"""
    pub = state.get("pub") or {}
    if isinstance(pub, dict):
        v = (pub.get("name") or pub.get("subdomain") or "").strip()
        if v:
            return v
    pub2 = state.get("publisher") or {}
    if isinstance(pub2, dict):
        v = (pub2.get("name") or "").strip()
        if v:
            return v
    pub3 = state.get("publication") or {}
    if isinstance(pub3, dict):
        v = (pub3.get("name") or "").strip()
        if v:
            return v
    return "substack"


def _find_post_in_state(state: dict) -> dict | None:
    """从 state 找文章对象"""
    for k in ("post", "currentPost", "postWithPublishedMetadata"):
        v = state.get(k)
        if isinstance(v, dict) and v.get("body_html"):
            return v
    # 兜底: posts.* 第一个含 body_html
    d = state.get("posts") or {}
    if isinstance(d, dict):
        for v in d.values():
            if isinstance(v, dict) and v.get("body_html"):
                return v
    # 顶层扫一遍
    for v in state.values():
        if isinstance(v, dict) and v.get("body_html") and v.get("title"):
            return v
    return None


# ---------- 解析 ----------
def parse(html_str: str, base_url: str) -> dict:
    state = _extract_state(html_str)
    if state:
        post = _find_post_in_state(state)
        if post:
            return parse_from_state(state, post, base_url)
        print("  [!] state 找到了但 post 找不到, falling back to HTML scrape")
    return parse_from_html(html_str, base_url)


def parse_from_state(state: dict, post: dict, base_url: str) -> dict:
    title = unescape(post.get("title") or "(untitled)").strip()
    subtitle = (post.get("subtitle") or "").strip()
    author = _extract_author_from_state(state, post)
    pub_date = _extract_date_from_state(post)
    body_html = post.get("body_html") or ""

    return {
        "publication": _extract_publication(state),
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "date": pub_date,
        "body_html": body_html,
        "base_url": base_url,
    }


def parse_from_html(html_str: str, base_url: str) -> dict:
    soup = BeautifulSoup(html_str, "html.parser")
    title = (soup.title.string or "(untitled)").strip() if soup.title else "(untitled)"
    body = soup.find("div", class_=re.compile(r"body|post-content|available-content"))
    if not body:
        body = soup.find("article") or soup.find("main") or soup.body
    return {
        "publication": urlparse(base_url).netloc.split(".")[0],
        "title": title,
        "subtitle": "",
        "author": "",
        "date": "",
        "body_html": str(body) if body else "",
        "base_url": base_url,
    }


# ---------- HTML -> Markdown ----------
def html_to_markdown(body_html: str, base_url: str) -> str:
    soup = BeautifulSoup(body_html, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src") or ""
        m = re.search(r"https%3A%2F%2F[^!\")'\s]+|https://substack-post-media\.s3[^)\"'\s]+", src)
        if m:
            real = unescape(m.group(0).replace("https%3A%2F%2F", "https://"))
            img["src"] = real
        if "pixel.wp.com" in (img.get("src") or "") or "tracking." in (img.get("src") or ""):
            img.decompose()

    out = []
    for el in soup.children:
        s = str(el)
        s = re.sub(r"<(p)(\s[^>]*)?>", "\n\n", s)
        s = re.sub(r"</p>", "\n", s)
        s = re.sub(r"<h1(\s[^>]*)?>", "\n\n# ", s)
        s = re.sub(r"<h2(\s[^>]*)?>", "\n\n## ", s)
        s = re.sub(r"<h3(\s[^>]*)?>", "\n\n### ", s)
        s = re.sub(r"<h4(\s[^>]*)?>", "\n\n#### ", s)
        s = re.sub(r"</h[1-6]>", "\n", s)
        s = re.sub(r"<(strong|b)>", "**", s)
        s = re.sub(r"</(strong|b)>", "**", s)
        s = re.sub(r"<(em|i)>", "*", s)
        s = re.sub(r"</(em|i)>", "*", s)
        s = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>', r"[\1](", s)
        s = re.sub(r"</a>", ")", s)
        s = re.sub(r"<(blockquote)(\s[^>]*)?>", "\n\n> ", s)
        s = re.sub(r"</blockquote>", "\n", s)
        s = re.sub(r"<(ul|ol)(\s[^>]*)?>", "\n\n", s)
        s = re.sub(r"</(ul|ol)>", "\n", s)
        s = re.sub(r"<li>", "\n- ", s)
        s = re.sub(r"</li>", "", s)

        def _img_repl(m):
            return f"\n\n![]({m.group(1)})\n\n"
        s = re.sub(r'<img[^>]*src="([^"]+)"[^>]*/?>', _img_repl, s)
        s = re.sub(r"<br\s*/?>", "\n", s)
        s = re.sub(r"<[^>]+>", "", s)
        out.append(unescape(s))

    md = "".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


# ---------- 写文件 + 调 pandoc ----------
def write_outputs(meta: dict, md: str, out_dir: Path, fmt: str = "all") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w\-]+", "-", meta["title"].lower())[:80].strip("-") or "post"
    md_path = out_dir / f"{slug}.md"
    docx_path = out_dir / f"{slug}.docx"
    pdf_path = out_dir / f"{slug}.pdf"

    header = f"# {meta['title']}\n\n"
    if meta.get("subtitle"):
        header += f"**{meta['subtitle']}**\n\n"
    if meta.get("author") or meta.get("date"):
        bits = []
        if meta.get("author"):
            bits.append(f"作者: {meta['author']}")
        if meta.get("date"):
            bits.append(f"发布: {meta['date']}")
        header += " · ".join(bits) + "\n\n"
    header += f"来源: {meta['base_url']}\n\n---\n\n"

    md_path.write_text(header + md + "\n", encoding="utf-8")
    print(f"  [md]   -> {md_path}")

    paths = {"md": md_path, "chars": len(md)}
    if fmt in ("docx", "all"):
        res = subprocess.run(
            ["pandoc.exe", str(md_path), "-o", str(docx_path), "--from", "markdown",
             "--resource-path", str(out_dir)],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            print(f"  [docx] -> {docx_path}")
            paths["docx"] = docx_path
        else:
            print(f"  [!] pandoc docx error: {res.stderr[:200]}")
    if fmt in ("pdf", "all"):
        res = subprocess.run(
            ["pandoc.exe", str(md_path), "-o", str(pdf_path), "--from", "markdown"],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            print(f"  [pdf]  -> {pdf_path}")
            paths["pdf"] = pdf_path
        else:
            print(f"  [!] pandoc pdf error (LaTeX not installed?): {res.stderr[:200]}")
    return paths


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--cookies", help="Netscape/简易 k=v 格式的 cookie 文件")
    ap.add_argument("--out", default=str(OUTPUT),
                    help=f"输出根目录 (默认 {OUTPUT})")
    ap.add_argument("--format", default="all", choices=["md", "docx", "pdf", "all"],
                    help="输出格式 (默认 all)")
    args = ap.parse_args()

    url = expand_tco(args.url)

    cookies = load_cookies(args.cookies) if args.cookies else {}
    if cookies:
        print(f"[*] using {len(cookies)} cookies from {args.cookies}")

    print(f"[*] fetching: {url}")
    html_str = fetch(url, cookies)
    print(f"[*] got {len(html_str)} bytes")

    if is_paywalled(html_str):
        print("[!] 付费墙检测: 文章被锁, 当前 cookie 可能无效或未订阅")
        print("    如果是已订阅文章, 请提供 cookie 文件: --cookies <path>")

    print("[*] parsing...")
    meta = parse(html_str, url)
    print(f"    publication: {meta['publication']}")
    print(f"    title:       {meta['title']}")
    print(f"    author:      {meta['author']}")
    print(f"    date:        {meta['date']}")
    print(f"    body chars:  {len(meta['body_html'])}")

    print("[*] converting HTML -> Markdown...")
    md = html_to_markdown(meta["body_html"], url)
    print(f"    markdown chars: {len(md)}")

    out_dir = Path(args.out) / meta["publication"]
    paths = write_outputs(meta, md, out_dir, args.format)
    print(f"\n[done] {paths['chars']} chars written")
    for k, v in paths.items():
        if k != "chars":
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
