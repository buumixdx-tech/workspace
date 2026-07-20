"""观测切板块 + 选股后 note-row 的 DOM 状态变化,定位消失根因。"""
import sys
import time
from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context()
        page = ctx.new_page()
        # 收集 console
        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda e: logs.append(f"[ERROR] {e}"))

        # 1) 加载首页
        page.goto("http://127.0.0.1:5181/")
        page.wait_for_selector("#sector-tree .sector-node", timeout=10000)
        time.sleep(2)

        # 找有笔记的板块 — 用 101 (800vDC) 含 sh.605111
        sectors = page.evaluate("""async () => {
            const r = await fetch('/api/sectors');
            return (await r.json()).data;
        }""")
        target = next((s for s in sectors if s['id'] == 101), sectors[0])
        print(f"目标板块: id={target['id']} name={target['name']}")

        # 点开 sector 101
        page.click(f'.sector-node[data-id="{target["id"]}"]')
        time.sleep(2)  # 等 tree + notes 端点回

        # 3) 看 notesCache
        nc = page.evaluate("Object.keys(state.notesCache)")
        print(f"  notesCache keys (前 5): {nc[:5]} ... 总 {len(nc)}")

        # 4) 点击第一只有笔记的股
        # 找一支有笔记的股
        target_code = next(iter(page.evaluate("Object.keys(state.notesCache)")), None)
        if not target_code:
            print("  该板块没笔记,无法继续测")
            return
        print(f"  目标股: {target_code}")

        # 触发 selectStock
        page.evaluate(f"ui.selectStock({target_code!r})")
        time.sleep(0.5)  # 等下拉动画

        # 5) 立即检测 note-row
        snap1 = page.evaluate(f"""() => {{
            const row = document.querySelector('.stock-row[data-code="{target_code}"]');
            const note = document.getElementById('note-row-{target_code}');
            return {{
                stockRowExists: !!row,
                noteRowExists: !!note,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
                notesCache: state.notesCache[{target_code!r}] ? state.notesCache[{target_code!r}].length : -1,
                selectedStockCode: state.selectedStockCode,
            }};
        }}""")
        print(f"  t=0.5s 快照: {snap1}")

        time.sleep(1.0)  # 等 1.5s
        snap2 = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{target_code}');
            return {{
                noteRowExists: !!note,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
                noteInDOM: note ? document.body.contains(note) : false,
            }};
        }}""")
        print(f"  t=1.5s 快照: {snap2}")

        time.sleep(2.0)  # 3.5s,经历一个 3s tick
        snap3 = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{target_code}');
            return {{
                noteRowExists: !!note,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
            }};
        }}""")
        print(f"  t=3.5s 快照: {snap3}")

        # 6) 切到板块 109 (PCB,parent,有 4 个子板块;sh.688625 在父板块直接股,
        #    sz.300321 / sh.688127 / sz.301678 在子板块 121 玻璃基板)
        next_sector = next((s for s in sectors if s['id'] == 109), sectors[0])
        print(f"\n  切到板块: id={next_sector['id']} name={next_sector['name']}")
        page.click(f'.sector-node[data-id="{next_sector["id"]}"]')
        time.sleep(3)
        page.evaluate("""() => {
            document.querySelectorAll('.sub-sector-children').forEach(c => {
                if (c.innerHTML === '') {
                    const block = c.closest('.sub-sector-block');
                    const sid = parseInt(block.dataset.sid);
                    const data = state.subSectorCache[sid];
                    if (data) {
                        c.innerHTML = renderSubChildren(data, new Set(), sid);
                        bindChildStockDrag(c, sid);
                    }
                }
            });
        }""")
        time.sleep(0.5)

        # 7) 选股 A: 父板块直接股 sh.688625 (对照组,应能正常下拉)
        new_code = 'sh.688625'
        print(f"  === A. 父板块直接股: {new_code} ===")
        page.evaluate(f"ui.selectStock({new_code!r})")
        time.sleep(0.5)
        snap = page.evaluate(f"""() => {{
            const note = document.getElementById('note-row-{new_code}');
            return {{
                noteRowExists: !!note,
                noteDisplay: note ? note.style.display : null,
                noteMaxHeight: note ? note.style.maxHeight : null,
            }};
        }}""")
        print(f"  A. 切板块 + 父板块股: {snap}")

        # 8) 选股 B: 子板块 121 玻璃基板内股 sz.300321 (有笔记,BUG 触发点)
        new_code2 = 'sz.300321'
        has_note = page.evaluate(f"{new_code2!r} in state.notesCache && state.notesCache[{new_code2!r}].length > 0")
        print(f"  === B. 子板块股: {new_code2}, 是否有笔记: {has_note} ===")
        if has_note:
            page.evaluate(f"ui.selectStock({new_code2!r})")
            time.sleep(0.5)
            snap = page.evaluate(f"""() => {{
                const note = document.getElementById('note-row-{new_code2}');
                return {{
                    noteRowExists: !!note,
                    noteDisplay: note ? note.style.display : null,
                    noteMaxHeight: note ? note.style.maxHeight : null,
                }};
            }}""")
            print(f"  B. 切板块 + 子板块股: {snap}")
            time.sleep(2.0)
            snap2 = page.evaluate(f"""() => {{
                const note = document.getElementById('note-row-{new_code2}');
                return {{
                    noteRowExists: !!note,
                    noteDisplay: note ? note.style.display : null,
                    noteMaxHeight: note ? note.style.maxHeight : null,
                }};
            }}""")
            print(f"  B. 切板块 + 子板块股 (3s 后): {snap2}")

            page.evaluate(f"ui.selectStock({new_code!r})")
            time.sleep(0.5)
            snap4 = page.evaluate(f"""() => {{
                const note = document.getElementById('note-row-{new_code}');
                const rows = document.querySelectorAll('.stock-row[data-code="{new_code}"]');
                return {{
                    noteRowExists: !!note,
                    noteDisplay: note ? note.style.display : null,
                    noteMaxHeight: note ? note.style.maxHeight : null,
                    stockRowCount: rows.length,
                }};
            }}""")
            print(f"  切板块后 0.5s 快照: {snap4}")

            time.sleep(1.0)
            snap5 = page.evaluate(f"""() => {{
                const note = document.getElementById('note-row-{new_code}');
                const rows = document.querySelectorAll('.stock-row[data-code="{new_code}"]');
                return {{
                    noteRowExists: !!note,
                    noteDisplay: note ? note.style.display : null,
                    noteMaxHeight: note ? note.style.maxHeight : null,
                    stockRowCount: rows.length,
                }};
            }}""")
            print(f"  切板块后 1.5s 快照: {snap5}")

            time.sleep(2.0)
            snap6 = page.evaluate(f"""() => {{
                const note = document.getElementById('note-row-{new_code}');
                const rows = document.querySelectorAll('.stock-row[data-code="{new_code}"]');
                return {{
                    noteRowExists: !!note,
                    noteDisplay: note ? note.style.display : null,
                    noteMaxHeight: note ? note.style.maxHeight : null,
                    stockRowCount: rows.length,
                }};
            }}""")
            print(f"  切板块后 3.5s 快照: {snap6}")

        # 8) 输出 console 日志
        print(f"\n  === console 日志 ({len(logs)} 条) ===")
        for log in logs[-30:]:
            print(f"    {log}")

        browser.close()


if __name__ == "__main__":
    main()
