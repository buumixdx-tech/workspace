
import pandas as pd

class StockStrategy:
    """Base strategy interface"""
    def filter(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        raise NotImplementedError

class StrategyS1(StockStrategy):
    """
    策略一:
    1. 市值 <= 35亿
    2. 流通市值占比 <= 50%
    3. 排除 ST
    4. 排除 30开头(创业板), 68开头(科创板), 92开头(北交所), BJ(北交所)
    """
    def filter(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        df_sel = df.copy()
        df_sel = df_sel[df_sel["总市值"] > 0]
        df_sel["流通占比"] = df_sel["流通市值"] / df_sel["总市值"]
        
        cond_mcap = df_sel["总市值"] <= 35 * 100000000
        cond_float_ratio = df_sel["流通占比"] <= 0.5
        cond_not_st = df_sel["是否st"] == "否"
        
        def is_main_board(code):
            num_part = code.split('.')[-1]
            if num_part.startswith('30'): return False
            if num_part.startswith('68'): return False
            if num_part.startswith('92'): return False
            if code.startswith('BJ'): return False 
            return True
        cond_board = df_sel["股票代码"].apply(is_main_board)
        
        final_selection = df_sel[cond_mcap & cond_float_ratio & cond_not_st & cond_board]
        final_selection = final_selection.sort_values(by="总市值")
        
        return {"Selected": final_selection}

class StrategyS2(StockStrategy):
    """
    策略二:
    1. 排除 ST
    2. 排除 30开头(创业板), 68开头(科创板), 92开头(北交所), BJ(北交所)
    3. 分两档:
       - selected1: 流通市值 <= 10亿
       - selected2: 流通市值 <= 15亿
    """
    def filter(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        df_base = df.copy()
        df_base = df_base[df_base["总市值"] > 0]
        
        cond_not_st = df_base["是否st"] == "否"
        
        def is_main_board(code):
            num_part = code.split('.')[-1]
            if num_part.startswith('30'): return False
            if num_part.startswith('68'): return False
            if num_part.startswith('92'): return False
            if code.startswith('BJ'): return False 
            return True
        cond_board = df_base["股票代码"].apply(is_main_board)
        
        df_common = df_base[cond_not_st & cond_board]
        
        selected1 = df_common[df_common["流通市值"] <= 10 * 100000000].copy()
        selected1 = selected1.sort_values(by="流通市值")
        
        selected2 = df_common[df_common["流通市值"] <= 15 * 100000000].copy()
        selected2 = selected2.sort_values(by="流通市值")
        
        return {
            "selected1": selected1,
            "selected2": selected2
        }

class StrategyS3(StockStrategy):
    """
    策略三:
    1. 剔除科创板 (688开头)、北交所 (8, 4, 92开头)
    2. 流通市值 < 20亿
    3. 剔除 ST / *ST
    """
    def filter(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        df_sel = df.copy()
        
        def is_not_star_or_bj(code):
            # code could be "SH.688123" or similar
            num_part = code.split('.')[-1]
            # 1. 剔除科创板 (688开头)
            if num_part.startswith('68'): return False
            # 2. 剔除北交所 (8, 4, 92开头)
            if num_part.startswith('8') or num_part.startswith('4') or num_part.startswith('92'): return False
            # 额外防御：检查前缀
            if code.startswith('BJ'): return False
            return True
        
        cond_board = df_sel["股票代码"].apply(is_not_star_or_bj)
        cond_float_mcap = df_sel["流通市值"] < 20 * 100000000
        cond_not_st = df_sel["是否st"] == "否"
        
        final_selection = df_sel[cond_board & cond_float_mcap & cond_not_st]
        final_selection = final_selection.sort_values(by="流通市值")
        
        return {"Selected": final_selection}

class StrategyS5(StockStrategy):
    """
    策略五:
    1. 剔除北交所 (8, 4, 92开头)，保留科创板
    2. 流通市值在 12亿 - 20亿 之间
    3. 剔除 ST / *ST
    """
    def filter(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        df_sel = df.copy()
        
        def is_not_bj(code):
            num_part = code.split('.')[-1]
            # 剔除北交所 (8, 4, 92开头)
            if num_part.startswith('8') or num_part.startswith('4') or num_part.startswith('92'): return False
            if code.startswith('BJ'): return False
            return True
        
        cond_board = df_sel["股票代码"].apply(is_not_bj)
        cond_float_mcap = (df_sel["流通市值"] >= 12 * 100000000) & (df_sel["流通市值"] <= 20 * 100000000)
        cond_not_st = df_sel["是否st"] == "否"
        
        final_selection = df_sel[cond_board & cond_float_mcap & cond_not_st]
        final_selection = final_selection.sort_values(by="流通市值")
        
        return {"Selected": final_selection}
