"""
BacktestResult: Standardized result container for backtest runs.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class BacktestResult:
    """
    Holds the results of a single stock backtest.
    
    Attributes:
        stock_code: Stock identifier (e.g., 'sh.600000')
        total_return: Strategy return (final_value / initial_value - 1)
        hold_return: Buy-and-hold return for comparison
        index_return: Benchmark index return for the same period
        win_rate: Ratio of winning trades to total trades
        trade_count: Number of trades executed
        max_drawdown: Maximum peak-to-trough decline
        final_value: Portfolio value at end of backtest
        initial_value: Portfolio value at start of backtest
        suspension_days: Number of missing trading days (data quality)
        data_quality_issue: Flag indicating data problems
        details: Optional dictionary for strategy-specific metrics
    """
    stock_code: str
    total_return: float
    hold_return: float = 0.0
    index_return: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0
    max_drawdown: float = 0.0
    final_value: float = 0.0
    initial_value: float = 0.0
    suspension_days: int = 0
    data_quality_issue: bool = False
    details: Optional[Dict[str, Any]] = field(default_factory=dict)
