"""
Stock Filtering Utilities for Backtest.
Provides functions to filter stocks based on data quality criteria.
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set, Callable, Optional
import pandas as pd


def filter_qualified_stocks(
    stock_codes: List[str],
    start_date: str,
    end_date: str,
    data_loader: Callable,
    benchmark_code: str = "sh.000001",
    progress_callback: Optional[Callable] = None,
    max_workers: int = 32
) -> List[str]:
    """
    Filter stocks that have complete data (no suspensions) for the given period.
    
    Args:
        stock_codes: List of stock codes to filter
        start_date: Start of the period (YYYY-MM-DD)
        end_date: End of the period (YYYY-MM-DD)
        data_loader: Function to load price data: (code, start, end, adjust) -> DataFrame
        benchmark_code: Index code to use for valid trading days
        progress_callback: Optional callback(current, total, message) for progress updates
        max_workers: Number of parallel workers
        
    Returns:
        List of qualified stock codes with no missing trading days
    """
    # 1. Get valid trading days from benchmark
    benchmark_df = data_loader(benchmark_code, start_date, end_date, 'none')
    if benchmark_df.empty:
        return []
        
    valid_days_set = set(benchmark_df['date'].astype(str).unique())
    total_trading_days = len(valid_days_set)
    
    # 2. Define check function
    def is_qualified(code: str) -> Optional[str]:
        try:
            df = data_loader(code, start_date, end_date, 'none')
            if df.empty:
                return None
            # Check complete days
            if len(df) != total_trading_days:
                return None
            # Check no suspension (volume > 0)
            if not (df['volume'] > 0).all():
                return None
            return code
        except:
            return None
    
    # 3. Parallel filtering
    qualified = []
    total_input = len(stock_codes)
    
    if progress_callback:
        progress_callback(0, total_input, "正在并行筛选无停牌标的...")
    
    workers = min(max_workers, (os.cpu_count() or 1) * 4)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(is_qualified, code): code for code in stock_codes}
        
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result:
                qualified.append(result)
            
            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, total_input, f"筛选中: {i+1}/{total_input} (已找到 {len(qualified)} 只符合要求)")
    
    if progress_callback:
        progress_callback(total_input, total_input, f"筛选完成！共有 {len(qualified)} 只标的无停牌")
    
    return qualified


def get_index_return(data_loader: Callable, index_code: str, start_date: str, end_date: str) -> float:
    """
    Calculate the return of an index over a period.
    
    Args:
        data_loader: Function to load price data
        index_code: Index code (e.g., 'sh.000001')
        start_date: Period start
        end_date: Period end
        
    Returns:
        Index return as a decimal (e.g., 0.05 for 5%)
    """
    df = data_loader(index_code, start_date, end_date, 'none')
    if df.empty:
        return 0.0
    
    start_price = float(df.iloc[0]['close'])
    end_price = float(df.iloc[-1]['close'])
    
    if start_price == 0:
        return 0.0
        
    return (end_price / start_price) - 1
