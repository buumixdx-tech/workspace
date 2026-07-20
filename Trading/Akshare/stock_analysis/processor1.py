from typing import List
from .base import BaseProcessor
from .types import StockTask, AnalysisResult
from .dify_client import call_stock_analysis_workflow

class HotspotProcessor(BaseProcessor):
    """
    Processor 1: Analyzes stock hotspot associations using Dify workflow.
    """
    
    @property
    def name(self) -> str:
        return "HotspotAnalysis"

    @property
    def code(self) -> str:
        return "p1"

    @property
    def report_config(self) -> dict:
        """定义如何对外展示热点分析结果"""
        return {
            # 表格标题顺序
            "columns": ["股票代码", "股票名称", "总市值", "流通市值", "关联热点", "挂钩方式", "信息来源", "关联描述"],
            # 列宽配置 (字符宽度)
            "widths": {
                "股票代码": 15, "股票名称": 15, "总市值": 12, "流通市值": 12,
                "关联热点": 15, "挂钩方式": 15, "信息来源": 15, "关联描述": 60
            },
            # 合并逻辑：如果股票代码相同，合并前 4 列
            "merge_cols": 4
        }

    def process(self, task: StockTask) -> List[AnalysisResult]:
        """
        Implementation of the standard process method.
        """
        if not task.code:
            return []

        # 1. Call Dify
        success, result = call_stock_analysis_workflow(task.code, task.name)
        
        if not success:
            print(f"  [HotspotProcessor] Failed for {task.code}: {result}")
            return [] 

        # 2. Parse Dify Result
        associations = result.get("hotspot_associations", [])
        
        results = []
        if not associations:
            return []
            
        for item in associations:
            h_name = item.get("hotspot_name", "").strip()
            # Business Filter Logic
            if not h_name or h_name in ["无关联热点", "无", "不相关", "无明显关联"]:
                continue
            
            # 3. Construct Standard Output
            results.append(AnalysisResult(
                task=task,
                strategy_name=self.name,
                structured_data={
                    "关联热点": h_name,
                    "挂钩方式": item.get("connection_method", ""),
                    "信息来源": item.get("info_source_type", ""),
                    "关联描述": item.get("description", "")
                },
                raw_response=item
            ))
            
        return results
