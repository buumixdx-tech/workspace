import time
from pywinauto import Application, mouse
import os

def test_hard_click():
    print("🚀 正在通过系统级坐标 (而非相对坐标) 测试点击...")
    try:
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        main_win.set_focus()
        time.sleep(1)
        
        # 获取窗口位置
        rect = main_win.rectangle()
        print(f"窗口范围: Left={rect.left}, Top={rect.top}, Right={rect.right}, Bottom={rect.bottom}")
        
        # 计算绝对坐标 (基于你给的相对坐标 650, 750)
        # 注意：650, 750 如果是相对坐标，我们需要加上窗口原点
        # 如果 650, 750 是你从屏幕左上角量的绝对坐标，我直接用
        target_x = 650
        target_y = 750
        
        print(f"🖱️ 鼠标正向坐标 ({target_x}, {target_y}) 移动...")
        # 尝试使用最高优先级的 mouse 库直接操作
        mouse.click(button='right', coords=(target_x, target_y))
        
        time.sleep(3) # 停 3 秒，让你看看弹出来没
        print("检查屏幕：右键菜单弹出来了吗？")
        
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    test_hard_click()
