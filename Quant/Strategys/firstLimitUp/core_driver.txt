# modules/core_driver.py

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Any
import yaml


from modules.config_loader import load_config
from modules.order_generator import OrderGenerator
from modules.simulated_broker import SimulatedBroker
from modules.utils import load_trading_calendar, load_market_data, load_selected_stocks, get_clickhouse_client, save_trading_calendar_to_csv, get_clickhouse_client


class BacktestDriver:
    """
    核心驱动模块：控制整个回测流程
    """
    
    def __init__(self, config_path: str):
        """
        初始化回测驱动器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(config_path)
        self.strategy_config = self.config['strategy']
        
        # 生成trading_calendar.csv
        save_trading_calendar_to_csv(get_clickhouse_client(), "data/trading_calendar.csv", self.config['backtest']['start_date'], self.config['backtest']['end_date'])
        
        # 初始化各模块
        self.broker = SimulatedBroker(self.strategy_config)
        self.order_generator = OrderGenerator(self.strategy_config)
        
        # 加载交易日历 (现在返回 YYYYMMDD 格式的列表)
        self.trading_days = load_trading_calendar()
        
        # 存储回测结果
        self.results = []
        self.daily_metrics = []
        
        print(f"✅ 核心驱动模块初始化完成")
        print(f"💰 初始资金: {self.strategy_config['initial_capital']:,}")
        print(f"📅 交易日数量: {len(self.trading_days)}")
    
    def run(self):
        """
        执行完整的回测流程
        """
        print("🚀 开始执行回测...")
        
        for i, date in enumerate(self.trading_days):
            try:
                # 显示进度
                if i % 10 == 0 or i == len(self.trading_days) - 1:
                    progress = (i + 1) / len(self.trading_days) * 100
                    print(f"🔄 进度: {progress:.1f}% ({i+1}/{len(self.trading_days)}) - 处理日期: {date}")
                
                # 执行单日回测
                daily_result = self._process_single_day(date)
                self.results.append(daily_result)
                
            except Exception as e:
                print(f"❌ 日期 {date} 处理出错: {str(e)}")
                continue
        
        # 生成绩效报告
        self._generate_performance_report()
        print("✅ 回测执行完成")
    
    def _process_single_day(self, date: str) -> Dict[str, Any]:
        """
        处理单个交易日
        
        Args:
            date: 交易日期 (YYYYMMDD)
            
        Returns:
            当日结果字典
        """
        # 1. 加载数据
        selected_stocks = load_selected_stocks(date)
        market_data = load_market_data(date)
        
        # 2. 生成交易指令
        orders = self.order_generator.generate(
            date, selected_stocks, market_data # date 是 YYYYMMDD
        )
        
        # 3. 执行交易指令
        executions = []
        failed_orders = []
        
        for order in orders:
            try:
                execution = self.broker.execute_order(order)
                executions.append(execution)
            except Exception as e:
                failed_orders.append({
                    'order': order,
                    'error': str(e)
                })
                print(f"⚠️  交易执行失败 {date} {order['stock']}: {str(e)}")
        
        # 4. 计算当日市值
        total_market_value = self._calculate_total_market_value(date, market_data)
        total_value = self.broker.account['cash'] + total_market_value
        
        # 5. 返回当日结果
        return {
            'date': date, # YYYYMMDD
            'cash': self.broker.account['cash'],
            'positions': dict(self.broker.account['positions']),
            'total_value': total_value,
            'market_value': total_market_value,
            'executions': executions,
            'failed_orders': failed_orders,
            'position_count': len(self.broker.account['positions'])
        }
    
    def _calculate_total_market_value(self, date: str, market_data: Dict) -> float:
        """
        计算当前持仓的总市值
        
        Args:
            date: 当前日期 (YYYYMMDD)
            market_ 当日行情数据
            
        Returns:
            总市值
        """
        total_value = 0.0
        
        for stock, position in self.broker.account['positions'].items():
            amount = position['amount']
            if amount > 0 and stock in market_data:
                close_price = market_data[stock].get('close', 0)
                total_value += amount * close_price
            elif amount > 0:
                print(f"⚠️  股票 {stock} 在 {date} 缺少收盘价数据")
        
        return total_value
    
    def _generate_performance_report(self):
        """
        生成绩效报告
        """
        print("📊 生成绩效报告...")
        
        # 转换为DataFrame
        df_results = pd.DataFrame(self.results)
        
        if len(df_results) == 0:
            print("❌ 没有回测结果可分析")
            return
        
        # 计算基础指标
        # 将 'date' 列从 YYYYMMDD 字符串转换为 datetime 对象以便排序和计算
        df_results['date_dt'] = pd.to_datetime(df_results['date'], format='%Y%m%d')
        df_results = df_results.sort_values('date_dt')
        df_results['return'] = df_results['total_value'].pct_change()
        df_results['cumulative_return'] = (1 + df_results['return']).cumprod() - 1
        df_results['drawdown'] = self._calculate_drawdown(df_results['total_value'])
        
        # 基础统计
        initial_capital = self.strategy_config['initial_capital']
        final_value = df_results['total_value'].iloc[-1]
        total_return = (final_value - initial_capital) / initial_capital
        
        # 年化收益
        days = len(df_results)
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        # 波动率和夏普比率
        daily_volatility = df_results['return'].std()
        annual_volatility = daily_volatility * np.sqrt(252)
        sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
        
        # 最大回撤
        max_drawdown = df_results['drawdown'].min()
        
        # 胜率计算
        winning_days = len(df_results[df_results['return'] > 0])
        win_rate = winning_days / len(df_results) if len(df_results) > 0 else 0
        
        # 输出统计结果
        print("\n" + "="*50)
        print("📈 回测绩效报告")
        print("="*50)
        print(f"初始资金:     ¥{initial_capital:,.2f}")
        print(f"最终价值:     ¥{final_value:,.2f}")
        print(f"总收益率:     {total_return:.2%}")
        print(f"年化收益率:   {annual_return:.2%}")
        print(f"年化波动率:   {annual_volatility:.2%}")
        print(f"夏普比率:     {sharpe_ratio:.2f}")
        print(f"最大回撤:     {max_drawdown:.2%}")
        print(f"胜率:         {win_rate:.2%}")
        print(f"交易日数:     {len(df_results)}")
        print("="*50)
        
        # 保存详细结果
        self._save_detailed_results(df_results)
        
        # 保存交易记录
        self._save_trade_history()
    
    def _calculate_drawdown(self, values: pd.Series) -> pd.Series:
        """
        计算回撤序列
        
        Args:
            values: 资产价值序列
            
        Returns:
            回撤序列
        """
        peak = values.expanding(min_periods=1).max()
        drawdown = (values - peak) / peak
        return drawdown
    
    def _save_detailed_results(self, df_results: pd.DataFrame):
        """
        保存详细的每日结果
        
        Args:
            df_results: 结果DataFrame
        """
        try:
            # 保存每日净值
            output_columns = [
                'date', 'cash', 'market_value', 'total_value', 
                'return', 'cumulative_return', 'drawdown', 'position_count'
            ]
            
            df_output = df_results[output_columns].copy()
            # 保持 'date' 列为 YYYYMMDD 格式的字符串
            # df_output['date'] = df_output['date'].dt.strftime('%Y%m%d') # date 列已经是字符串
            
            output_path = 'output/daily_performance.csv'
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df_output.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"💾 每日绩效已保存至: {output_path}")
            
        except Exception as e:
            print(f"❌ 保存每日绩效失败: {str(e)}")
    
    def _save_trade_history(self):
        """
        保存所有交易记录
        """
        try:
            if not self.broker.account['history']:
                print("⚠️  没有交易记录可保存")
                return
            
            # 转换为DataFrame
            df_trades = pd.DataFrame(self.broker.account['history'])
            # 将 'date' 列从 YYYYMMDD 字符串转换为 datetime 对象以便排序
            df_trades['date_dt'] = pd.to_datetime(df_trades['date'], format='%Y%m%d')
            df_trades = df_trades.sort_values('date_dt')
            
            # 保持 'date' 列为 YYYYMMDD 格式的字符串
            # df_trades['date'] = df_trades['date_dt'].dt.strftime('%Y%m%d')
            # 或者直接使用原始的 'date' 列
            df_trades = df_trades.drop(columns=['date_dt']) # 删除临时列
            
            output_path = 'output/trade_history.csv'
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df_trades.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"💾 交易记录已保存至: {output_path}")
            
        except Exception as e:
            print(f"❌ 保存交易记录失败: {str(e)}")
    
    def get_summary_stats(self) -> Dict[str, float]:
        """
        获取摘要统计信息
        
        Returns:
            统计信息字典
        """
        if not self.results:
            return {}
        
        df_results = pd.DataFrame(self.results)
        initial_capital = self.strategy_config['initial_capital']
        final_value = df_results['total_value'].iloc[-1]
        total_return = (final_value - initial_capital) / initial_capital
        
        days = len(df_results)
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        daily_returns = df_results['total_value'].pct_change().dropna()
        annual_volatility = daily_returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
        
        max_drawdown = self._calculate_drawdown(df_results['total_value']).min()
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'final_value': final_value,
            'initial_capital': initial_capital
        }


# 便捷函数
def run_backtest(config_path: str = "config/strategy.yaml") -> BacktestDriver:
    """
    运行回测的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        BacktestDriver实例
    """
    driver = BacktestDriver(config_path)
    driver.run()
    return driver


if __name__ == "__main__":
    # 测试代码
    driver = run_backtest()
