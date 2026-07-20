import time
import pandas as pd
import pyperclip
from pywinauto import Application, mouse
from pywinauto.keyboard import send_keys
from io import StringIO
import os

def run_batch_export(count=20):
    output_dir = "data/pywinauto"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"🚀 开启极速批量抓取 (Turbo Mode)，计划抓取 {count} 组数据...")

    try:
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        
        for i in range(1, count + 1):
            file_name = f"{i:03d}.csv"
            file_path = os.path.join(output_dir, file_name)
            
            main_win.set_focus()
            # 清空剪贴板标记位
            pyperclip.copy("WAITING")
            
            print(f"[{i}/{count}] 🚀 {file_name}", end=" ", flush=True)

            # 1. 右键菜单
            mouse.click(button='right', coords=(650, 750))
            time.sleep(0.4) # 缩减

            # 2. 键盘导航 (合在一起发送更快)
            send_keys("{UP 6}{RIGHT}{ENTER}")
            time.sleep(0.8) # 缩减弹窗等待

            # 3. 目标位置三连击 (根据反馈调整：第二下与第三下间隔1秒)
            mouse.click(button='left', coords=(1090, 730)) # 第1下
            time.sleep(0.2)
            mouse.click(button='left', coords=(1090, 730)) # 第2下
            time.sleep(1.0) # 用户要求：第二下第三下之间间隔1秒
            mouse.click(button='left', coords=(1090, 730)) # 第3下

            # 4. 剪贴板轮询 (最长等 1.5 秒，成功立刻跳出)
            content = ""
            for _ in range(15): 
                time.sleep(0.1)
                content = pyperclip.paste()
                if content and content != "WAITING" and len(content) > 100:
                    break
            
            if content and content != "WAITING":
                try:
                    df = pd.read_csv(StringIO(content), sep='\t')
                    df.to_csv(file_path, index=False, encoding='utf-8-sig')
                    print(f"OK ({len(df)}行)")
                except:
                    print("ERR(Format)")
            else:
                print("FAIL(Timeout)")

            # 5. 板块切换
            mouse.click(button='left', coords=(566, 566))
            time.sleep(0.2)
            send_keys("{DOWN}")
            time.sleep(0.3) # 给一点点刷新时间

        print(f"\n✨ 极速任务完成！")

    except Exception as e:
        print(f"\n❌ 中断: {e}")

if __name__ == "__main__":
    import sys
    # 支持从命令行传入次数，默认 20
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1 
    run_batch_export(loops)