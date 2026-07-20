"""长时间密集观察: 切板块 → 选股 → 10s 内每 200ms 抓 note-row 状态 + 监控 DOM mutation。"""
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

        # 1) 切到 101,选 sh.605111
        page.click('.sector-node[data-id="101"]')
        time.sleep(3)
        page.evaluate("ui.selectStock('sh.605111')")
        time.sleep(0.5)
        s1 = page.evaluate("""() => {
            const n = document.getElementById('note-row-sh.605111');
            return {exists: !!n, maxH: n?.style.maxHeight, disp: n?.style.display};
        }""")
        print(f"101 板块 0.5s: {s1}")

        # 2) 切到 109,选 sh.688625
        page.click('.sector-node[data-id="109"]')
        time.sleep(3)
        page.evaluate("ui.selectStock('sh.688625')")
        # 装上 MutationObserver
        page.evaluate("""() => {
            window._noteLogs = [];
            const target = document.body;
            const observer = new MutationObserver(muts => {
                for (const m of muts) {
                    for (const node of m.addedNodes) {
                        if (node.id && node.id.startsWith('note-row-')) {
                            window._noteLogs.push({t: Date.now(), ev: 'add', id: node.id, mh: node.style.maxHeight});
                        }
                    }
                    if (m.removedNodes.length > 0) {
                        for (const node of m.removedNodes) {
                            if (node.id && node.id.startsWith('note-row-')) {
                                window._noteLogs.push({t: Date.now(), ev: 'remove', id: node.id});
                            }
                        }
                    }
                    if (m.type === 'attributes' && m.target.id && m.target.id.startsWith('note-row-')) {
                        if (m.attributeName === 'style') {
                            window._noteLogs.push({t: Date.now(), ev: 'style', id: m.target.id, mh: m.target.style.maxHeight, disp: m.target.style.display});
                        }
                    }
                }
            });
            observer.observe(target, {childList: true, subtree: true, attributes: true, attributeFilter: ['style']});
        }""")

        # 3) 10s 抓快照
        print("\n10s 监控 (每 500ms):")
        for i in range(20):
            time.sleep(0.5)
            s = page.evaluate("""() => {
                const n = document.getElementById('note-row-sh.688625');
                return {
                    exists: !!n,
                    inDOM: n ? document.body.contains(n) : false,
                    maxH: n ? n.style.maxHeight : null,
                    disp: n ? n.style.display : null,
                    selectedStockCode: state.selectedStockCode,
                    busySelecting: state.busySelecting,
                    lastSelectAt: state._lastSelectAt,
                    now: Date.now(),
                };
            }""")
            print(f"  t={i*0.5:.1f}s  {s}")

        # 4) 输出 MutationObserver 日志
        logs2 = page.evaluate("window._noteLogs")
        print(f"\n=== MutationObserver 日志 ({len(logs2)} 条) ===")
        t0 = logs2[0]['t'] if logs2 else 0
        for l in logs2:
            print(f"  +{l['t']-t0:5}ms  {l['ev']:6}  {l.get('id','')}  {l.get('mh','')}  {l.get('disp','')}")

        # 5) console
        print(f"\n=== console 日志 ({len(logs)} 条) ===")
        for l in logs[-15:]:
            print(f"  {l}")

        browser.close()


if __name__ == "__main__":
    main()
