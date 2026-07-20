# modules/simulated_broker.py

from typing import Dict, List, Any

class SimulatedBroker:
    def __init__(self, strategy_config: Dict[str, Any]):
        self.buy_fee_rate = strategy_config['transaction_cost']['buy_fee_rate']
        self.sell_fee_rate = strategy_config['transaction_cost']['sell_fee_rate']
        self.stock_unit = strategy_config['stock_unit']
        
        # 初始化账户
        self.account = {
            'cash': strategy_config['initial_capital'],
            'positions': {},
            'history': []
        }
    
    def execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行交易指令
        
        Args:
            order: 交易指令
            
        Returns:
            成交回报
        """
        stock = order['stock']
        price = order['price']
        amount = order['amount']
        order_type = order['type']
        date = order['date'] # YYYYMMDD 格式
        
        if order_type == 'buy':
            total_cost = amount * price + order['fee']
            if self.account['cash'] < total_cost:
                raise Exception(f"资金不足，无法买入 {stock}。可用资金: {self.account['cash']}, 需要: {total_cost}")
            
            self.account['cash'] -= total_cost
            
            # 更新持仓
            if stock not in self.account['positions']:
                self.account['positions'][stock] = {
                    'amount': 0,
                    'cost_price': 0,
                    'market_value': 0
                }
            
            pos = self.account['positions'][stock]
            total_amount = pos['amount'] + amount
            total_value = pos['amount'] * pos['cost_price'] + amount * price
            
            pos['amount'] = total_amount
            pos['cost_price'] = total_value / total_amount if total_amount > 0 else 0
            pos['market_value'] = total_amount * price
        
        elif order_type == 'sell':
            if stock not in self.account['positions']:
                raise Exception(f"无持仓 {stock}，无法卖出")
            
            pos = self.account['positions'][stock]
            if pos['amount'] < amount:
                raise Exception(f"持仓不足 {stock}，当前持仓: {pos['amount']}, 欲卖出: {amount}")
            
            revenue = amount * price - order['fee']
            self.account['cash'] += revenue
            
            pos['amount'] -= amount
            pos['market_value'] = pos['amount'] * price
            
            if pos['amount'] == 0:
                del self.account['positions'][stock]
        
        # 记录交易历史
        execution = order.copy()
        self.account['history'].append(execution)
        
        return execution
    
    def get_account_status(self) -> Dict[str, Any]:
        """
        获取账户状态
        
        Returns:
            账户状态字典
        """
        return {
            'cash': self.account['cash'],
            'positions': dict(self.account['positions']),
            'total_value': self.account['cash'] + sum(pos['market_value'] 
                                                    for pos in self.account['positions'].values())
        }
