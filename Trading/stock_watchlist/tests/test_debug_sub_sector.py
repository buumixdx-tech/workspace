"""深度调试:切到 126 后,直接调 showInlineNoteView,看是否成功。"""
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

        # 手动调 showInlineNoteView,看是否 work
        result = page.evaluate("""() => {
            const code = 'sh.603296';
            const stockRow = document.querySelector(`.stock-row[data-code="${code}"]`);
            const notes = state.notesCache[code];
            return {
                stockRowExists: !!stockRow,
                notesCache_has: notes ? notes.length : -1,
                notesCache_first_id: notes && notes.length > 0 ? notes[0].id : null,
                selectedStockCode: state.selectedStockCode,
            };
        }""")
        print(f"切到 126 后: {result}")

        # 直接调 showInlineNoteView
        page.evaluate("""() => {
            const code = 'sh.603296';
            const notes = state.notesCache[code];
            showInlineNoteView(code, notes[0]);
        }""")
        time.sleep(0.5)
        snap1 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            return {
                noteRowExists: !!note,
                noteMaxHeight: note ? note.style.maxHeight : null,
            };
        }""")
        print(f"手动调 showInlineNoteView 后 0.5s: {snap1}")

        time.sleep(1.0)
        snap2 = page.evaluate("""() => {
            const note = document.getElementById('note-row-sh.603296');
            return {
                noteRowExists: !!note,
                noteMaxHeight: note ? note.style.maxHeight : null,
            };
        }""")
        print(f"1.5s 后: {snap2}")

        print(f"\n=== console 日志 ({len(logs)} 条) ===")
        for log in logs[-15:]:
            print(f"  {log}")

        browser.close()


if __name__ == "__main__":
    main()
