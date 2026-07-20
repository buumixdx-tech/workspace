import time
import pyperclip
from pywinauto import Application
from pywinauto.keyboard import send_keys

def debug_menu_keys():
    print("🎯 正在准备寻找正确的导出快捷键...")
    try:
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        main_win.set_focus()
        time.sleep(1)
        
        # 记录尝试的序列
        # 方案1: T (很多版本导出是T) -> C (复制) 或 A (全部内容)
        # 方案2: 直接发送 Ctrl+Shift+S (有些版本的全局导出快捷键)
        
        test_sequences = [
            "{ESC}", # 先清理
            "T",     # 尝试 T
            "{DOWN 10}", # 尝试向下移
        ]

        print("🖱️ 右键点击并尝试按键序列...")
        main_win.click_input(button='right', coords=(250, 220))
        time.sleep(0.5)
        
        # 这里你可以手动观察，看哪条命令让菜单动了
        # 既然自动化的 D/A 没用，我们试试发送原生按键序列
        
        # 尝试常用代码：T -> A (导出 -> 全部)
        print("⌨️ 尝试发送 T...")
        send_keys("T")
        time.sleep(0.5)
        print("⌨️ 尝试发送 A...")
        send_keys("A")
        time.sleep(1)
        
        content = pyperclip.paste()
        if content and len(content) > 100:
            print("🚀 🎉 成功了！快捷键是 T 和 A (或类似组合)")
            return
        
        print("❌ T -> A 方案失败。")
        
    except Exception as e:
        print(f"出错: {e}")

if __name__ == "__main__":
    debug_menu_keys()
