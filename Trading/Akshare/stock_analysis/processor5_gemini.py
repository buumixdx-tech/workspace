import os
import glob
import pandas as pd
import toml
import requests
import json
import time
import argparse
import threading
from tqdm import tqdm
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

pbar = None  # Global progress bar instance

def get_dify_config():
    config_path = r"d:\WorkSpace\Trading\Akshare\config.toml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = toml.load(f).get("dify", {})
    return config.get("processor5_gemini_api_key"), config.get("base_url", "http://localhost:5001"), config.get("max_workers", 8)

def call_processor5_gemini(stock_code, stock_name, hotspots, api_key, base_url, report_content=None):
    api_url = f"{base_url}/v1/workflows/run"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    inputs_dict = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "hotspots": hotspots
    }
    if report_content:
        inputs_dict["report"] = report_content
        
    payload = {
        "inputs": inputs_dict,
        "response_mode": "blocking",
        "user": "processor5-module"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 1200 seconds timeout for long-running gemini workflow
            response = requests.post(api_url, headers=headers, json=payload, timeout=(10, 1200))
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "failed":
                return False, f"Dify Error: {result.get('error', 'Unknown Error')}"
                
            if result.get("data") and result["data"].get("outputs"):
                outputs = result["data"]["outputs"]
                if "json_data" in outputs:
                    json_str_or_dict = outputs["json_data"]
                    md_text = outputs.get("markdown_report")
                    
                    parsed_json = {}
                    if isinstance(json_str_or_dict, dict):
                        parsed_json = json_str_or_dict
                    elif isinstance(json_str_or_dict, str):
                        cleaned = json_str_or_dict.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        elif cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        try:
                            parsed_json = json.loads(cleaned.strip())
                        except json.JSONDecodeError as e:
                            print(f"JSON Parsing Error: {e}. Raw: {cleaned}")
                    
                    parsed_json["report_md"] = md_text
                    return True, parsed_json
                else:
                    raw_output = outputs.get("text", outputs.get("result", list(outputs.values())[0] if outputs else ""))
                    
                    if isinstance(raw_output, str):
                        cleaned = raw_output.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        elif cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        
                        try:
                            return True, json.loads(cleaned.strip())
                        except json.JSONDecodeError as e:
                            return False, f"Failed to parse JSON string: {e}\nRaw output: {raw_output}"
                    elif isinstance(raw_output, dict):
                        return True, raw_output
                    else:
                        return False, f"Unexpected Dify output format: {type(raw_output)}"
            else:
                return False, f"Invalid Dify response format: {result}"
                
        except json.JSONDecodeError as e:
            return False, f"Failed to parse inner JSON string: {e}"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                time.sleep(10)
                continue
            return False, f"HTTP Error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            return False, f"Request failed: {str(e)}"
            
    return False, "Max retries exceeded"


def load_last_log(p5_dir, excel_filename):
    """加载与 Excel 文件名关联的执行日志"""
    log_name = f"{os.path.splitext(excel_filename)[0]}.log.json"
    log_path = os.path.join(p5_dir, "logs", log_name)
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取日志文件失败: {e}")
        return None


def save_log(p5_dir, excel_filename, log_data):
    """保存与 Excel 文件名关联的执行日志"""
    log_name = f"{os.path.splitext(excel_filename)[0]}.log.json"
    log_dir = os.path.join(p5_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_path = os.path.join(log_dir, log_name)
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"执行日志已保存至: {log_path}")
    except Exception as e:
        print(f"保存日志文件失败: {e}")


def main(limit=None, retry=False):
    api_key, base_url, max_workers_config = get_dify_config()
    if not api_key:
        print("API Key for processor5_gemini not found in config.toml")
        return
    
    # Use max_workers from config.toml directly
    max_workers = max_workers_config if max_workers_config else 3

    stock_analysis_dir = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis"
    p5_dir = os.path.join(stock_analysis_dir, "p5")
    if not os.path.exists(p5_dir):
        os.makedirs(p5_dir)
    
    # 确保 log 目录存在
    log_dir = os.path.join(p5_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    hotspots_path = r"d:\WorkSpace\Trading\Akshare\docs\hotspots2.txt"
    if not os.path.exists(hotspots_path):
        print(f"Hotspots file not found at {hotspots_path}")
        return
        
    with open(hotspots_path, "r", encoding="utf-8") as f:
        hotspots_text = f.read()

    # Find the latest stockpool_p5_*.xlsx by version date in filename
    search_pattern = os.path.join(stock_analysis_dir, "stockpool_p5_*.xlsx")
    files = glob.glob(search_pattern)
    if not files:
        print("No stockpool_p5_*.xlsx files found.")
        return
        
    latest_file = max(files, key=os.path.basename)
    print(f"Using stock pool file: {latest_file}")
    
    df_full = pd.read_excel(latest_file)
    overall_total = len(df_full)
    code_col = df_full.columns[0]
    name_col = df_full.columns[1]
    mcap_col = next((c for c in df_full.columns if "调整后流通市值" in str(c)), None)

    # --- 重试模式 ---
    prev_success_list = []  # 上次成功的条目（重试模式下保留）
    excel_basename = os.path.basename(latest_file)
    if retry:
        last_log = load_last_log(p5_dir, excel_basename)
        if not last_log or not last_log.get("failed"):
            print("🎉 该文件（" + excel_basename + "）上次执行没有失败条目，无需重试。")
            return
        
        failed_codes = {item["code"] for item in last_log["failed"]}
        prev_success_list = last_log.get("success", [])
        
        print(f"🔄 断点续传：检测到上次有 {len(failed_codes)} 个条目未完成")
        print(f"📊 当前总进度: {len(prev_success_list)}/{overall_total} ({len(prev_success_list)/overall_total*100:.1f}%)")
        
        df = df_full[df_full[code_col].astype(str).isin(failed_codes)]
        
        if df.empty:
            print("在当前股票池中未找到上次失败的条目。")
            return
    elif limit:
        print(f"🧪 测试模式：限制处理前 {limit} 只股票")
        df = df_full.head(limit)
    else:
        df = df_full
    
    # Process inputs
    total = len(df)
    print(f"🚀 开始执行：本次需处理 {total} 个条目")
    
    results = []
    success_list = []
    failed_list = []
    log_lock = threading.Lock()
    
    def process_row(index, row):
        stock_code = str(row[code_col])
        stock_name = str(row[name_col])
        float_mcap = row[mcap_col] if mcap_col else 0
        
        # Get rid of . in stock code (e.g. SZ.301107 -> SZ301107)
        cleaned_code = stock_code.replace('.', '')
        
        # 尝试读取已存在的评估报告
        existing_report_content = None
        md_path = os.path.join(p5_dir, f"{cleaned_code}.md")
        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as rf:
                    existing_report_content = rf.read()
            except Exception as e:
                print(f"[{stock_code}] 读取已有报告失败: {e}")
        
        try:
            success, api_result = call_processor5_gemini(
                stock_code, stock_name, hotspots_text, api_key, base_url, report_content=existing_report_content
            )
        except Exception as e:
            # 捕获所有意外异常
            with log_lock:
                failed_list.append({"code": stock_code, "name": stock_name, "error": f"意外异常: {str(e)}"})
            print(f"[{stock_code}] 意外异常: {e}")
            with log_lock:
                if pbar: pbar.update(1)
            return {
                "股票代码": stock_code, "股票名称": stock_name,
                "调整后流通市值（亿）": float_mcap,
                "挂钩领域": "分析失败", "潜在关联领域": "分析失败",
                "原索引": index
            }
        
        if success and isinstance(api_result, dict):
            direct_links = api_result.get("direct_links", [])
            potential_links = api_result.get("potential_links", [])
            company_intro = api_result.get("company_intro", "无公司介绍")
            report_md = api_result.get("report_md")
            
            # format lists out to comma separated strings
            direct_str = ", ".join(direct_links) if isinstance(direct_links, list) else str(direct_links)
            potential_str = ", ".join(potential_links) if isinstance(potential_links, list) else str(potential_links)

            # Write individual markdown report
            md_path = os.path.join(p5_dir, f"{cleaned_code}.md")
            md_saved = False
            
            if report_md:
                try:
                    with open(md_path, "w", encoding="utf-8") as mf:
                        mf.write(report_md)
                    md_saved = True
                except Exception as e:
                    print(f"[{stock_code}] Failed to save markdown: {e}")
            else:
                # 已经有报告或者API未返回报告，当作成功
                md_saved = True
            
            if md_saved:
                # 记录成功
                with log_lock:
                    if pbar: 
                        pbar.set_description(f"Processing {stock_code}")
                # 原有的打印逻辑保留，但可以考虑精简或移除以保持进度条整洁
                # try:
                #     print(f"[{stock_code}] Markdown report saved to {cleaned_code}.md")
                # except Exception:
                #     pass  
            
            with log_lock:
                success_list.append(stock_code)
                if pbar: pbar.update(1)

            return {
                "股票代码": stock_code, "股票名称": stock_name,
                "调整后流通市值（亿）": float_mcap,
                "公司基本业务介绍": company_intro,
                "挂钩领域": direct_str, "潜在关联领域": potential_str,
                "原索引": index
            }
        else:
            error_msg = str(api_result) if api_result else "Unknown error"
            with log_lock:
                failed_list.append({"code": stock_code, "name": stock_name, "error": error_msg})
            print(f"[{stock_code}] ❌ API Call Failed: {error_msg}")
            with log_lock:
                if pbar: pbar.update(1)
            return {
                "股票代码": stock_code, "股票名称": stock_name,
                "调整后流通市值（亿）": float_mcap,
                "公司基本业务介绍": "分析失败",
                "挂钩领域": "分析失败", "潜在关联领域": "分析失败",
                "原索引": index
            }

    global pbar
    pbar = tqdm(total=total, desc="🚀 任务进度", unit="stock")
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_row, i, row): i for i, row in df.iterrows()}
            for future in as_completed(futures):
                res = future.result()
                results.append(res)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断执行，正在保存当前进度日志...")
    except Exception as e:
        print(f"\n\n❌ 执行过程中发生异常: {e}，正在保存当前进度日志...")
    finally:
        if pbar: pbar.close()
        # --- 补全未执行的条目 ---
        # 如果是因为 Ctrl+C 等原因中断，有些条目既不在成功也不在失败中
        processed_codes = set(success_list) | {f['code'] for f in failed_list}
        for _, row in df.iterrows():
            c = str(row[code_col])
            if c not in processed_codes:
                failed_list.append({
                    "code": c,
                    "name": str(row[name_col]),
                    "error": "未执行或中途被中断 (Interrupted)"
                })

        # --- 写入执行日志 ---
        if retry:
            # 重试模式：合并上次成功的和本次新成功的
            merged_success = list(set(prev_success_list + success_list))
            log_data = {
                "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "retry",
                "source_file": os.path.basename(latest_file),
                "total": len(merged_success) + len(failed_list),
                "success_count": len(merged_success),
                "fail_count": len(failed_list),
                "success": merged_success,
                "failed": failed_list
            }
        else:
            log_data = {
                "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "full" if not limit else f"limit={limit}",
                "source_file": os.path.basename(latest_file),
                "total": total,
                "success_count": len(success_list),
                "fail_count": len(failed_list),
                "success": success_list,
                "failed": failed_list
            }
        save_log(p5_dir, excel_basename, log_data)
    
    # Sort results to match original excel ranking
    results.sort(key=lambda x: x["原索引"])
    
    # Save the aggregated results
    if results:
        df_out = pd.DataFrame(results)
        df_out = df_out.drop(columns=["原索引"])
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_filename = f"result_p5_{timestamp}.xlsx"
        output_file = os.path.join(p5_dir, output_filename)
        
        try:
            writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
            df_out.to_excel(writer, index=False, sheet_name='Analysis')
            
            workbook  = writer.book
            worksheet = writer.sheets['Analysis']
            
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            base_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

            for col_idx, col_name in enumerate(df_out.columns):
                worksheet.write(0, col_idx, col_name, header_fmt)
                
                # 设置列宽
                if col_idx == 2:   # C列 (调整后流通市值)
                    width = 23
                elif col_idx == 3: # D列 (公司基本业务介绍)
                    width = 51
                elif col_idx >= 4: # E列及以后 (挂钩领域等)
                    width = 25
                else:             # A, B列 (代码, 名称)
                    width = 15
                
                worksheet.set_column(col_idx, col_idx, width)
                
                for row_idx in range(len(df_out)):
                    val = df_out.iloc[row_idx, col_idx]
                    worksheet.write(row_idx + 1, col_idx, val, base_fmt)

            writer.close()
            print(f"Analysis completed. Saved {len(df_out)} rows to {output_filename}")
        except Exception as e:
            print(f"Error saving result: {e}")
    else:
        print("No results to save.")
    
    # 打印执行摘要
    print(f"\n{'='*50}")
    print(f"执行摘要: 成功 {len(success_list)}, 失败 {len(failed_list)}, 共 {total}")
    if failed_list:
        print("失败条目:")
        for item in failed_list:
            print(f"  - [{item['code']}] {item['name']}: {item['error'][:80]}")
    print(f"{'='*50}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Processor 5 Gemini Analysis")
    parser.add_argument("--limit", type=int, default=None, help="最大处理的股票数量限制 (例如: --limit 5)")
    parser.add_argument("--retry", action="store_true", help="仅重试上次执行失败的条目")
    args = parser.parse_args()
    
    main(limit=args.limit, retry=args.retry)
