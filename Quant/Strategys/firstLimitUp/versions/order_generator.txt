# modules/order_generator.py

from typing import Dict, List, Any
from modules.utils import get_next_n_trading_days, load_trading_calendar
from datetime import datetime

class OrderGenerator:
    def __init__(self, strategy_config: Dict[str, Any]):
        self.config = strategy_config
        self.holding_days = strategy_config['holding_days']
        self.initial_capital = strategy_config['initial_capital']
        self.stock_unit = strategy_config['stock_unit']
        self.buy_fee_rate = strategy_config['transaction_cost']['buy_fee_rate']
        self.sell_fee_rate = strategy_config['transaction_cost']['sell_fee_rate']
        self.skip_suspended = strategy_config.get('skip_suspended_stocks', True)
        
        # 初始化资金池
        self.capital_pool = {
            'total': self.initial_capital,
            'available': [self.initial_capital // self.holding_days] * self.holding_days,
            'used': []
        }
        
        # 初始化持仓记录
        self.positions = []
        self.trading_calendar = load_trading_calendar()
    
    def generate(self, trading_day: str, selected_stocks: List[str], 
                market_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        生成交易指令
        
        Args:
            trading_day: 交易日期 (YYYYMMDD)
            selected_stocks: 选股清单
            market_data: 市场数据
            
        Returns:
            交易指令列表
        """
        instructions = []
        
        # 1. 处理到期清仓
        instructions.extend(self._generate_sell_instructions(trading_day, market_data))
        
        # 2. 处理建仓
        instructions.extend(self._generate_buy_instructions(trading_day, selected_stocks, market_data))
        
        return instructions
    
    def _generate_sell_instructions(self, trading_day: str, 
                                  market_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成卖出指令"""
        sell_instructions = []
        
        for position in self.positions[:]:  # 使用切片避免迭代时修改列表
            # position['sell_date'] 和 trading_day 都是 YYYYMMDD 格式
            if position['sell_date'] == trading_day and position['status'] == 'holding':
                for stock in position['stocks']:
                    if stock in market_data:
                        price = market_data[stock]['close']
                        amount = position['holdings'].get(stock, {}).get('amount', 0)
                        if amount > 0:
                            fee = amount * price * self.sell_fee_rate
                            cash = amount * price - fee
                            
                            sell_instructions.append({
                                "date": trading_day, # YYYYMMDD
                                "type": "sell",
                                "stock": stock,
                                "price": price,
                                "amount": amount,
                                "fee": fee,
                                "cash_change": cash
                            })
                
                # 回收资金
                self.capital_pool['available'].append(position['capital_used'])
                position['status'] = 'closed'
        
        return sell_instructions
    
    def _generate_buy_instructions(self, trading_day: str, selected_stocks: List[str],
                                 market_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成买入指令"""
        buy_instructions = []
        
        if not self.capital_pool['available']:
            return buy_instructions
        
        # 过滤停牌股票
        if self.skip_suspended:
            valid_stocks = [s for s in selected_stocks 
                          if s in market_data and not market_data[s].get('suspended', False)]
        else:
            valid_stocks = [s for s in selected_stocks if s in market_data]
        
        if not valid_stocks:
            return buy_instructions
        
        # 取出一份资金
        capital_to_use = self.capital_pool['available'].pop(0)
        per_stock_capital = capital_to_use / len(valid_stocks)
        
        # 为每只股票生成买入指令
        holdings = {}
        for stock in valid_stocks:
            if stock not in market_data:
                continue
                
            open_price = market_data[stock]['open']
            max_amount = int(per_stock_capital / (open_price * self.stock_unit)) * self.stock_unit
            
            if max_amount <= 0:
                continue
            
            fee = max_amount * open_price * self.buy_fee_rate
            total_cost = max_amount * open_price + fee
            
            buy_instructions.append({
                "date": trading_day, # YYYYMMDD
                "type": "buy",
                "stock": stock,
                "price": open_price,
                "amount": max_amount,
                "fee": fee,
                "cash_change": -total_cost
            })
            
            holdings[stock] = {
                'amount': max_amount,
                'buy_price': open_price
            }
        
        # 记录持仓信息
        if buy_instructions:  # 只有成功生成指令时才记录持仓
            # 计算卖出日期 (YYYYMMDD)
            sell_date = get_next_n_trading_days(trading_day, self.holding_days, self.trading_calendar)
            if sell_date:
                position_entry = {
                    'buy_date': trading_day, # YYYYMMDD
                    'sell_date': sell_date,  # YYYYMMDD
                    'stocks': valid_stocks,
                    'capital_used': capital_to_use,
                    'status': 'holding',
                    'holdings': holdings
                }
                self.positions.append(position_entry)
        
        return buy_instructions
