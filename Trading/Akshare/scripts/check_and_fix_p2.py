
import sys
import os
import pandas as pd
import glob
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 将项目根目录添加到 sys.path 中，以便能找到 stock_analysis 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_analysis.types import StockTask
from stock_analysis.processor2 import SectorHookProcessor
from stock_analysis.dify_client import MAX_WORKERS

import argparse

def get_latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def main():
    start_time = time.time()
    
    # --- 参数解析 ---
    parser = argparse.ArgumentParser(description="P2 深度补重与缝合工具")
    parser.add_argument("--source", type=str, help="指定源文件名 (默认 hotspots_analysis.xlsx)")
    parser.add_argument("--result", type=str, help="指定对比的结果文件名 (不指定则自动找最新的)")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data", "stock_analysis")
    
    # 确定源文件
    source_name = args.source if args.source else "hotspots_analysis.xlsx"
    source_file = os.path.join(data_dir, source_name)
    
    # 确定结果文件
    if args.result:
        latest_result = os.path.join(data_dir, args.result)
    else:
        result_pattern = os.path.join(data_dir, "result_p2_*.xlsx")
        latest_result = get_latest_file(result_pattern)
    
    if not os.path.exists(source_file):
        print(f"❌ 错误：找不到源文件 {source_file}")
        return
    
    print(f"\n🚀 [阶段 1: 扫描与索引比对]")
    print(f"   源文件: {source_file}")
    
    # --- Phase 1: Scanning ---
    df_origin = pd.read_excel(source_file)
    # 探测描述列名
    desc_col = next((c for c in ["一句话描述", "关联描述"] if c in df_origin.columns), None)
    if not desc_col:
        print(f"   ❌ 错误: 源文件中未找到 '一句话描述' 或 '关联描述' 列。可用列: {list(df_origin.columns)}")
        return

    cols_to_fill = [c for c in ["股票代码", "股票名称"] if c in df_origin.columns]
    if cols_to_fill:
        df_origin[cols_to_fill] = df_origin[cols_to_fill].ffill()
    
    df_clean_source = df_origin.dropna(subset=[desc_col]).copy()
    num_total_sources = len(df_clean_source)
    
    existing_data_map = {}
    if latest_result:
        try:
            df_temp_res = pd.read_excel(latest_result)
            fill_res = [c for c in ["股票代码", "股票名称", "一句话描述"] if c in df_temp_res.columns]
            if fill_res:
                df_temp_res[fill_res] = df_temp_res[fill_res].ffill()
                
            for _, row in df_temp_res.iterrows():
                # 指纹比对：使用找到的 desc_col 或结果文件中的列
                res_desc_col = next((c for c in ["一句话描述", "关联描述"] if c in df_temp_res.columns), "一句话描述")
                fp = str(row.get("股票代码", "")).strip() + str(row.get(res_desc_col, "")).strip()
                if fp not in existing_data_map:
                    existing_data_map[fp] = []
                existing_data_map[fp].append(row.to_dict())
        except Exception as e:
            print(f"   ⚠️ 读取对比文件失败，将进行全量重扫: {e}")

    missing_tasks_dict = {}
    ordered_slots = []
    cached_count = 0

    for _, row in df_clean_source.iterrows():
        code = str(row.get("股票代码", "")).strip()
        desc = str(row.get(desc_col, "")).strip()
        name = str(row.get("股票名称", "")).strip()
        fp = code + desc
        
        if fp in existing_data_map:
            ordered_slots.append({"type": "cached", "fp": fp})
            cached_count += 1
        else:
            if fp not in missing_tasks_dict:
                task = StockTask(code=code, name=name, context={"description": desc})
                missing_tasks_dict[fp] = task
            ordered_slots.append({"type": "live", "fp": fp})

    num_missing = len(missing_tasks_dict)
    print(f"   📊 结果: 总描述条数 {num_total_sources} | 缓存命中 {cached_count} | 需补发 {num_missing} 条")

    # --- Phase 2: Execution ---
    all_missing_tasks = list(missing_tasks_dict.values())
    supplementary_results = {}
    success_count = 0
    fail_details = []

    if all_missing_tasks:
        print(f"\n📡 [阶段 2: Dify 批量补发执行]")
        processor = SectorHookProcessor()
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_fp = {executor.submit(processor.process, t): str(t.code)+str(t.context["description"]) for t in all_missing_tasks}
            
            for future in tqdm(as_completed(future_to_fp), total=len(all_missing_tasks), desc="补录进度", unit="task"):
                fp = future_to_fp[future]
                try:
                    res_list = future.result()
                    if res_list:
                        formatted = []
                        for r in res_list:
                            formatted.append({
                                "股票代码": r.task.code,
                                "股票名称": r.task.name,
                                "一句话描述": r.task.context.get("description", ""),
                                **r.structured_data
                            })
                        supplementary_results[fp] = formatted
                        success_count += 1
                    else:
                        supplementary_results[fp] = []
                        fail_details.append(f"{fp[:30]} (无结果返回)")
                except Exception as e:
                    supplementary_results[fp] = []
                    fail_details.append(f"{fp[:30]} (报错: {str(e)[:50]})")

        print(f"   ✅ 执行完毕: 成功 {success_count} 条 | 失败 {len(all_missing_tasks) - success_count} 条")
        if fail_details:
            print(f"   ❌ 失败明细 (前 5 条):")
            for detail in fail_details[:5]:
                print(f"      - {detail}")
    else:
        print(f"\n✨ [阶段 2: 跳过] 无需补发。")

    # --- Phase 3: Stitching ---
    print(f"\n🧵 [阶段 3: 数据缝合与顺序校验]")
    final_rows = []
    for slot in ordered_slots:
        fp = slot["fp"]
        if slot["type"] == "cached":
            final_rows.extend(existing_data_map[fp])
        else:
            if fp in supplementary_results:
                final_rows.extend(supplementary_results[fp])
    
    # --- Phase 4: Output ---
    if final_rows:
        df_final = pd.DataFrame(final_rows)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_filename = f"RECOVERED_P2_{timestamp}.xlsx"
        output_path = os.path.join(data_dir, output_filename)
        
        processor = SectorHookProcessor()
        save_to_stylized_excel(df_final, output_path, processor.report_config)
        
        print(f"   💾 完成: 最终结果已排序并保存至: {output_filename}")
    else:
        print("   ⚠️ 警告: 没有生成任何数据，请检查 Dify 连接。")

    total_duration = time.time() - start_time
    print(f"\n🌟 总任务耗时: {total_duration:.2f} 秒\n")


def save_to_stylized_excel(df, path, r_config):
    desired_columns = r_config.get("columns", [])
    col_widths = r_config.get("widths", {})
    merge_cols_count = r_config.get("merge_cols", 0)
    
    cols_to_use = [c for c in desired_columns if c in df.columns]
    df = df[cols_to_use]
    
    writer = pd.ExcelWriter(path, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    
    header_fmt = workbook.add_format({'bold':True, 'bg_color':'#D7E4BC', 'border':1, 'align':'center', 'valign':'vcenter'})
    base_fmt = workbook.add_format({'border':1, 'align':'center', 'valign':'vcenter', 'text_wrap':True})
    desc_fmt = workbook.add_format({'border':1, 'align':'left', 'valign':'vcenter', 'text_wrap':True, 'font_size':9})
    
    for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, col_name, header_fmt)
        width = col_widths.get(col_name, 15)
        worksheet.set_column(col_idx, col_idx, width)
        for row_idx in range(len(df)):
            val = df.iloc[row_idx, col_idx]
            fmt = desc_fmt if width >= 40 or "描述" in col_name or "原因" in col_name else base_fmt
            worksheet.write(row_idx + 1, col_idx, val, fmt)
            
    if merge_cols_count > 0:
        fprints = (df.iloc[:, 0].astype(str) + df.iloc[:, 2].astype(str)).tolist()
        curr = 0
        while curr < len(fprints):
            nxt = curr + 1
            while nxt < len(fprints) and fprints[nxt] == fprints[curr]:
                nxt += 1
            if nxt - curr > 1:
                for col in range(min(merge_cols_count, len(df.columns))):
                    val = df.iloc[curr, col]
                    worksheet.merge_range(curr + 1, col, nxt, col, val, base_fmt)
            curr = nxt
            
    worksheet.set_default_row(25)
    writer.close()

if __name__ == "__main__":
    main()
