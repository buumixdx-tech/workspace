"""用户场景:刷新 → 第一个板块笔记正常 → 切第二个板块 → 笔记下来后消失。"""
import time
from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def main():
    with sync_playwright() as p:
        # disable cache
        browser = p.chromium.launch(
            executable_path=CHROME, headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-cache"],
        )
        ctx = browser.new_context()
        page = ctx.new_page()
        # 加 cache-control bypass
        page.set_extra_http_headers({"Cache-Control": "no-cache, no-store"})
        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda e: logs.append(f"[ERROR] {e}"))

        page.goto("http://127.0.0.1:5181/?_=" + str(time.time()))
        page.wait_for_selector("#sector-tree .sector-node", timeout=10000)
        time.sleep(1.5)

        # 1) 切到 101 (800vDC) — 用户说的"第一个板块"
        page.click('.sector-node[data-id="101"]')
        time.sleep(3)
        # 找第一只有笔记的股
        target = page.evaluate("Object.keys(state.notesCache)[0]")
        print(f"板块 101 第一只有笔记的股: {target}")
        page.evaluate(f"ui.selectStock({target!r})")
        time.sleep(0.5)
        s1 = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{target}');
            return {{noteRowExists: !!note, noteMaxHeight: note ? note.style.maxHeight : null}};
        }}""")
        print(f"  板块 101 笔记: {s1}")

        # 2) 切到第二个板块 109 (PCB)
        page.click('.sector-node[data-id="109"]')
        time.sleep(3)
        # 找 109 内真实有笔记的股 — 父板块直接股 sh.688625 (之前已知有笔记)
        target2 = 'sh.688625'
        has_note = page.evaluate(f"{target2!r} in state.notesCache && state.notesCache[{target2!r}].length > 0")
        print(f"  109 父板块直接股 {target2} 有笔记: {has_note}")
        if not has_note:
            # 退而求其次,找 currentStocks 内第一只有笔记的
            target2 = page.evaluate("""() => {
                for (const s of state.currentStocks) {
                    if (state.notesCache[s.stock_code] && state.notesCache[s.stock_code].length > 0)
                        return s.stock_code;
                }
                return null;
            }""")
            print(f"  退而求其次: {target2}")
        print(f"\n板块 109 第一只有笔记的股: {target2}")
        # 在切板块前先看 selectedStockCode
        s_pre = page.evaluate("state.selectedStockCode")
        print(f"  切板块前 selectedStockCode: {s_pre}")
        # 看 stock-list
        s_dom = page.evaluate("""() => {
            const list = document.getElementById('stock-list');
            return {
                rowCount: list ? list.querySelectorAll('.stock-row').length : -1,
                firstRowCode: list ? (list.querySelector('.stock-row')||{}).dataset?.code : null,
            };
        }""")
        print(f"  切板块后 stock-list: {s_dom}")
        # 关键: selectStock 之前看 noteRow 是否被残留
        s_remain = page.evaluate(f"""() => {{
            const oldNote = document.getElementById('note-row-{target}');
            return {{oldNoteRowExists: !!oldNote, oldNoteMaxHeight: oldNote ? oldNote.style.maxHeight : null}};
        }}""")
        print(f"  旧 note-row 残留: {s_remain}")

        page.evaluate(f"ui.selectStock({target2!r})")
        time.sleep(0.1)
        s2 = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{target2}');
            return {{noteRowExists: !!note, noteMaxHeight: note ? note.style.maxHeight : null, selectedStockCode: state.selectedStockCode}};
        }}""")
        print(f"  板块 109 selectStock 0.1s: {s2}")

        time.sleep(0.5)
        s3 = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{target2}');
            return {{noteRowExists: !!note, noteMaxHeight: note ? note.style.maxHeight : null, noteInDOM: note ? document.body.contains(note) : false}};
        }}""")
        print(f"  板块 109 selectStock 0.6s: {s3}")

        time.sleep(2.0)
        s4 = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{target2}');
            return {{noteRowExists: !!note, noteMaxHeight: note ? note.style.maxHeight : null, noteInDOM: note ? document.body.contains(note) : false}};
        }}""")
        print(f"  板块 109 selectStock 2.6s: {s4}")

        print(f"\n=== console 日志 ({len(logs)} 条) ===")
        for log in logs[-20:]:
            print(f"  {log}")

        browser.close()


if __name__ == "__main__":
    main()
