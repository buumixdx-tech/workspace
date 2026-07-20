
import os
import pandas as pd
import glob
from datetime import datetime
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from stock_analysis.types import StockTask, AnalysisResult
from stock_analysis.processor1 import HotspotProcessor
from stock_analysis.processor2 import SectorHookProcessor
from stock_analysis.processor3 import HotspotMatchedProcessor
from stock_analysis.processor4_gemini import GeminiAnalysisProcessor
from stock_analysis.dify_client import MAX_WORKERS

def create_task_from_row(row) -> StockTask:
    """Factory method to convert Excel row to standard StockTask."""
    # 自动识别列名：兼容“股票名称”和“股票简称”
    name_val = row.get("股票名称", row.get("股票简称", row.get("名称", row.get("name", ""))))
    code_val = row.get("股票代码", row.get("code", ""))
    
    return StockTask(
        code=str(code_val).strip(),
        name=str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() != "nan" else "",
        total_mcap=row.get("总市值", 0),
        float_mcap=row.get("流通市值", 0),
        # Extra context for Processor 2
        context={
            "description": str(row.get("一句话描述", row.get("关联描述", ""))).strip()
        }
    )

def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="Stock Analysis Runner")
    parser.add_argument("--limit", type=int, help="Limit number of stocks to process for testing")
    parser.add_argument("--file", type=str, help="Specific input file path")
    parser.add_argument("--strategy", type=str, default="hotspot", help="Select strategy: hotspot | sector_hook | hotspot2 | gemini")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"Concurrency workers (default: {MAX_WORKERS} from config)")
    args = parser.parse_args()

    # 1. Setup paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(project_root, "data", "stock_analysis")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 2. Select Processor
    if args.strategy == "hotspot":
        processor = HotspotProcessor()
    elif args.strategy == "sector_hook":
        processor = SectorHookProcessor()
    elif args.strategy in ["hotspot2", "p3"]:
        processor = HotspotMatchedProcessor()
    elif args.strategy == "gemini":
        processor = GeminiAnalysisProcessor()
        # Enforce maximum concurrency limit for long Dify workflow
        if args.workers > 3:
            print("Notice: 'gemini' strategy detected. Force limiting workers to 3 to prevent API and network hang.")
            args.workers = 3
    else:
        print(f"Unknown strategy: {args.strategy}")
        return
        
    print(f"Using Strategy: {processor.name}, Workers: {args.workers}")

    # Generate dynamic filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    p_code = processor.code
    output_filename = f"result_{p_code}_{timestamp}.xlsx"
    
    if args.strategy == "gemini":
        output_dir = os.path.join(project_root, "data", "strategy_result", "reports")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    output_file = os.path.join(output_dir, output_filename)

    # 3. Find input file
    if args.file:
        input_file = args.file
    else:
        # Smart Default Based on Strategy
        if args.strategy == "gemini":
            # For Gemini analysis, default to reading the results of the recent strategy 4
            default_name = "market_analysis_s4.xlsx"
            input_file = os.path.join(project_root, "data", "strategy_result", default_name)
        elif args.strategy in ["sector_hook", "hotspot2", "p3"]:
            default_name = "hotspots_analysis.xlsx"
            input_file = os.path.join(output_dir, default_name)
        else:
            default_name = "stockpool.xlsx"
            input_file = os.path.join(output_dir, default_name)
    
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        return
        
    print(f"Using input file: {input_file}")
    
    # 4. Read Data
    df = pd.DataFrame()
    try:
        xls = pd.ExcelFile(input_file)
        sheets = xls.sheet_names
        sheet_to_read = next((s for s in ["Selected", "selected1", "selected2"] if s in sheets), sheets[0])
        df = pd.read_excel(input_file, sheet_name=sheet_to_read)
        # 预处理：向下填充空值（处理合并单元格的情况）
        if not df.empty:
            # 假设股票代码和股票名称在合并单元格中，需要填充
            cols_to_fill = [c for c in ["股票代码", "股票名称", "股票简称", "名称"] if c in df.columns]
            if cols_to_fill:
                df[cols_to_fill] = df[cols_to_fill].ffill()
        
        print(f"Reading {len(df)} stocks from sheet '{sheet_to_read}'")
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    # 5. Process (Concurrency)
    results_dict = {} # Use dict to store results by original index
    if args.limit:
        df = df.head(args.limit)
    
    total = len(df)
    print(f"Starting analysis with {args.workers} threads for {total} stocks...")
    
    tasks = [create_task_from_row(row) for _, row in df.iterrows()]
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Map future to its original index
        future_to_idx = {executor.submit(processor.process, tasks[i]): i for i in range(total)}
        
        for future in tqdm(as_completed(future_to_idx), total=total, unit="stock"):
            idx = future_to_idx[future]
            task = tasks[idx]
            try:
                results = future.result()
                if results:
                    results_dict[idx] = results
            except Exception as exc:
                print(f"\nError processing {task.code}: {exc}")
        
    # Re-assemble results in original order
    all_results = []
    for i in range(total):
        if i in results_dict:
            all_results.extend(results_dict[i])
        
    # 6. Save Results (Generic Wrapper)
    if all_results:
        # Get instructions from processor
        r_config = processor.report_config
        desired_columns = r_config.get("columns", [])
        col_widths = r_config.get("widths", {})
        merge_cols_count = r_config.get("merge_cols", 0)

        flat_rows = []
        for res in all_results:
            row_dict = {
                "股票代码": res.task.code,
                "股票名称": res.task.name,
                "总市值": res.task.total_mcap,
                "流通市值": res.task.float_mcap,
            }
            # Readable Cap conversion
            for k in ["总市值", "流通市值"]:
                val = row_dict.get(k, 0)
                if isinstance(val, (int, float)) and val > 0:
                    row_dict[k] = f"{val/100000000:.2f} 亿"

            # Merge structured_data from processor
            row_dict.update(res.structured_data)
            flat_rows.append(row_dict)

        df_out = pd.DataFrame(flat_rows)
        # Ensure only columns defined by processor are used, in order
        cols_to_use = [c for c in desired_columns if c in df_out.columns]
        df_out = df_out[cols_to_use]
        
        try:
            writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
            df_out.to_excel(writer, index=False, sheet_name='Analysis')
            
            workbook  = writer.book
            worksheet = writer.sheets['Analysis']
            
            # --- Common Formats ---
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            base_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
            desc_fmt = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})

            # Formatting
            for col_idx, col_name in enumerate(df_out.columns):
                # Apply Header Format
                worksheet.write(0, col_idx, col_name, header_fmt)
                # Apply Width (Generic)
                width = col_widths.get(col_name, 15)
                worksheet.set_column(col_idx, col_idx, width)
                # Apply Cell Format line-by-line
                for row_idx in range(len(df_out)):
                    val = df_out.iloc[row_idx, col_idx]
                    # Specific description format (guess by col_name or width > 40)
                    fmt = desc_fmt if width > 40 or "描述" in col_name else base_fmt
                    worksheet.write(row_idx + 1, col_idx, val, fmt)

            # Generic Merge Logic
            if merge_cols_count > 0:
                codes = df_out.iloc[:, 0].tolist() # Assume first col is indicator for merging
                curr = 0
                while curr < len(codes):
                    nxt = curr + 1
                    while nxt < len(codes) and codes[nxt] == codes[curr]:
                        nxt += 1
                    if nxt - curr > 1:
                        for col in range(min(merge_cols_count, len(df_out.columns))):
                            val = df_out.iloc[curr, col]
                            worksheet.merge_range(curr + 1, col, nxt, col, val, base_fmt)
                    curr = nxt 
            
            worksheet.set_default_row(25)
            writer.close()
            print(f"Analysis completed. Saved {len(df_out)} rows to {output_filename}")
        except Exception as e:
            print(f"Error saving result: {e}")
    else:
        print("No results to save.")
    
    total_duration = time.time() - start_time
    print(f"\n✨ All tasks finished in {total_duration:.2f} seconds.")

if __name__ == "__main__":
    main()
