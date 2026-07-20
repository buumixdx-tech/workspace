import time
import pandas as pd
import pyperclip
from pywinauto import Application
from pywinauto.keyboard import send_keys
import os

def get_ths_data_via_ui():
    print("🚀 正在尝试连接同花顺客户端...")
    
    try:
        # 尝试连接
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        
        # 记录标题
        titles = main_win.texts()
        print(f"✅ 找到窗口: {titles}")
        
        # 唤起并置顶
        main_win.set_focus()
        time.sleep(1)
        
        # 尝试通过点击确保激活
        # 如果是 "板块热点"，说明已经在我们要的页面了，直接点中心
        print("🖱️ 正在模拟点击以确保列表聚焦...")
        main_win.click_input() 
        time.sleep(0.5)
        
        # 发送 ESC 确保清除之前的输入状态
        print("⌨️ 清除状态 (ESC)...")
        send_keys("{ESC}")
        time.sleep(0.5)

        # 看看是否需要跳转
        if "板块" not in titles[0]:
            print("⌨️ 正在尝试跳转 (.400)...")
            send_keys(".400{ENTER}")
            time.sleep(3)
        
        # 执行复制
        print("📝 正在尝试复制 (Ctrl+A, Ctrl+C)...")
        pyperclip.copy("") # 清空
        
        # 分步骤按，增加间隔
        send_keys("^a") 
        time.sleep(0.5)
        send_keys("^c")
        
        print("⏳ 等待剪贴板数据...")
        for i in range(5):
            time.sleep(0.5)
            content = pyperclip.paste()
            if content and len(content) > 10:
                print(f"🎉 成功获取数据！字节数: {len(content)}")
                break
        else:
            print("❌ 依然未能获取数据。")
            return

        # 解析
        from io import StringIO
        # 同花顺复制的内容通常是 \t 分隔，或者含有表头
        df = pd.read_csv(StringIO(content), sep='\t')
        
        print("\n--- 提取字段 ---")
        print(df.columns.tolist())
        print("\n--- 数据预览 ---")
        print(df.head(5).to_string())
        
        output_path = "temp/ths_ui_test_result.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n💾 已保存到: {output_path}")

    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    get_ths_data_via_ui()
