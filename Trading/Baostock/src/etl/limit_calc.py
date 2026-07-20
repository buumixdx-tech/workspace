
import numpy as np
import pandas as pd
import datetime

class LimitCalculator:
    """
    Calculator for A-share price limits (Limit Up / Limit Down).
    Handles complex rules:
    1. Main Board: 10% (ST 5%)
    2. ChiNext (300): 10% before 2020-08-24, 20% after.
    3. STAR Market (688): 20%.
    4. BJ Stock Exchange (bj): 30%.
    5. Rounding: Round to 0.01 (Fen).
    """

    DATE_CHINEXT_REGISTRATION = pd.Timestamp("2020-08-24")
    
    @staticmethod
    def calculate_limits(df):
        """
        Input DataFrame must have: 'code', 'date', 'preclose', 'isST'
        Returns DataFrame with added columns: 'limit_up_price', 'limit_down_price', 'limit_ratio'
        """
        # Ensure date is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])

        # 1. Determine Board Type
        # Vectorized string checking
        code_series = df['code'].astype(str)
        
        is_bj = code_series.str.startswith(('bj.4', 'bj.8'))
        is_star = code_series.str.startswith('sh.688')
        is_chinext = code_series.str.startswith('sz.300')
        
        # 2. Determine Ratio
        # Default 0.1
        ratios = pd.Series(0.1, index=df.index)
        
        # BJ: 0.3
        ratios[is_bj] = 0.3
        
        # STAR: 0.2
        ratios[is_star] = 0.2
        
        # ST (Main Board Only) -> 0.05
        # Note: ST on ChiNext/STAR is still 0.2
        is_st = df['isST'] == 1
        is_main_st = is_st & (~is_chinext) & (~is_star) & (~is_bj)
        ratios[is_main_st] = 0.05
        
        # ChiNext Special Rule
        # Before 2020-08-24: 0.1 (or 0.05 if ST)
        # After 2020-08-24: 0.2 (ST included)
        
        if is_chinext.any():
            mask_chinext_old = is_chinext & (df['date'] < LimitCalculator.DATE_CHINEXT_REGISTRATION)
            mask_chinext_new = is_chinext & (df['date'] >= LimitCalculator.DATE_CHINEXT_REGISTRATION)
            
            # Old ChiNext: Standard Main Board Rules apply (0.1, ST 0.05)
            # Check those who are ST in the old era
            is_st_old_chinext = mask_chinext_old & is_st
            ratios[mask_chinext_old] = 0.1
            ratios[is_st_old_chinext] = 0.05
            
            # New ChiNext: All 0.2
            ratios[mask_chinext_new] = 0.2

        # 3. Calculate Prices with Rounding
        # Formula: round(preclose * (1 +/- ratio), 2)
        # Usage of standard round vs numpy round?
        # A-share uses standard rounding usually.
        
        # Caution: Python round() maps x.5 to nearest even number!
        # e.g. round(2.5) -> 2, round(3.5) -> 4.
        # This is NOT what we want for money.
        # We want arithmetic rounding (0.5 always up).
        # Actually in finance, usually we add epsilon.
        
        preclose = df['preclose']
        
        # Add epsilon to handle floating point issues and ensure x.005 rounds up
        # Standard implementation for "Round Half Up"
        def round_half_up(n, decimals=0):
            multiplier = 10 ** decimals
            return np.floor(n * multiplier + 0.5) / multiplier

        up_prices = round_half_up(preclose * (1 + ratios), 2)
        down_prices = round_half_up(preclose * (1 - ratios), 2)
        
        df = df.copy()
        df['limit_ratio'] = ratios.astype('float32')
        df['limit_up_price'] = up_prices.astype('float32')
        df['limit_down_price'] = down_prices.astype('float32')
        
        return df
