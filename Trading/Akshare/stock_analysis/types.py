from dataclasses import dataclass, field
from typing import List, Optional, Any

@dataclass
class StockTask:
    """
    Standard input DTO for stock analysis processors.
    Decouples the processor from the data source (Excel/DB/API).
    """
    code: str
    name: str = ""
    total_mcap: float = 0.0  # 总市值
    float_mcap: float = 0.0  # 流通市值
    
    # Context dictionary for future extensions (e.g., pe_ttm, industry, report_date)
    # Processors can look up what they need here.
    context: dict = field(default_factory=dict) 

@dataclass
class AnalysisResult:
    """
    Standard output DTO from stock analysis processors.
    Decouples the runner/saver from the processor's internal logic.
    """
    task: StockTask       # Reference to the input task
    strategy_name: str    # Strategy identifier (e.g. "HotspotAnalysis")
    
    # Structured output for Excel/DB columns
    # Example for Hotspot: {"关联热点": "..", "挂钩方式": "...", "关联描述": "..."}
    structured_data: dict = field(default_factory=dict)
    
    raw_response: Any = None # Original response for debugging (optional)
