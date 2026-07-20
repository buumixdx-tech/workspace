from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class BaseSnapshotProvider(ABC):
    """
    快照数据源的抽象基类。
    所有具体的数据源适配器（如 Tencent, Sina）都必须继承此类。
    """

    @abstractmethod
    def get_batch(self, codes: List[str]) -> Any:
        """
        发送网络请求，获取一批股票的原始响应数据。
        :param codes: 经过 format_code 处理后的代码列表 (e.g. ['sh600000', 'sz000001'])
        :return: 原始响应内容 (str, json, etc.)，若失败返回 None
        """
        pass

    @abstractmethod
    def parse(self, response: Any, snapshot_time: datetime) -> List[Dict]:
        """
        解析原始响应，返回标准化的数据字典列表。
        :param response: get_batch 返回的原始数据
        :param snapshot_time: 批次逻辑时间
        :return: 符合 ClickHouse stock_snapshot_intraday 表结构的字典列表
        """
        pass

    @abstractmethod
    def format_code(self, ck_code: str) -> str:
        """
        将 ClickHouse 标准代码转换为该数据源要求的格式。
        Code: sh.600000 -> Provider: sh600000
        """
        pass
    
    @property
    @abstractmethod
    def batch_size(self) -> int:
        """该数据源建议的单次请求大小"""
        pass
