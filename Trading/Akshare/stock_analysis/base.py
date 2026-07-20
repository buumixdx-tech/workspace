from abc import ABC, abstractmethod
from typing import List
from .types import StockTask, AnalysisResult

class BaseProcessor(ABC):
    """
    Abstract base class for all stock analysis strategies.
    Ensures that any new strategy (Financial, Technical, News) follows the same protocol.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy Name identifier"""
        pass

    @property
    @abstractmethod
    def code(self) -> str:
        """Strategy Code identifier (e.g. p1, p2)"""
        pass

    @property
    @abstractmethod
    def report_config(self) -> dict:
        """
        Returns a configuration dictionary for the runner to format the output.
        Example: {
            "columns": ["col1", "col2"],
            "widths": {"col1": 20},
            "merge_cols": 4
        }
        """
        pass

    @abstractmethod
    def process(self, task: StockTask) -> List[AnalysisResult]:
        """
        Core logic to process a single stock task.
        Must return a list of results (one task can generate multiple result rows, 
        e.g. multiple hotspot associations).
        """
        pass
