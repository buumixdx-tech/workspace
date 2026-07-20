import pandas as pd
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import date
from .topology_trend import TopologicalTrendIdentifier, SwingPoint

class SimulationState(Enum):
    HOLD_CASH = "空仓 (Cash)"
    HOLD_LONG = "持仓 (Long)"

@dataclass
class TradeSignal:
    date: str
    price: float
    type: str # 'BUY' or 'SELL'
    reason: str
    score: float

class TradeSignalGenerator:
    def __init__(self, full_data: pd.DataFrame, trend_algo_class=TopologicalTrendIdentifier):
        """
        Args:
            full_data: The entire dataset to simulate.
            trend_algo_class: The class to use for detecting trends.
        """
        self.full_data = full_data.reset_index(drop=True)
        self.algo_class = trend_algo_class
        self.signals: List[TradeSignal] = []
        self.daily_states: List[Dict] = []
        self.logs: List[str] = []
        
    def log(self, msg: str):
        self.logs.append(msg)
        
    def run_simulation(self, start_date: str, end_date: str = None, threshold_method='atr', threshold_value=1.5) -> pd.DataFrame:
        """
        Runs a walk-forward simulation.
        
        Args:
            start_date: Simulation start date (YYYY-MM-DD)
            end_date: Simulation end date (YYYY-MM-DD). If None, runs to end of data.
        """
        # Find start index
        try:
            # Ensure date formats match for comparison
            # self.full_data['date'] might be str or date/datetime objects.
            # start_date is passed as str.
            # Robust way: Convert both to pd.Timestamp for the mask
            mask = pd.to_datetime(self.full_data['date']) >= pd.to_datetime(start_date)
            start_idx = self.full_data[mask].index[0]
        except IndexError:
            self.log(f"Error: Start date {start_date} not found in data.")
            return pd.DataFrame()
            
        current_state = SimulationState.HOLD_CASH
        
        self.log(f"Starting Simulation from {start_date}, Index: {start_idx}")
        
        # State tracking for signal generation
        # We track the 'conf_date' of the last swing we acted upon.
        # If the topology suddenly reveals a NEW swing with a later conf_date, that's our signal.
        last_processed_swing_conf_date = "1900-01-01"
        
        # Simulation Loop
        for i in range(start_idx, len(self.full_data)):
            current_date = self.full_data.at[i, 'date']
            
            # Check End Date
            if end_date:
                # Compare as strings or timestamps
                if str(current_date) > str(end_date):
                    self.log(f"End date reached: {current_date} > {end_date}")
                    break
            
            current_close = self.full_data.at[i, 'close']
            
            # 1. Define Knowledge Window
            # Use data from BEGINNING up to today (i) to ensure strict consistency with historical analysis.
            daily_snapshot = self.full_data.iloc[0 : i+1].copy().reset_index(drop=True)
            snapshot_len = len(daily_snapshot)
            
            # 2. Run Analysis
            algo = self.algo_class(daily_snapshot)
            swings = algo.identify_swings(threshold_method=threshold_method, threshold_value=threshold_value)
            # Optional: Analyze metadata if needed for score-based filtering
            swings = algo.analyze_volume_price(swings)
            swings = algo.analyze_signals(swings)
            swings = algo.calculate_trend_score(swings)
            
            if not swings:
                continue
                
            # Filter out visual-only trailing points
            # We want the last REAL confirmed swing.
            valid_swings = [s for s in swings if s.is_real]
            
            if not valid_swings:
                continue
                
            last_swing = valid_swings[-1]
            
            # 3. Detect Confirmation Event (State Change Detection)
            # Instead of checking index, we check: Is this a NEW swing we haven't processed yet?
            # We use 'conf_date' as the unique ID for the confirmation event.
            
            is_new_confirmation = False
            
            if last_swing.conf_date > last_processed_swing_conf_date:
                # A new swing point has appeared/confirmed!
                is_new_confirmation = True
                # Update our tracker so we don't signal again for THIS swing
                last_processed_swing_conf_date = last_swing.conf_date
                
                self.log(f"🔥 {current_date} NEW SIGNAL! SwingType: {last_swing.type}, ConfDate: {last_swing.conf_date}")
            
            # 4. State Machine Transition (Action)
            is_confirmed_today = is_new_confirmation # Alias for logic below
            
            # 4. State Machine Transition
            
            # 4. State Machine Transition
            
            # --- State: HOLD CASH ---
            if current_state == SimulationState.HOLD_CASH:
                if is_confirmed_today and last_swing.type == 'LOW':
                    # A Low is confirmed -> We are in an UP leg.
                    # Direct BUY
                    current_state = SimulationState.HOLD_LONG
                    self.signals.append(TradeSignal(
                        current_date, 
                        current_close, 
                        "BUY", 
                        f"确认底部 (评分:{last_swing.score:.0f})", 
                        last_swing.score
                    ))
            
            # --- State: HOLD LONG ---
            elif current_state == SimulationState.HOLD_LONG:
                if is_confirmed_today and last_swing.type == 'HIGH':
                    # A High is confirmed -> We are in a DOWN leg.
                    # Direct SELL
                    current_state = SimulationState.HOLD_CASH
                    self.signals.append(TradeSignal(
                        current_date, 
                        current_close, 
                        "SELL", 
                        f"确认顶部 (评分:{last_swing.score:.0f})", 
                        last_swing.score
                    ))

            # Record Daily State
            self.daily_states.append({
                "date": current_date,
                "close": current_close,
                "state": current_state.value,
                "last_swing_score": last_swing.score if last_swing else 0
            })
            
        return pd.DataFrame(self.daily_states)
