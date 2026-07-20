import os
from stock_analysis.types import StockTask, AnalysisResult
from stock_analysis.dify_client import call_gemini_analysis_workflow

class GeminiAnalysisProcessor:
    code = "gemini"
    name = "Gemini 个股深度分析"
    
    # 因为此处理器主要产出 md 文件，所以这里对表格输出的要求极简
    report_config = {
        "columns": ["股票代码", "股票名称", "分析状态"],
        "widths": {
            "股票代码": 15,
            "股票名称": 15,
            "分析状态": 40
        },
        "merge_cols": 0
    }

    def process(self, task: StockTask) -> list[AnalysisResult]:
        print(f"[{task.code} {task.name}] 正在调用 Dify Gemini 工作流 (预计耗时较长)...")
        
        # 提取去掉前缀的纯 6 位代码
        pure_code = task.code.split(".")[-1]
        
        success, response = call_gemini_analysis_workflow(pure_code)
        
        status_msg = ""
        if success:
            # Save the raw markdown to the designated directory
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            reports_dir = os.path.join(project_root, "data", "strategy_result", "reports")
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
                
            report_path = os.path.join(reports_dir, f"{pure_code}.md")
            
            try:
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(response)
                status_msg = f"成功生成报告，保存在: reports/{pure_code}.md"
                print(f"[{task.code} {task.name}] ✅ {status_msg}")
            except Exception as e:
                status_msg = f"报告内容获取成功，但写入文件失败: {e}"
                print(f"[{task.code} {task.name}] ❌ {status_msg}")
        else:
            status_msg = f"调用 API 失败: {response}"
            print(f"[{task.code} {task.name}] ❌ {status_msg}")
            
        return [AnalysisResult(
            task=task,
            strategy_name=self.name,
            structured_data={
                "分析状态": status_msg
            }
        )]
