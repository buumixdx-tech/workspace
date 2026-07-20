import time
from pywinauto import Application
import os

def probe_context_menu():
    print("🚀 正在探测同花顺右键菜单结构...")
    try:
        # 1. 连接并置顶
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        main_win.set_focus()
        time.sleep(1)
        
        # 2. 模拟右键点击
        print("🖱️ 执行右键点击 (250, 220)...")
        main_win.click_input(button='right', coords=(250, 220))
        time.sleep(1)
        
        # 3. 尝试寻找弹出菜单窗口
        # Context menus are often top-level windows with class #32768
        try:
            menu_app = Application(backend="win32").connect(active_only=True)
            # 尝试获取当前活动窗口，这通常就是刚弹出的菜单
            popup = menu_app.top_window()
            print(f"✅ 捕获到弹出窗口: {popup.texts()}")
            
            # 打印该窗口下所有的子控件文字（看看有没有“数据导出”）
            print("\n--- 菜单项内容探测 ---")
            for child in popup.descendants():
                text = child.window_text()
                if text:
                    print(f"  - {text}")
                    
        except Exception as e:
            print(f"无法抓取菜单文字: {e}")
            print("这说明同花顺使用了非标准绘制的菜单。")

    except Exception as e:
        print(f"失败: {e}")

if __name__ == "__main__":
    probe_context_menu()
