import json
import os
from datetime import datetime
from market.ck_client import ClickHouseClient

def generate_concept_dict():
    """
    生成或同步每日板块字典
    逻辑：检查 ClickHouse 中今日是否已生成字典 -> (若无) 聚合生成 -> 导出 JSON
    """
    ck = ClickHouseClient()
    today = datetime.now().date()
    # today_str = today.strftime('%Y-%m-%d')
    
    # 1. 检查今日是否已存在
    check_sql = f"SELECT count() as cnt FROM dict_concept_mapping WHERE update_date = '{today}'"
    res = ck.query_df(check_sql)
    exists = res['cnt'].iloc[0] > 0 if not res.empty else False
    
    if not exists:
        print(f"[{today}] 字典未生成，正在从视图聚合...")
        
        # 2. 插入新的一版字典
        # 核心：必须按 concept_name 排序以保证 ID 的确定性
        insert_sql = f"""
        INSERT INTO dict_concept_mapping (concept_id, concept_name, update_date)
        SELECT 
            rowNumberInAllBlocks() - 1 as concept_id,
            concept_name,
            '{today}'
        FROM (
            SELECT DISTINCT concept_name 
            FROM view_selected_concept_list 
            ORDER BY concept_name
        )
        """
        try:
            ck.command(insert_sql)
            print(f"[{today}] 字典生成并入库成功。")
        except Exception as e:
            print(f"生成字典失败: {e}")
            return

    else:
        print(f"[{today}] 字典已存在，跳过生成。")

    # 3. 导出为 JSON (始终执行，确保本地文件是最新的)
    export_sql = f"SELECT concept_name, concept_id FROM dict_concept_mapping WHERE update_date = '{today}' ORDER BY concept_id"
    df = ck.query_df(export_sql)
    
    mapping = dict(zip(df['concept_name'], df['concept_id']))
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "concept_dict.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
        
    print(f"[{today}] 字典已导出至本地: {output_path} (共 {len(mapping)} 个)")

if __name__ == "__main__":
    generate_concept_dict()
