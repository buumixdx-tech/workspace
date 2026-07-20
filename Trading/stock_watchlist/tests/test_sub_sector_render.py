"""调试:切到 109 后 sz.300321 stock-row 是否在 DOM。"""
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

        # 切到 109
        page.click('.sector-node[data-id="109"]')
        time.sleep(3)

        snap = page.evaluate("""() => {
            const row = document.querySelector('.stock-row[data-code="sz.300321"]');
            const inCurrent = state.currentStocks.find(s => s.stock_code === 'sz.300321');
            const inCache = !!state.subSectorCache[121] && state.subSectorCache[121].stocks ?
                state.subSectorCache[121].stocks.find(s => s.stock_code === 'sz.300321') : null;
            return {
                stockRowExists: !!row,
                currentStocks_has: !!inCurrent,
                subSectorCache121_keys: Object.keys(state.subSectorCache || {}),
                subSectorCache121_stocks_count: state.subSectorCache[121] && state.subSectorCache[121].stocks ? state.subSectorCache[121].stocks.length : -1,
                subSectorCache121_has_sz300321: !!inCache,
            };
        }""")
        print(f"切到 109 后 3s: {snap}")

        # selectStock
        page.evaluate("ui.selectStock('sz.300321')")
        time.sleep(0.3)
        snap2 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sz.300321');
            const row = document.querySelector('.stock-row[data-code="sz.300321"]');
            return {
                noteRowExists: !!note,
                noteMaxHeight: note ? note.style.maxHeight : null,
                stockRowExists: !!row,
                selectedStockCode: state.selectedStockCode,
            };
        }""")
        print(f"selectStock 后 0.3s: {snap2}")

        time.sleep(1.5)
        snap3 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sz.300321');
            return {
                noteRowExists: !!note,
                noteMaxHeight: note ? note.style.maxHeight : null,
            };
        }""")
        print(f"1.8s 后: {snap3}")

        print(f"\n=== console 日志 ({len(logs)} 条) ===")
        for log in logs[-15:]:
            print(f"  {log}")

        browser.close()


if __name__ == "__main__":
    main()
