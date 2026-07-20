import pandas as pd
import os

def process_concept_excel():
    # Define file paths
    input_file = r"d:\WorkSpace\Trading\Akshare\data\akshare_data\concept_20260125.xlsx"
    output_file = r"d:\WorkSpace\Trading\Akshare\data\akshare_data\concept_20260125_processed.xlsx"

    if not os.path.exists(input_file):
        print(f"找不到输入文件: {input_file}")
        return

    print(f"正在读取文件: {input_file}...")
    try:
        # 1. 读取 "concepts" 页
        df_concepts = pd.read_excel(input_file, sheet_name='concepts')
        print(f"成功读取 'concepts' 页，共 {len(df_concepts)} 条数据。")
    except Exception as e:
        print(f"读取 Excel 出错: {e}")
        return

    # 2. 板块统计
    # 统计每个板块的成分股个数
    print("正在进行板块统计...")
    # 假设列名为 '板块名称'
    if '板块名称' in df_concepts.columns:
        df_stats = df_concepts.groupby('板块名称').size().reset_index(name='成分股个数')
        # 按个数降序排列
        df_stats = df_stats.sort_values(by='成分股个数', ascending=False)
        print(f"统计完成，共计 {len(df_stats)} 个板块。")
    else:
        print("错误: 'concepts' 页中未找到 '板块名称' 列。")
        return

    # 3. 过滤大板块并创建 concepts_v2
    print("正在创建 concepts_v2 (过滤成员超过 1000 的板块)...")
    # 找出成员数 <= 1000 的板块
    valid_boards = df_stats[df_stats['成分股个数'] <= 1000]['板块名称'].tolist()
    # 过滤原始数据
    df_concepts_v2 = df_concepts[df_concepts['板块名称'].isin(valid_boards)]
    print(f"concepts_v2 创建完成，过滤后剩余 {len(df_concepts_v2)} 条记录，共 {len(valid_boards)} 个板块。")

    # 4. 保存到新的 Excel 文件
    print(f"正在保存处理后的数据到: {output_file}...")
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # 完整信息页
            df_concepts.to_excel(writer, sheet_name='concepts', index=False)
            # 过滤后的信息页
            df_concepts_v2.to_excel(writer, sheet_name='concepts_v2', index=False)
            # 板块统计页
            df_stats.to_excel(writer, sheet_name='板块统计', index=False)
        print("保存成功！")
    except Exception as e:
        print(f"保存 Excel 出错: {e}")

if __name__ == "__main__":
    process_concept_excel()
