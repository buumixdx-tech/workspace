from typing import List
from .base import BaseProcessor
from .types import StockTask, AnalysisResult
from .dify_client import call_sector_hook_workflow

class SectorHookProcessor(BaseProcessor):
    """
    Processor 2: Analyzes stock-sector hooks based on a one-sentence description.
    """
    
    @property
    def name(self) -> str:
        return "SectorHookAnalysis"

    @property
    def code(self) -> str:
        return "p2"

    @property
    def report_config(self) -> dict:
        return {
            "columns": ["股票代码", "股票名称", "一句话描述", "挂钩板块", "挂钩原因"],
            "widths": {
                "股票代码": 15, "股票名称": 15, 
                "一句话描述": 60, "挂钩板块": 20, "挂钩原因": 50
            },
            # Merge code, name, and description if they are the same
            "merge_cols": 0
        }

    def process(self, task: StockTask) -> List[AnalysisResult]:
        description = task.context.get("description", "")
        if not description or description == "nan":
            return []

        # 1. Call Dify
        success, result = call_sector_hook_workflow(description)
        
        if not success:
            print(f"  [SectorHookProcessor] Failed for {task.code}: {result}")
            return [] 

        # 2. Parse Dify Result
        # Format: {"info_content": "...", "linked_sectors": [{"sector_name": "...", "analysis": "..."}, ...]}
        linked_sectors = result.get("linked_sectors", [])
        
        if not linked_sectors:
            return []
            
        results = []
        for sector_item in linked_sectors:
            sector_name = sector_item.get("sector_name", "")
            analysis = sector_item.get("analysis", "")
            
            results.append(AnalysisResult(
                task=task,
                strategy_name=self.name,
                structured_data={
                    "一句话描述": description,
                    "挂钩板块": sector_name,
                    "挂钩原因": analysis
                },
                raw_response=sector_item
            ))
            
        return results
