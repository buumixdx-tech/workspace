import time
import pandas as pd
import pyperclip
from pywinauto import Application
from pywinauto.keyboard import send_keys
from io import StringIO
import os

def auto_export_ths_v3():
    print(f"🚀 正在启动全自动数据导出 (V3 - 盲操模式)...")
    
    try:
        # 1. 连接同花顺
        app = Application(backend="win32").connect(path="hexin.exe")
        main_win = app.window(title_re=".*同花顺.*")
        main_win.set_focus()
        time.sleep(1)
        
        # 2. 定位右键点击位置 (用户指定坐标: 650, 750)
        # 确保你在 1920x1080 且窗口最大化状态下
        print("🖱️ 正在右键点击列表区域 (650, 750)...")
        main_win.click_input(button='right', coords=(650, 750))
        time.sleep(1)
        
        # 3. 模拟按键序列：上6下 -> 右1下 -> 回车
        print("⌨️ 正在执行盲操序列: {UP 6} -> {RIGHT} -> {ENTER}...")
        send_keys("{UP 6}") # 向上 6 下移动到数据导出
        time.sleep(0.5)
        send_keys("{RIGHT}") # 进入子菜单
        time.sleep(0.5)
        send_keys("{ENTER}") # 全部导出到粘贴板
        
        print("⏳ 等待剪贴板数据同步...")
        time.sleep(2) 
        
        # 4. 读取剪贴板
        content = pyperclip.paste()
        if not content or len(content) < 100:
            print("❌ 导出失败：剪贴板内容不足，请检查窗口聚焦或坐标是否正确。")
            return
            
        print(f"🎉 成功！字节数: {len(content)}")
        
        # 5. 解析并打印预览
        df = pd.read_csv(StringIO(content), sep='\t')
        print(f"\n✅ 解析成功: 共有 {len(df)} 个板块数据。")
        print("\n--- 顶部数据预览 ---")
        print(df[['板块名称', '涨幅', '主力金额']].head(5).to_string(index=False))
        
        # 保存备份
        output_path = "temp/auto_ths_v3_result.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n💾 数据已存入: {output_path}")

    except Exception as e:
        print(f"❌ 自动化过程出错: {e}")

if __name__ == "__main__":
    auto_export_ths_v3()
