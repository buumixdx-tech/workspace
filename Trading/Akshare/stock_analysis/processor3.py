from typing import List
from .base import BaseProcessor
from .types import StockTask, AnalysisResult
from .dify_client import call_hotspot_2_workflow

class HotspotMatchedProcessor(BaseProcessor):
    """
    Processor 3: Analyzes detailed stock-hotspot associations using the new JSON scheme.
    """
    
    @property
    def name(self) -> str:
        return "HotspotMatchedAnalysis"

    @property
    def code(self) -> str:
        return "p3"

    @property
    def report_config(self) -> dict:
        return {
            "columns": ["股票代码", "股票名称", "关联描述", "关联热点", "关联方式"],
            "widths": {
                "股票代码": 15, "股票名称": 15, 
                "关联描述": 50, "关联热点": 20, "关联方式": 20
            },
            # Only merge first 2 columns (Code, Name)
            "merge_cols": 2
        }

    def process(self, task: StockTask) -> List[AnalysisResult]:
        description = str(task.context.get("description", "")).strip()
        if not description or description.lower() in ["nan", "none", ""]:
            return []

        # 1. Call Dify (New Workflow)
        success, result = call_hotspot_2_workflow(description)
        
        if not success:
            print(f"  [HotspotMatchedProcessor] Failed for {task.code}: {result}")
            return [] 
        
        # Debug: Print raw result to see what we got
        # print(f"[DEBUG P3] Raw result keys: {result.keys()}")
        # print(f"[DEBUG P3] Raw result: {result}")
        
        # 2. Parse Dify Result (New Scheme)
        # Fallback: Check if data is hidden in 'text' key (common Dify raw output)
        if "linked_hotspots" not in result and "text" in result:
            try:
                # Try to parse the 'text' field content
                raw_text = result["text"]
                # Clean markdown blocks if present
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                    
                import json
                import ast
                try:
                    parsed_inner = json.loads(raw_text.strip())
                except:
                    parsed_inner = ast.literal_eval(raw_text.strip())
                    
                if isinstance(parsed_inner, dict):
                    result = parsed_inner
            except Exception as e:
                print(f"  [HotspotMatchedProcessor] Failed to parse 'text' field: {e}")

        linked_hotspots = result.get("linked_hotspots", [])
        
        # Helper: If it's a string (which sometimes happens with LLM output), parse it
        if isinstance(linked_hotspots, str):
            try:
                import json
                linked_hotspots = json.loads(linked_hotspots)
            except Exception:
                try:
                    import ast
                    linked_hotspots = ast.literal_eval(linked_hotspots)
                except Exception as e:
                    print(f"  [HotspotMatchedProcessor] Failed to parse linked_hotspots string: {e}")
                    return []
                
        if linked_hotspots is None:
             # Truly missing key or parsing failure
             print(f"  [P3] 'linked_hotspots' key missing. Keys found: {result.keys()}")
             results = []
             results.append(AnalysisResult(
                task=task,
                strategy_name=self.name,
                structured_data={
                    "关联描述": description,
                    "关联热点": "PARSING_ERROR",
                    "关联方式": "KEY_MISSING"
                },
                raw_response=result
             ))
             return results
        
        if len(linked_hotspots) == 0:
            # Valid empty list -> No association found
            results = []
            results.append(AnalysisResult(
                task=task,
                strategy_name=self.name,
                structured_data={
                    "关联描述": str(result.get("info_content", description)),
                    "关联热点": "无关联",
                    "关联方式": "-"
                },
                raw_response=result
            ))
            return results

        # Requirement: "One description, one result"
        # We take the best match (first item)
        item = linked_hotspots[0]
        if not isinstance(item, dict):
            print(f"  [P3] Warning: First item is not a dict: {item}")
            return []

        # Helper to get value case-insensitively or with aliases
        def get_val(keys_list):
            for k in keys_list:
                if k in item: return str(item[k])
                # Case insensitive check
                for existing_k in item.keys():
                    if existing_k.lower() == k.lower():
                        return str(item[existing_k])
            return ""

        hotspot = get_val(["hotspot", "hotspot_name", "热点"])
        pattern = get_val(["pattern", "connection_method", "association", "方式", "关联方式"])
        
        # Use info_content from API result if available (per schema), otherwise input description
        final_desc = str(result.get("info_content", description))

        res_list = [AnalysisResult(
            task=task,
            strategy_name=self.name,
            structured_data={
                "关联描述": final_desc,
                "关联热点": hotspot,
                "关联方式": pattern
            },
            raw_response=item
        )]
        # print(f"  [P3] Generated {len(res_list)} results for {task.code}")
        return res_list
