import time
import pandas as pd
import pyperclip
from pywinauto import Application, mouse
from pywinauto.keyboard import send_keys
from io import StringIO
import os

def auto_export_ths_v4():
    print(f"🚀 正在启动全自动数据导出 (V4 - 坐标盲操模式)...")
    
    try:
        # 1. 连接并置顶同花顺
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        main_win.set_focus()
        time.sleep(1)
        
        # 2. 触发右键菜单 (根据之前的成功经验)
        print("🖱️ 正在右键点击列表区域 (600, 450)...") 
        # 这里我微调一下，点击稍微靠上的位置确保能点中一行
        mouse.click(button='right', coords=(650, 750)) 
        time.sleep(1)
        
        # 3. 导航到数据导出并打开对话框
        print("⌨️ 执行键盘序列: {UP 6} -> {RIGHT} -> {ENTER}...")
        send_keys("{UP 6}") 
        time.sleep(0.5)
        send_keys("{RIGHT}")
        time.sleep(0.5)
        send_keys("{ENTER}") # 此时应该弹出了“数据导出”对话框
        print("⏳ 等待导出对话框弹出...")
        time.sleep(2)
        
        # 4. 执行你指定的最后点击动作
        target_click_pos = (1090, 730)
        print(f"🖱️ 并在目标位置 {target_click_pos} 执行左击 3 次...")
        for i in range(3):
            print(f"  - 点击 {i+1}/3...")
            mouse.click(button='left', coords=target_click_pos)
            time.sleep(1)
            
        print("⏳ 等待数据进入剪贴板...")
        time.sleep(2)
        
        # 5. 读取并解析
        content = pyperclip.paste()
        if not content or len(content) < 100:
            print("❌ 最终读取失败：剪贴板依然为空。")
            # 调试：看看剪贴板到底有什么
            # print(f"DEBUG CLIP: {content[:50]}")
            return
            
        print(f"🎉 成功抓取！得到数据量: {len(content)} 字节")
        df = pd.read_csv(StringIO(content), sep='\t')
        print(f"✅ 解析成功: {len(df)} 行。")
        
        output_path = "temp/ths_automated_final.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"💾 数据已备份至: {output_path}")

    except Exception as e:
        print(f"❌ 出错: {e}")

if __name__ == "__main__":
    auto_export_ths_v4()
