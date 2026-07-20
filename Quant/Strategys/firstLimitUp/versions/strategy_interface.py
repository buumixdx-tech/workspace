# strategy_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import date

class StockSelectionStrategy(ABC):
    """
    抽象基类，定义选股策略的接口。
    所有具体的选股策略都必须继承此类并实现其抽象方法。
    """

    @abstractmethod
    def select_stocks(self, t_date: date) -> List[Dict[str, Any]]:
        """
        核心方法：根据给定的T日执行选股逻辑。

        Args:
            t_date (date): T日日期对象 (交易日)。策略应基于此日期之前的数据选股，
                          选出的股票将在 T+1 日建仓。

        Returns:
            List[Dict[str, Any]]: 选中的股票列表。
                                    每个元素是一个字典，包含股票信息和策略相关数据。
                                    执行引擎期望的字典键名应保持一致，例如：
                                    [
                                        {
                                            '股票代码': 'sh.600000', # 建议保留原始代码格式
                                            '股票名称': '浦发银行',
                                            '行业': '银行',
                                            '首板日期': '2023-10-26', # YYYY-MM-DD 格式字符串
                                            '首板价格': 10.50,        # 数值类型
                                            '回调周期': 3,            # 整数
                                            '板后走势': '稳定回调',    # 字符串
                                            '板后最高价': 11.20,      # 数值类型
                                            '板后最低价': 10.80,      # 数值类型
                                            '最高价日期': '20231030收盘价', # 特定格式字符串
                                            '最低价日期': '20231029开盘价', # 特定格式字符串
                                            '板后回调(%)': 25.50,     # 数值类型 (百分比回调幅度)
                                            # ... 其他策略可能需要的字段
                                        },
                                        ...
                                    ]
                                    如果没有选中股票，应返回空列表 []。
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        获取策略的唯一名称或描述。

        Returns:
            str: 策略名称，例如 "首板回调策略"。
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """
        获取策略运行时使用的关键参数。

        Returns:
            Dict[str, Any]: 策略参数字典，键为参数名，值为参数值。
                            例如：
                            {
                                'upper_limit': 0.75,
                                'lower_limit': 0.10,
                                'holding_period': 3
                            }
                            如果没有参数，可以返回空字典 {}。
        """
        pass

# 注意：这个接口定义了策略需要提供的功能，但不涉及具体的实现细节，
# 也不处理如数据库连接、文件读写（除了策略自身的配置）、结果保存等执行流程。
# 这些职责将由执行引擎（如修改后的 flu1.txt）来管理。