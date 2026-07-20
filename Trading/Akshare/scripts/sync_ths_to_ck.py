import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from market.ck_client import ClickHouseClient
from datetime import datetime

def sync_data():
    ck = ClickHouseClient()
    concept_list_path = "data/pywinauto/Table.xls"
    data_dir = "data/pywinauto"
    
    if not os.path.exists(concept_list_path):
        print(f"❌ 找不到板块列表文件: {concept_list_path}")
        return

    # 1. 加载名录
    concept_names = []
    try:
        found_enc = None
        for enc in ['utf-8-sig', 'gb18030', 'gbk']:
            try:
                with open(concept_list_path, 'r', encoding=enc) as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                    if len(lines) > 0:
                        # 检查第一行是否是表头
                        if lines[0] in ["名称", "板块名称", "Name"]:
                            concept_names = lines[1:]
                        else:
                            concept_names = lines
                        found_enc = enc
                        break
            except:
                continue
        
        if not concept_names:
            print("❌ 无法读取 Table.xls 或内容为空。")
            return
            
        print(f"📂 已通过 {found_enc} 加载 {len(concept_names)} 个板块名录")
    except Exception as e:
        print(f"❌ 读取 Table.xls 出错: {e}")
        return

    main_records = []
    component_records = []
    now = datetime.now()

    # 2. 扫描并排序文件
    files = [f for f in os.listdir(data_dir) if f.endswith('.csv') and f[0].isdigit()]
    files.sort(key=lambda x: int(x.split('.')[0]))
    print(f"🔍 发现 {len(files)} 个成分股文件，开始处理...")

    processed_count = 0
    for file_name in files:
        idx_str = file_name.split('.')[0]
        try:
            # 文件名 001.csv 对应列表第 0 个
            idx = int(idx_str) - 1 
            if idx < 0 or idx >= len(concept_names):
                print(f"  ⚠️ 跳过 {file_name}: 索引 {idx+1} 超出名录范围 (1-{len(concept_names)})")
                continue
                
            c_name = concept_names[idx]
            file_path = os.path.join(data_dir, file_name)
            
            # 读取成分股
            try:
                # 自动检测编码尝试读取
                df = None
                for inner_enc in ['utf-8-sig', 'gb18030', 'gbk']:
                    try:
                        df = pd.read_csv(file_path, encoding=inner_enc)
                        if '代码' in df.columns: break
                    except:
                        continue
                
                if df is None or '代码' not in df.columns:
                    print(f"  ❌ 文件 {file_name} 格式不正确或无法读取")
                    continue
                
                # 记录板块基础信息
                main_records.append({'name': c_name, 'source': 'THS_LOCAL', 'update_time': now})

                # 解析代码
                for _, row in df.iterrows():
                    raw_code = str(row['代码']).strip()
                    if not raw_code: continue
                    
                    std_code = ""
                    # 情况 A: 带前缀 (SZ000001)
                    if len(raw_code) >= 8 and raw_code[:2].isalpha():
                        market = raw_code[:2].lower()
                        pure_code = raw_code[2:]
                        if market == 'bj': continue # 过滤北交所
                        std_code = f"{market}.{pure_code}"
                    # 情况 B: 纯 6 位数字 (600000)
                    elif len(raw_code) == 6 and raw_code.isdigit():
                        if raw_code.startswith('6'): market = 'sh'
                        elif raw_code.startswith(('0', '3')): market = 'sz'
                        else: continue # 其他默认过滤（如北交所 8/4/9）
                        std_code = f"{market}.{raw_code}"
                    
                    if std_code:
                        component_records.append({
                            'concept_name': c_name,
                            'stock_code': std_code,
                            'update_time': now
                        })
                
                processed_count += 1
                if processed_count % 50 == 0:
                    print(f"  已处理 {processed_count}/{len(files)}...")

            except Exception as inner_e:
                print(f"  ❌ 读取文件 {file_name} 失败: {inner_e}")

        except Exception as e:
            print(f"  ❌ 处理 {file_name} 出错: {e}")

    # 3. 批量入库
    if main_records:
        print(f"\n✅ 处理完成。正在入库 {len(main_records)}/390 个板块，共 {len(component_records)} 条映射...")
        try:
            # 开启事务性清理
            ck.command("TRUNCATE TABLE finance_concept_main")
            ck.command("TRUNCATE TABLE finance_concept_components")
            
            df_main = pd.DataFrame(main_records).drop_duplicates('name')
            ck.insert_df("finance_concept_main", df_main)
            
            df_comp = pd.DataFrame(component_records).drop_duplicates(['concept_name', 'stock_code'])
            ck.insert_df("finance_concept_components", df_comp)
            
            print(f"🚀 同步成功！")
        except Exception as db_e:
            print(f"❌ 数据库写入失败: {db_e}")
    else:
        print("⚠️ 未发现有效数据，未执行入库。")

    ck.close()
    print("\n✨ 本地同步完成！")

if __name__ == "__main__":
    sync_data()
