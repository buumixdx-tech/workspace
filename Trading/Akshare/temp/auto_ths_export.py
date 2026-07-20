import time
import pandas as pd
import pyperclip
from pywinauto import Application
from pywinauto.keyboard import send_keys
from io import StringIO
import os

def auto_export_ths():
    print("🚀 正在启动全自动数据导出...")
    
    try:
        # 1. 连接同花顺
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        main_win.set_focus()
        time.sleep(1)
        
        # 2. 定位右键点击位置
        # 根据截图，列表起始位约在窗口左上角偏移 (250, 220) 处
        # 我们点击这个位置来触发右键菜单
        print("🖱️ 正在模拟右键点击列表区域...")
        main_win.click_input(button='right', coords=(250, 220))
        time.sleep(1)
        
        # 3. 模拟快捷键操作右键菜单
        # 同花顺菜单中：'D' 通常对应 '数据导出'
        print("⌨️ 正在选择：数据导出 (D)...")
        send_keys("D")
        time.sleep(0.5)
        
        # 'A' 通常对应 '全部导出到粘贴板'
        print("⌨️ 正在选择：导出到粘贴板 (A)...")
        send_keys("A")
        time.sleep(1.5) # 等待数据进入剪贴板
        
        # 4. 读取剪贴板
        content = pyperclip.paste()
        if not content or len(content) < 100:
            print("❌ 导出失败：剪贴板内容不足，可能是右键菜单未正常弹出或快捷键冲突。")
            return
            
        print(f"🎉 成功抓取数据！字节数: {len(content)}")
        
        # 5. 解析并打印预览
        df = pd.read_csv(StringIO(content), sep='\t')
        print(f"\n✅ 解析成功: 共有 {len(df)} 个板块数据。")
        print("\n--- 板块前5名 ---")
        print(df[['板块名称', '涨幅', '主力净量', '主力金额']].head(5).to_string(index=False))
        
        # 保存
        output_path = "temp/auto_ths_result.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n💾 数据已存入: {output_path}")

    except Exception as e:
        print(f"❌ 自动化过程出错: {e}")

if __name__ == "__main__":
    auto_export_ths()
