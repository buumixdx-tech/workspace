"""trace selectStock 完整调用链。"""
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

        # 切到 126
        page.click('.sector-node[data-id="126"]')
        time.sleep(3)

        # 注入 trace 到 showInlineNoteView
        page.evaluate("""() => {
            const orig = window.showInlineNoteView;
            window.showInlineNoteView = function(code, n) {
                const stockRow = document.querySelector(`.stock-row[data-code="${CSS.escape(code)}"]`);
                console.log('[TRACE] showInlineNoteView called code=' + code + ' note_id=' + n.id);
                console.log('[TRACE]   stockRowExists=' + !!stockRow);
                const ret = orig.call(this, code, n);
                const after = document.getElementById('note-row-' + code);
                console.log('[TRACE]   after call: noteRowExists=' + !!after + ' maxHeight=' + (after ? after.style.maxHeight : 'null'));
                return ret;
            };
        }""")

        # 调 selectStock 并加 await + try-catch 看错误
        result = page.evaluate("""async () => {
            try {
                await ui.selectStock('sh.603296');
                return {ok: true};
            } catch (e) {
                return {ok: false, error: e.message, stack: e.stack};
            }
        }""")
        print(f"selectStock await 结果: {result}")
        time.sleep(0.1)
        snap1 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            const rows = document.querySelectorAll('.stock-row[data-code="sh.603296"]');
            return {
                noteRowExists: !!note,
                noteInDOM: note ? document.body.contains(note) : false,
                noteMaxHeight: note ? note.style.maxHeight : null,
                stockRowCount: rows.length,
                selectedStockCode: state.selectedStockCode,
            };
        }""")
        print(f"selectStock 后 0.1s: {snap1}")

        time.sleep(0.5)
        snap2 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            return {
                noteRowExists: !!note,
                noteInDOM: note ? document.body.contains(note) : false,
                noteMaxHeight: note ? note.style.maxHeight : null,
            };
        }""")
        print(f"0.6s 后: {snap2}")

        time.sleep(2.0)
        snap3 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            return {
                noteRowExists: !!note,
                noteInDOM: note ? document.body.contains(note) : false,
                noteMaxHeight: note ? note.style.maxHeight : null,
            };
        }""")
        print(f"2.6s 后: {snap3}")

        print(f"\n=== console 日志 ({len(logs)} 条) ===")
        for log in logs[-25:]:
            print(f"  {log}")

        browser.close()


if __name__ == "__main__":
    main()
