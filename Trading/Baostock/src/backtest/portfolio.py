"""
PortfolioManager: Handles position management, trade execution, and cost accounting.
"""
from typing import List, Dict
from dataclasses import dataclass, field


@dataclass
class TradeRecord:
    """Record of a single executed trade."""
    date: str
    action: str  # 'BUY' or 'SELL'
    price: float
    shares: int
    cost: float
    value_after: float


class PortfolioManager:
    """
    Manages cash, shares, and transaction costs for a single stock simulation.
    
    Attributes:
        initial_capital: Starting cash amount
        min_pos_pct: Minimum position percentage to maintain after sell signals
        commission: Trading commission rate (default 0.03%)
        stamp_duty: Stamp duty rate for sells (default 0.05%)
    """
    
    def __init__(self, 
                 initial_capital: float = 5000000.0, 
                 min_pos_pct: float = 0.0,
                 commission: float = 0.0003,
                 stamp_duty: float = 0.0005):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.shares = 0
        self.total_value = initial_capital
        self.min_pos_pct = min_pos_pct
        
        # Cost Config
        self.commission = commission
        self.stamp_duty = stamp_duty
        
        # Tracking
        self.history: List[Dict] = []
        self.trades: List[TradeRecord] = []
        self.last_buy_price = 0.0
        self.trade_results: List[bool] = []  # True for Win, False for Loss
        
    def execute_trade(self, date: str, price: float, action: str) -> None:
        """
        Execute trade based on signal.
        
        Args:
            date: Trade date (YYYY-MM-DD)
            price: Execution price
            action: 'BUY' (full position) or 'SELL' (reduce to min position)
        """
        current_value = self.cash + (self.shares * price)
        executed_shares = 0
        trade_cost = 0.0
        
        if action == 'BUY':
            # Target: 100% Position
            cost_factor = 1 + self.commission
            available_cash = self.cash
            
            if available_cash > 0:
                can_buy_shares = int(available_cash / (price * cost_factor))
                can_buy_shares = (can_buy_shares // 100) * 100  # Round to lot size
                
                if can_buy_shares > 0:
                    trade_cost = can_buy_shares * price * self.commission
                    total_spend = (can_buy_shares * price) + trade_cost
                    
                    self.shares += can_buy_shares
                    self.cash -= total_spend
                    self.last_buy_price = price
                    executed_shares = can_buy_shares
                    
        elif action == 'SELL':
            # Target: Min Position %
            target_equity = current_value * self.min_pos_pct
            current_equity = self.shares * price
            
            if current_equity > target_equity:
                sell_value = current_equity - target_equity
                sell_shares = int(sell_value / price)
                sell_shares = (sell_shares // 100) * 100  # Round to lot size
                
                if sell_shares > 0:
                    revenue = sell_shares * price
                    total_tax_rate = self.commission + self.stamp_duty
                    trade_cost = revenue * total_tax_rate
                    
                    self.shares -= sell_shares
                    self.cash += (revenue - trade_cost)
                    executed_shares = sell_shares
                    
                    # Track Win Rate
                    if self.last_buy_price > 0:
                        self.trade_results.append(price > self.last_buy_price)
                        self.last_buy_price = 0
        
        # Record trade
        if executed_shares > 0:
            self.trades.append(TradeRecord(
                date=date,
                action=action,
                price=price,
                shares=executed_shares,
                cost=trade_cost,
                value_after=self.cash + (self.shares * price)
            ))
        
        self.update_value(date, price)
        
    def update_value(self, date: str, price: float) -> None:
        """Update portfolio value and record history."""
        self.total_value = self.cash + (self.shares * price)
        self.history.append({
            "date": date,
            "value": self.total_value,
            "cash": self.cash,
            "shares": self.shares,
            "price": price
        })
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from value history."""
        if not self.history:
            return 0.0
            
        peak = self.history[0]['value']
        max_dd = 0.0
        
        for record in self.history:
            if record['value'] > peak:
                peak = record['value']
            dd = (peak - record['value']) / peak
            if dd > max_dd:
                max_dd = dd
                
        return max_dd
    
    def get_win_rate(self) -> float:
        """Calculate win rate from completed trades."""
        if not self.trade_results:
            return 0.0
        return sum(self.trade_results) / len(self.trade_results)
