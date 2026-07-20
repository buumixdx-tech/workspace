"""用户在浏览器里操作: 点 stock-row 触发 selectStock。模拟这个事件 + 装 MutationObserver 在
#stock-list 上看 note-row 是否被删。"""
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

        # 装 MutationObserver 在 #stock-list 上
        page.evaluate("""() => {
            window._ml = [];
            const target = document.getElementById('stock-list');
            const ob = new MutationObserver(muts => {
                for (const m of muts) {
                    if (m.type === 'childList') {
                        for (const node of m.addedNodes) {
                            window._ml.push({t: Date.now(), ev: 'addChild', id: node.id || node.tagName});
                        }
                        for (const node of m.removedNodes) {
                            window._ml.push({t: Date.now(), ev: 'rmChild', id: node.id || node.tagName, parent: m.target.id});
                        }
                    }
                }
            });
            ob.observe(target, {childList: true, subtree: false});
        }""")

        # 真点击 stock-row(模拟用户操作,不是 ui.selectStock 直接调)
        page.click('.stock-row[data-code="sh.688625"]')
        time.sleep(0.3)
        s1 = page.evaluate("""() => {
            const n = document.getElementById('note-row-sh.688625');
            return {exists: !!n, mh: n?.style.maxHeight, list_children: document.getElementById('stock-list').children.length};
        }""")
        print(f"点击后 0.3s: {s1}")

        # 等 5s 经历一个 3s tick
        for i in range(10):
            time.sleep(0.5)
            s = page.evaluate("""() => {
                const n = document.getElementById('note-row-sh.688625');
                return {exists: !!n, mh: n?.style.maxHeight, list_children: document.getElementById('stock-list').children.length};
            }""")
            print(f"  t={(i+1)*0.5:.1f}s  exists={s['exists']} mh={s['mh']} list_children={s['list_children']}")

        # 输出 mutation 日志
        ml = page.evaluate("window._ml")
        print(f"\n=== MutationObserver ({len(ml)} 条) ===")
        t0 = ml[0]['t'] if ml else 0
        for l in ml[:30]:
            print(f"  +{l['t']-t0:5}ms  {l['ev']:7}  {l.get('id','')} {l.get('parent','')}")

        print(f"\n=== console ({len(logs)} 条) ===")
        for l in logs[-15:]:
            print(f"  {l}")

        browser.close()


if __name__ == "__main__":
    main()
