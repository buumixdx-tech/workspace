import os
import sys
import pandas as pd
from datetime import datetime

# 将项目根目录添加到 sys.path 中，以便能找到 market 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.ck_client import ClickHouseClient

def import_sector_hooks(file_path: str):
    """
    1、stock_sector_hook.xlsx是源文件，其中含有股票与板块对应关系。
    A列股票代码、B列股票名称、D列挂钩板块、E列挂钩原因。
    2、从中提取必要的信息，填入ck中的存储特定股票于板块关系的表 (analysis_hot_topic_mapping)。
    """
    if not os.path.exists(file_path):
        print(f"❌ 错误: 找不到文件 {file_path}")
        return False

    print(f"📖 正在从 {file_path} 导入股票-板块挂钩关系...")

    try:
        # 1. 读取 Excel
        # 忽略 header，手动指定列索引 A(0), B(1), D(3), E(4)
        # 或者如果有表头，直接读。用户没说没表头，通常是有表头的。
        df = pd.read_excel(file_path)
        
        # 2. 预处理：向下填充 (处理合并单元格)
        # 强制按位置索引选择列以防列名变动
        # A:0 (代码), B:1 (名称), D:3 (板块), E:4 (原因)
        # 但由于 read_excel 默认第一行为 header，我们先检查列数
        if df.shape[1] < 5:
            print(f"❌ 错误: Excel 列数不足，期望至少 5 列。")
            return False

        # 映射列名（假设源文件有表头，如果没有表头建议加参数或使用 iloc）
        # 用户描述：A列股票代码、B列股票名称、D列挂钩板块、E列挂钩原因
        # 我们使用 iloc 获取这几列，避免列名不一致
        df_target = pd.DataFrame()
        df_target['stock_code'] = df.iloc[:, 0]
        df_target['stock_name'] = df.iloc[:, 1]
        df_target['concept_name'] = df.iloc[:, 3]
        df_target['reason'] = df.iloc[:, 4]

        # 向下填充代码和名称 (针对合并单元格)
        df_target[['stock_code', 'stock_name']] = df_target[['stock_code', 'stock_name']].ffill()

        # 剔除无效行 (板块名为空的行)
        df_target = df_target.dropna(subset=['concept_name'])
        
        # 3. 添加更新时间
        df_target['update_time'] = datetime.now()

        # 4. 写入 ClickHouse
        ck = ClickHouseClient()
        
        # 先清理旧数据吗？用户没说。为了安全性，这里采用追加模式。
        # 如果需要清理，可以执行 TRUNCATE TABLE analysis_hot_topic_mapping
        print(f"📝 准备写入 {len(df_target)} 条记录到 analysis_hot_topic_mapping...")
        
        ck.insert_df("analysis_hot_topic_mapping", df_target)
        ck.close()
        
        print(f"✅ 导入成功！")
        return True

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

if __name__ == "__main__":
    # 测试代码: 默认寻找当前目录或特定路径下的文件
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_file = os.path.join(project_root, "data", "stock_analysis", "stock_sector_hook.xlsx")
    
    if not os.path.exists(target_file):
        # 尝试当前目录
        target_file = "stock_sector_hook.xlsx"
        
    import_sector_hooks(target_file)
