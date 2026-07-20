"""拆分后的浏览器 smoke test:加载页面,点板块,点个股,看 console 报错。"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5181/"

def main():
    errors = []
    console_msgs = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222") if False else None
        # 用本地 chromium
        browser = p.chromium.launch(channel="chrome", headless=True) if False else p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))

        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        # 1. 检查模块化对象都加载了
        for mod in ["Util", "Sector", "StockList", "Notes", "Modal", "Chart"]:
            exists = page.evaluate(f"typeof window.{mod}")
            if exists != "object" and exists != "function":
                errors.append(f"模块 {mod} 未挂到 window (got {exists})")

        # 2. 检查 sector 树渲染了
        sector_count = page.evaluate("document.querySelectorAll('.sector-node').length")
        if sector_count == 0:
            errors.append("sector 树为空")

        # 3. 找第一个板块,点击进入
        first = page.locator(".sector-node").first
        if first.count() == 0:
            errors.append("找不到第一个 .sector-node")
        else:
            first.click()
            page.wait_for_timeout(2000)
            stock_count = page.evaluate("document.querySelectorAll('.stock-row').length")
            if stock_count == 0:
                errors.append("点板块后 stock-row 为 0 (板块可能无股或没渲染)")
            else:
                # 4. 点第一只股
                page.locator(".stock-row").first.click()
                page.wait_for_timeout(2000)
                detail_visible = page.evaluate("document.getElementById('stock-detail').style.display")
                if detail_visible != 'flex':
                    errors.append(f"详情面板未显示, display={detail_visible}")

        # 5. 检查 3s tick 还在跑 (看是否有 chart 引用错误)
        page.wait_for_timeout(3500)

        browser.close()

    print("=== console (前 40 条) ===")
    for m in console_msgs[:40]:
        print(m)
    print(f"\n=== 错误 ({len(errors)}) ===")
    for e in errors:
        print("  -", e)
    if errors:
        sys.exit(1)
    print("\nOK")

if __name__ == "__main__":
    main()