"""复现:切到 126 锚定律动(parent) → 默认子板块 135 华为超节点 已展开 → 点 sh.603296 →
确认 sub-sector-children 是否已经渲染 stock-row,以及 showInlineNoteView 是否成功。"""
import sys
import time
from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME, headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context()
        page = ctx.new_page()
        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda e: logs.append(f"[ERROR] {e}"))

        page.goto("http://127.0.0.1:5181/")
        page.wait_for_selector("#sector-tree .sector-node", timeout=10000)
        time.sleep(1.5)

        # 1) 切到 126 锚定律动
        page.click('.sector-node[data-id="126"]')
        time.sleep(3)

        # 2) 看子板块 135 是否已展开 + sh.603296 的 stock-row 是否在 DOM
        snap = page.evaluate("""() => {
            const child135 = document.querySelector('.sub-sector-block[data-sid="135"]');
            const childList = child135 ? child135.querySelector('.sub-sector-children') : null;
            const row603296 = document.querySelector('.stock-row[data-code="sh.603296"]');
            return {
                child135_exists: !!child135,
                child135_open: child135 ? child135.querySelector('.sub-sector-toggle').classList.contains('open') : null,
                child135_innerHTML_empty: childList ? childList.innerHTML === '' : null,
                child135_rowCount: childList ? childList.querySelectorAll('.stock-row').length : 0,
                sh603296_row_exists: !!row603296,
            };
        }""")
        print(f"切到 126 后 3s 状态: {snap}")

        # 3) 主动 selectStock sh.603296
        page.evaluate("ui.selectStock('sh.603296')")
        time.sleep(0.3)
        snap1 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            return {
                noteRowExists: !!note,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
                selectedStockCode: state.selectedStockCode,
            };
        }""")
        print(f"selectStock sh.603296 后 0.3s: {snap1}")

        time.sleep(1.5)
        snap2 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            const noteInDOM = note ? document.body.contains(note) : false;
            const row = document.querySelector('.stock-row[data-code="sh.603296"]');
            return {
                noteRowExists: !!note,
                noteInDOM,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
                stockRowExists: !!row,
                selectedStockCode: state.selectedStockCode,
            };
        }""")
        print(f"1.5s 后: {snap2}")

        time.sleep(2.0)
        snap3 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            return {
                noteRowExists: !!note,
                noteInDOM: note ? document.body.contains(note) : false,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
            };
        }""")
        print(f"3.5s 后(过一个 tick): {snap3}")

        # console 日志
        print(f"\n=== console 日志 ({len(logs)} 条) ===")
        for log in logs[-20:]:
            print(f"  {log}")

        browser.close()


if __name__ == "__main__":
    main()
