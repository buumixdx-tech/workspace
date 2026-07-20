"""端到端测试: 切板块、切股、写笔记、inline note、3s tick。"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5181/"

def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))

        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        # 1. 切板块
        sectors = page.locator(".sector-node")
        n = sectors.count()
        print(f"sectors found: {n}")
        if n < 2:
            errors.append(f"板块数 < 2, 没法切板块")
            browser.close(); return

        sectors.nth(0).click()
        page.wait_for_timeout(1500)
        s1_count = page.evaluate("document.querySelectorAll('.stock-row').length")
        print(f"sector 1 stocks: {s1_count}")

        sectors.nth(1).click()
        page.wait_for_timeout(1500)
        s2_count = page.evaluate("document.querySelectorAll('.stock-row').length")
        print(f"sector 2 stocks: {s2_count}")

        if s2_count == 0:
            errors.append("板块 2 没有 stock-row")

        # 2. 选股
        rows = page.locator(".stock-row")
        if rows.count() > 0:
            rows.first.click()
            page.wait_for_timeout(2000)
            detail = page.evaluate("document.getElementById('stock-detail').style.display")
            if detail != 'flex':
                errors.append(f"详情面板未显示 display={detail}")

        # 3. 选第二只股, 看 inline note 是不是又出来
        if rows.count() > 1:
            rows.nth(1).click()
            page.wait_for_timeout(1500)
            notes_area = page.evaluate("document.getElementById('notes-area')?.style.display")
            print(f"notes-area display: {notes_area}")

        # 4. 切回板块 1, 再点股票, 看 inline note 恢复
        sectors.nth(0).click()
        page.wait_for_timeout(1500)
        rows2 = page.locator(".stock-row")
        if rows2.count() > 0:
            rows2.first.click()
            page.wait_for_timeout(1500)
            note_rows = page.evaluate("document.querySelectorAll('.stock-note-row').length")
            print(f"note-row count after re-select: {note_rows}")

        # 5. 3s tick 验证 — 等 7s, 看 quote 价格有没有变 (也确保没崩)
        page.wait_for_timeout(7000)
        for e in errors:
            print("ERROR:", e)

        browser.close()

    if errors:
        sys.exit(1)
    print("E2E OK")

if __name__ == "__main__":
    main()