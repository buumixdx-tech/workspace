import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from market.ck_client import ClickHouseClient
from datetime import datetime

def recover_concept_data():
    ck = ClickHouseClient()
    file_path = r"d:\WorkSpace\Trading\Akshare\data\akshare_data\concept_20260125_processed.xlsx"
    
    if not os.path.exists(file_path):
        print(f"❌ 找不到备份文件: {file_path}")
        return

    print(f"开始从 {file_path} 恢复数据...")
    
    try:
        # 1. 恢复 finance_concept_components (从 concepts_v2 页)
        # 期望字段: 板块名称, 代码 (或者是 股票代码)
        df_comp = pd.read_excel(file_path, sheet_name='concepts_v2')
        print(f"读取成分股数据: {len(df_comp)} 条")
        
        # 转换字段名以符合表结构
        # finance_concept_components: [concept_name, stock_code, update_time]
        comp_to_db = pd.DataFrame({
            'concept_name': df_comp['板块名称'],
            'stock_code': df_comp['代码'],
            'update_time': datetime.now()
        })
        ck.insert_df("finance_concept_components", comp_to_db)
        print("✅ finance_concept_components 恢复完成")

        # 2. 恢复 finance_concept_main (板块清单)
        # finance_concept_main: [name, source, update_time]
        unique_concepts = df_comp['板块名称'].unique()
        main_to_db = pd.DataFrame({
            'name': unique_concepts,
            'source': 'THS_EXCEL_BACKUP',
            'update_time': datetime.now()
        })
        ck.insert_df("finance_concept_main", main_to_db)
        print(f"✅ finance_concept_main 恢复完成, 共 {len(unique_concepts)} 个板块")

    except Exception as e:
        print(f"❌ 恢复失败: {e}")
    finally:
        ck.close()

if __name__ == "__main__":
    recover_concept_data()
