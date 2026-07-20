"""复现:首次点股 → 切日K,看是否拉到数据。"""
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

        page.goto("http://127.0.0.1:5181/")
        page.wait_for_selector("#sector-tree .sector-node", timeout=10000)
        time.sleep(1.5)

        # 切到 101
        page.click('.sector-node[data-id="101"]')
        time.sleep(3)

        # 首次点股 sh.605111 (selectStock 走完,此时 chartData.kline 应为 null)
        page.click('.stock-row[data-code="sh.605111"]')
        time.sleep(1.0)
        s1 = page.evaluate("""() => ({
            kline_null: state.chartData.kline === null,
            minute_null: state.chartData.minute === null,
            chartMode: state.chartMode,
            selectedStockCode: state.selectedStockCode,
        })""")
        print(f"selectStock 后: {s1}")

        # 切到日K
        page.click('#tab-kline')
        time.sleep(0.5)
        s2 = page.evaluate("""() => ({
            kline_null: state.chartData.kline === null,
            kline_bars_count: state.chartData.kline && state.chartData.kline.bars ? state.chartData.kline.bars.length : -1,
            chartMode: state.chartMode,
        })""")
        print(f"切日K 后 0.5s: {s2}")

        time.sleep(1.5)
        s3 = page.evaluate("""() => ({
            kline_bars_count: state.chartData.kline && state.chartData.kline.bars ? state.chartData.kline.bars.length : -1,
        })""")
        print(f"2s 后: {s3}")

        # 看 chart 容器内容
        chart_state = page.evaluate("""() => {
            const c = document.getElementById('chart-canvas');
            const empty = c && c.querySelector('div');
            return {
                hasChart: !!c,
                canvasContent: c ? c.innerHTML.slice(0, 200) : null,
            };
        }""")
        print(f"chart 容器: {chart_state}")

        print(f"\n=== console ({len(logs)} 条) ===")
        for l in logs[-10:]:
            print(f"  {l}")

        browser.close()


if __name__ == "__main__":
    main()
