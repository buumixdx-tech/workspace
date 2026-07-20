import pandas as pd
import pyperclip
from io import StringIO

def test_clipboard_parse():
    print("⏳ 正在尝试从剪贴板解析数据...")
    content = pyperclip.paste()
    
    if not content:
        print("❌ 剪贴板目前为空，请先在同花顺里 Ctrl+C 复制列表。")
        return
        
    try:
        # 同花顺复制出来通常是 Tab 分隔
        df = pd.read_csv(StringIO(content), sep='\t')
        print(f"🎉 成功！解析到 {len(df)} 行数据。")
        print("\n--- 字段名 ---")
        print(df.columns.tolist())
        print("\n--- 前3行数据 ---")
        print(df.head(3).to_string())
        
        # 存入 CSV 备查
        df.to_csv("temp/manual_clip_test.csv", index=False, encoding='utf-8-sig')
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        print("内容预览:", content[:100])

if __name__ == "__main__":
    test_clipboard_parse()
