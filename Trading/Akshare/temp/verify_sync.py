import os
import sys
import pandas as pd
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market.ck_client import ClickHouseClient

def check_sync_accuracy():
    ck = ClickHouseClient()
    concept_list_path = "data/pywinauto/Table.xls"
    data_dir = "data/pywinauto"
    
    # 1. 加载名录
    concept_names = []
    for enc in ['gb18030', 'utf-8-sig', 'gbk']:
        try:
            with open(concept_list_path, 'r', encoding=enc) as f:
                concept_names = [line.strip() for line in f.readlines() if line.strip()]
                if len(concept_names) > 0: break
        except:
            continue

    # 2. 抽样检查 (首、中、尾)
    samples = [0, 100, 389] 
    
    print("📋 开始随机同步精度抽查...")
    print("=" * 50)

    for i in samples:
        c_name = concept_names[i]
        file_name = f"{i+1:03d}.csv"
        file_path = os.path.join(data_dir, file_name)
        
        # 解析 CSV 中的有效代码 (过滤北交所，转换格式)
        csv_df = None
        for inner_enc in ['utf-8-sig', 'gb18030', 'gbk']:
            try:
                csv_df = pd.read_csv(file_path, encoding=inner_enc)
                if '代码' in csv_df.columns: break
            except:
                continue

        if csv_df is None:
            print(f"   ❌ 无法读取文件: {file_name}")
            continue

        csv_codes = set()
        for raw in csv_df['代码'].astype(str):
            raw = raw.strip()
            std = ""
            if len(raw) >= 8 and raw[:2].isalpha():
                market = raw[:2].lower()
                if market != 'bj': std = f"{market}.{raw[2:]}"
            elif len(raw) == 6 and raw.isdigit():
                if raw.startswith('6'): std = f"sh.{raw}"
                elif raw.startswith(('0', '3')): std = f"sz.{raw}"
            if std: csv_codes.add(std)

        # 查询数据库中的记录
        db_df = ck.query_df(f"SELECT stock_code FROM finance_concept_components WHERE concept_name = '{c_name}'")
        db_codes = set(db_df['stock_code'].tolist())

        # 对比
        missing = csv_codes - db_codes
        extra = db_codes - csv_codes
        
        print(f"📍 板块: {c_name} (对应文件: {file_name})")
        print(f"   CSV有效记录: {len(csv_codes)} | DB记录: {len(db_codes)}")
        
        if len(missing) == 0 and len(extra) == 0:
            print("   ✅ 结果: 完全一致")
        else:
            if missing: print(f"   ❌ DB 缺失: {missing}")
            if extra: print(f"   ❌ DB 多余: {extra}")
        print("-" * 50)

    ck.close()

if __name__ == "__main__":
    check_sync_accuracy()
