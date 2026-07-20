import pandas as pd
import numpy as np
import os
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, date
import logging
from analysis.strategy import TradeSignalGenerator, TradeSignal
from analysis.topology_trend import TopologicalTrendIdentifier
from fetcher.baostock_connector import BaostockConnector

@dataclass
class BacktestResult:
    stock_code: str
    total_return: float
    win_rate: float
    trade_count: int
    max_drawdown: float
    final_value: float
    initial_value: float
    suspension_days: int
    hold_return: float = 0.0     # Final Price / Start Price - 1
    index_return: float = 0.0    # Index End / Index Start - 1
    data_quality_issue: bool = False
    details: Dict = None

class PortfolioManager:
    """
    Manages cash, shares, and transaction costs for a single stock simulation.
    """
    def __init__(self, initial_capital: float = 5000000.0, min_pos_pct: float = 0.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.shares = 0
        self.total_value = initial_capital
        self.min_pos_pct = min_pos_pct
        
        # Costs
        self.commission = 0.0003 # 0.03%
        self.stamp_duty = 0.0005 # 0.05% (Sell only)
        
        self.history: List[Dict] = []
        self.last_buy_price = 0.0
        self.trade_results: List[bool] = [] # True for Win, False for Loss
        
    def execute_trade(self, date: str, price: float, action: str):
        """
        Execute trade based on signal.
        Action: 'BUY' (Full Position), 'SELL' (Reduce to Min Position)
        """
        current_value = self.cash + (self.shares * price)
        
        if action == 'BUY':
            # Target: 100% Position
            # We use all available cash to buy shares
            cost_factor = 1 + self.commission
            available_cash = self.cash
            
            if available_cash > 0:
                # Calculate max shares we can buy
                can_buy_shares = int(available_cash / (price * cost_factor))
                # Must be multiple of 100
                can_buy_shares = (can_buy_shares // 100) * 100
                
                if can_buy_shares > 0:
                    cost = can_buy_shares * price * self.commission
                    total_spend = (can_buy_shares * price) + cost
                    
                    self.shares += can_buy_shares
                    self.cash -= total_spend
                    self.last_buy_price = price
                    
        elif action == 'SELL':
            # Target: Min Position %
            target_equity = current_value * self.min_pos_pct
            current_equity = self.shares * price
            
            if current_equity > target_equity:
                sell_value = current_equity - target_equity
                sell_shares = int(sell_value / price)
                # Must be multiple of 100
                sell_shares = (sell_shares // 100) * 100
                
                if sell_shares > 0:
                    revenue = sell_shares * price
                    # Sell Cost: Commission + Stamp Duty
                    total_tax_rate = self.commission + self.stamp_duty
                    cost = revenue * total_tax_rate
                    
                    self.shares -= sell_shares
                    self.cash += (revenue - cost)
                    
                    # Track Win Rate
                    if self.last_buy_price > 0:
                        self.trade_results.append(price > self.last_buy_price)
                        self.last_buy_price = 0 # Reset or keep if partial? Assuming full cycle focus.
        
        # Check Value after trade
        self.update_value(date, price)
        
    def update_value(self, date: str, price: float):
        self.total_value = self.cash + (self.shares * price)
        self.history.append({
            "date": date,
            "value": self.total_value,
            "cash": self.cash,
            "shares": self.shares,
            "price": price
        })

from concurrent.futures import ThreadPoolExecutor, as_completed
from storage.data_loader import get_price

class BatchBacktester:
    def __init__(self):
        # We use local data loader now
        pass
        
    def _is_stock_qualified(self, code, full_start, full_end, total_trading_days, valid_days_set):
        """Helper for Phase 1 Filtering (Parallel)"""
        try:
            df_check = get_price(code, full_start, full_end, adjust='none')
            if not df_check.empty:
                if len(df_check) == total_trading_days:
                    if (df_check['volume'] > 0).all():
                        return code
            return None
        except:
            return None

    def _run_single_stock_backtest(self, code, full_start, full_end, analysis_start, analysis_end, 
                                   backtest_start, backtest_end, threshold_mode, threshold_value, min_pos_pct,
                                   index_return_val=0.0):
        """Helper for Phase 2 Backtesting (Parallel)"""
        try:
            # 2. Fetch Stock Data (QFQ) for FULL Period
            df_full = get_price(code, full_start, full_end, adjust='qfq')
            
            if df_full.empty:
                return BacktestResult(code, 0, 0, 0, 0, 0, 0, 0, data_quality_issue=True)
                
            suspension_count = 0

            # 4. Split Data
            df_ana = df_full[(df_full['date'].astype(str) >= analysis_start) & (df_full['date'].astype(str) <= analysis_end)].copy()
            df_bt = df_full[(df_full['date'].astype(str) >= backtest_start) & (df_full['date'].astype(str) <= backtest_end)].copy()
            
            if df_ana.empty or df_bt.empty:
                 return BacktestResult(code, 0, 0, 0, 0, 0, 0, 999, data_quality_issue=True)

            # Calculation of Buy-and-Hold Return
            # We use first row open (or close) to last row close
            start_price = float(df_bt.iloc[0]['close'])
            end_price = float(df_bt.iloc[-1]['close'])
            hold_return = (end_price / start_price) - 1 if start_price != 0 else 0

            # 5. Determine Threshold (Auto Elbow or Fixed)
            final_thresh_method = 'atr' 
            final_thresh_val = threshold_value
            
            if threshold_mode == 'auto_elbow':
                try:
                    topo = TopologicalTrendIdentifier(df_ana)
                    best_atr, _ = topo.optimize_threshold_elbow(method='atr')
                    if best_atr:
                        final_thresh_val = best_atr
                        final_thresh_method = 'atr'
                except Exception as e:
                    final_thresh_val = threshold_value
            
            # 6. Run Strategy on BACKTEST Segment
            sim_engine = TradeSignalGenerator(df_bt)
            sim_engine.run_simulation(backtest_start, backtest_end, final_thresh_method, final_thresh_val)
            signals = sim_engine.signals
            
            # 5. Run Portfolio Execution
            pm = PortfolioManager(initial_capital=5000000.0, min_pos_pct=min_pos_pct)
            
            signal_map = {s.date: s.type for s in signals}
            
            for index, row in df_bt.iterrows():
                d_str = str(row['date'])
                price = float(row['close'])
                if d_str in signal_map:
                    pm.execute_trade(d_str, price, signal_map[d_str])
                else:
                    pm.update_value(d_str, price)
            
            final_val = pm.total_value
            initial_val = pm.initial_capital
            total_ret = (final_val - initial_val) / initial_val
            
            win_rate = 0.0
            if pm.trade_results:
                win_rate = sum(pm.trade_results) / len(pm.trade_results)
            
            val_hist = [h['value'] for h in pm.history]
            max_dd = 0.0
            if val_hist:
                peak = val_hist[0]
                for v in val_hist:
                    if v > peak: peak = v
                    dd = (peak - v) / peak
                    if dd > max_dd: max_dd = dd
            
            return BacktestResult(
                stock_code=code,
                total_return=total_ret,
                win_rate=win_rate,
                trade_count=len(signals),
                max_drawdown=max_dd,
                final_value=final_val,
                initial_value=initial_val,
                suspension_days=suspension_count,
                hold_return=hold_return,
                index_return=index_return_val,
                data_quality_issue=False
            )
        except Exception as e:
            logging.error(f"Error backtesting {code}: {e}")
            return BacktestResult(code, 0, 0, 0, 0, 0, 0, 0, data_quality_issue=True)

    def run_batch(self, 
                  stock_codes: List[str], 
                  analysis_start: str,
                  analysis_end: str,
                  backtest_start: str,
                  backtest_end: str, 
                  threshold_mode: str = 'auto_elbow',
                  threshold_value: float = 1.5,
                  min_pos_pct: float = 0.0,
                  progress_callback=None) -> pd.DataFrame:
        
        results = []
        
        # 1. Fetch Index Data for BOTH periods
        full_start = analysis_start
        full_end = backtest_end
        
        index_df = get_price("sh.000001", full_start, full_end, adjust='none')
        if index_df.empty:
            logging.error("Benchmark Index data is empty.")
            return pd.DataFrame()
            
        valid_days_set = set(index_df['date'].astype(str).unique())
        total_trading_days = len(valid_days_set)
        
        # Calculate Index return for Backtest Period
        index_bt = index_df[(index_df['date'].astype(str) >= backtest_start) & (index_df['date'].astype(str) <= backtest_end)]
        index_ret_val = 0.0
        if not index_bt.empty:
            i_start = float(index_bt.iloc[0]['close'])
            i_end = float(index_bt.iloc[-1]['close'])
            index_ret_val = (i_end / i_start) - 1 if i_start != 0 else 0

        # --- Phase 1: Filter Qualified Stocks (Multi-threaded) ---
        qualified_codes = []
        total_input = len(stock_codes)
        
        if progress_callback:
            progress_callback(0, total_input, "正在并行筛选无停牌标的...")
            
        max_workers = min(32, (os.cpu_count() or 1) * 4) # I/O bound mostly
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._is_stock_qualified, code, full_start, full_end, 
                                      total_trading_days, valid_days_set): code for code in stock_codes}
            
            for i, future in enumerate(as_completed(futures)):
                res_code = future.result()
                if res_code:
                    qualified_codes.append(res_code)
                
                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback(i + 1, total_input, f"筛选中: {i+1}/{total_input} (已找到 {len(qualified_codes)} 只符合要求)")

        total_qualified = len(qualified_codes)
        if progress_callback:
            progress_callback(total_input, total_input, f"筛选完成！共有 {total_qualified} 只标的无停牌，开始回测...")
            
        # --- Phase 2: Run Strategy on Qualified Stocks (Multi-threaded) ---
        if total_qualified == 0:
            return pd.DataFrame()
            
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._run_single_stock_backtest, code, full_start, full_end, 
                                      analysis_start, analysis_end, backtest_start, backtest_end,
                                      threshold_mode, threshold_value, min_pos_pct,
                                      index_return_val=index_ret_val): code for code in qualified_codes}
            
            for i, future in enumerate(as_completed(futures)):
                res = future.result()
                results.append(res)
                
                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(i + 1, total_qualified, f"回测执行中: {i+1}/{total_qualified} ({res.stock_code})")
            
        return pd.DataFrame([vars(r) for r in results])
