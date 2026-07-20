"""
BacktestEngine: Unified backtest runner that accepts any BaseStrategy.
Decoupled from specific strategy implementations.
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
import pandas as pd

from .result import BacktestResult
from .portfolio import PortfolioManager
from .filter import filter_qualified_stocks, get_index_return
from analysis.strategies.base import BaseStrategy


class BacktestEngine:
    """
    Unified backtest engine that runs any strategy implementing BaseStrategy.
    
    Usage:
        strategy = TopologySwingStrategy()
        strategy.initialize({'auto_elbow': True})
        
        engine = BacktestEngine(strategy, data_loader=get_price)
        results = engine.run(
            stock_codes=['sh.600000', 'sz.000001'],
            analysis_start='2024-01-01',
            analysis_end='2024-06-30',
            backtest_start='2024-07-01',
            backtest_end='2024-12-31'
        )
    """
    
    def __init__(self, 
                 strategy: BaseStrategy,
                 data_loader: Callable,
                 portfolio_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the backtest engine.
        
        Args:
            strategy: An instance of a class implementing BaseStrategy
            data_loader: Function to load price data: (code, start, end, adjust) -> DataFrame
            portfolio_config: Optional dict with keys: initial_capital, min_pos_pct, commission, stamp_duty
        """
        self.strategy = strategy
        self.data_loader = data_loader
        self.portfolio_config = portfolio_config or {}
        
    def _run_single_backtest(self, 
                             code: str,
                             full_start: str,
                             full_end: str,
                             analysis_start: str,
                             analysis_end: str,
                             backtest_start: str,
                             backtest_end: str,
                             index_return_val: float = 0.0) -> BacktestResult:
        """
        Run backtest for a single stock.
        """
        try:
            # Load full period data (QFQ for price accuracy)
            df_full = self.data_loader(code, full_start, full_end, 'qfq')
            
            if df_full.empty:
                return BacktestResult(stock_code=code, total_return=0, data_quality_issue=True)
            
            # Split into analysis and backtest periods
            df_ana = df_full[(df_full['date'].astype(str) >= analysis_start) & 
                            (df_full['date'].astype(str) <= analysis_end)].copy()
            df_bt = df_full[(df_full['date'].astype(str) >= backtest_start) & 
                           (df_full['date'].astype(str) <= backtest_end)].copy()
            
            if df_ana.empty or df_bt.empty:
                return BacktestResult(stock_code=code, total_return=0, data_quality_issue=True)
            
            # Calculate buy-and-hold return
            start_price = float(df_bt.iloc[0]['close'])
            end_price = float(df_bt.iloc[-1]['close'])
            hold_return = (end_price / start_price) - 1 if start_price != 0 else 0
            
            # Optimize strategy params using analysis period data
            optimized_params = self.strategy.optimize_params(df_ana)
            self.strategy.initialize(optimized_params)
            
            # Generate signals on backtest period
            signals = self.strategy.generate_signals(df_bt, backtest_start, backtest_end)
            
            # Execute trades through portfolio manager
            pm = PortfolioManager(
                initial_capital=self.portfolio_config.get('initial_capital', 5000000.0),
                min_pos_pct=self.portfolio_config.get('min_pos_pct', 0.0),
                commission=self.portfolio_config.get('commission', 0.0003),
                stamp_duty=self.portfolio_config.get('stamp_duty', 0.0005)
            )
            
            signal_map = {s.date: s.action for s in signals}
            
            for _, row in df_bt.iterrows():
                d_str = str(row['date'])
                price = float(row['close'])
                
                if d_str in signal_map:
                    pm.execute_trade(d_str, price, signal_map[d_str])
                else:
                    pm.update_value(d_str, price)
            
            # Calculate results
            total_return = (pm.total_value - pm.initial_capital) / pm.initial_capital
            
            return BacktestResult(
                stock_code=code,
                total_return=total_return,
                hold_return=hold_return,
                index_return=index_return_val,
                win_rate=pm.get_win_rate(),
                trade_count=len(signals),
                max_drawdown=pm.calculate_max_drawdown(),
                final_value=pm.total_value,
                initial_value=pm.initial_capital,
                suspension_days=0,
                data_quality_issue=False
            )
            
        except Exception as e:
            logging.error(f"Error backtesting {code}: {e}")
            return BacktestResult(stock_code=code, total_return=0, data_quality_issue=True)
    
    def run(self,
            stock_codes: List[str],
            analysis_start: str,
            analysis_end: str,
            backtest_start: str,
            backtest_end: str,
            auto_filter: bool = True,
            progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """
        Run batch backtest on multiple stocks.
        
        Args:
            stock_codes: List of stock codes to backtest
            analysis_start: Start of analysis period for parameter optimization
            analysis_end: End of analysis period
            backtest_start: Start of backtest period for signal generation
            backtest_end: End of backtest period
            auto_filter: If True, filter out stocks with suspensions
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            DataFrame with BacktestResult for each stock
        """
        full_start = analysis_start
        full_end = backtest_end
        
        # Get index return for benchmark
        index_ret = get_index_return(self.data_loader, "sh.000001", backtest_start, backtest_end)
        
        # Phase 1: Filter stocks
        if auto_filter:
            qualified_codes = filter_qualified_stocks(
                stock_codes=stock_codes,
                start_date=full_start,
                end_date=full_end,
                data_loader=self.data_loader,
                progress_callback=progress_callback
            )
        else:
            qualified_codes = stock_codes
        
        if not qualified_codes:
            return pd.DataFrame()
        
        total_qualified = len(qualified_codes)
        
        if progress_callback:
            progress_callback(0, total_qualified, f"开始回测 {total_qualified} 只标的...")
        
        # Phase 2: Run backtests in parallel
        results = []
        max_workers = min(32, (os.cpu_count() or 1) * 4)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._run_single_backtest,
                    code, full_start, full_end,
                    analysis_start, analysis_end,
                    backtest_start, backtest_end,
                    index_ret
                ): code for code in qualified_codes
            }
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                results.append(result)
                
                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(i + 1, total_qualified, 
                                    f"回测执行中: {i+1}/{total_qualified} ({result.stock_code})")
        
        if progress_callback:
            progress_callback(total_qualified, total_qualified, "回测完成！")
        
        return pd.DataFrame([vars(r) for r in results])
