"""
TopologySwingStrategy: Trend-following strategy based on topological swing analysis.
Implements the BaseStrategy interface for use with BacktestEngine.
"""
from typing import List, Dict, Any
import pandas as pd
from .base import BaseStrategy, TradeSignal
from analysis.topology_trend import TopologicalTrendIdentifier


class TopologySwingStrategy(BaseStrategy):
    """
    Strategy that generates buy/sell signals based on confirmed swing points.
    
    Buy when a LOW swing is confirmed (entering uptrend).
    Sell when a HIGH swing is confirmed (entering downtrend).
    """
    
    @property
    def name(self) -> str:
        return "拓扑趋势策略 (Topology Swing)"
    
    def __init__(self):
        self.threshold_method = 'atr'
        self.threshold_value = 1.5
        self.auto_elbow = True
        
    def initialize(self, params: Dict[str, Any]) -> None:
        """
        Initialize strategy parameters.
        
        Supported params:
            threshold_method: 'atr' or 'fixed'
            threshold_value: float multiplier for threshold
            auto_elbow: bool, if True, auto-calculate optimal threshold
        """
        self.threshold_method = params.get('threshold_method', 'atr')
        self.threshold_value = params.get('threshold_value', 1.5)
        self.auto_elbow = params.get('auto_elbow', True)
    
    def optimize_params(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Use the Elbow Rule to find optimal threshold from analysis data.
        """
        if not self.auto_elbow or data.empty:
            return {'threshold_method': self.threshold_method, 'threshold_value': self.threshold_value}
        
        try:
            topo = TopologicalTrendIdentifier(data)
            best_threshold, _ = topo.optimize_threshold_elbow(method='atr')
            if best_threshold:
                return {'threshold_method': 'atr', 'threshold_value': best_threshold}
        except:
            pass
        
        return {'threshold_method': self.threshold_method, 'threshold_value': self.threshold_value}
    
    def generate_signals(self, data: pd.DataFrame, start_date: str, end_date: str) -> List[TradeSignal]:
        """
        Walk-forward signal generation using swing point confirmation.
        """
        signals = []
        data = data.reset_index(drop=True)
        
        # Find start index
        try:
            mask = pd.to_datetime(data['date']) >= pd.to_datetime(start_date)
            start_idx = data[mask].index[0]
        except IndexError:
            return signals
        
        # State tracking
        is_holding = False
        last_processed_conf_date = "1900-01-01"
        
        # Walk-forward simulation
        for i in range(start_idx, len(data)):
            current_date = str(data.at[i, 'date'])
            
            # Check end date
            if current_date > end_date:
                break
            
            current_close = float(data.at[i, 'close'])
            
            # Knowledge window: all data up to current bar
            snapshot = data.iloc[0:i+1].copy().reset_index(drop=True)
            
            # Run analysis
            algo = TopologicalTrendIdentifier(snapshot)
            swings = algo.identify_swings(
                threshold_method=self.threshold_method, 
                threshold_value=self.threshold_value
            )
            swings = algo.analyze_volume_price(swings)
            swings = algo.analyze_signals(swings)
            swings = algo.calculate_trend_score(swings)
            
            if not swings:
                continue
            
            # Get last confirmed swing (filter out trailing visual points)
            valid_swings = [s for s in swings if s.is_real]
            if not valid_swings:
                continue
            
            last_swing = valid_swings[-1]
            
            # Check for new confirmation event
            if last_swing.conf_date > last_processed_conf_date:
                last_processed_conf_date = last_swing.conf_date
                
                # Generate signal based on swing type
                if not is_holding and last_swing.type == 'LOW':
                    # Confirmed low -> Uptrend -> BUY
                    signals.append(TradeSignal(
                        date=current_date,
                        price=current_close,
                        action='BUY',
                        reason=f"确认底部 (评分:{last_swing.score:.0f})",
                        score=last_swing.score
                    ))
                    is_holding = True
                    
                elif is_holding and last_swing.type == 'HIGH':
                    # Confirmed high -> Downtrend -> SELL
                    signals.append(TradeSignal(
                        date=current_date,
                        price=current_close,
                        action='SELL',
                        reason=f"确认顶部 (评分:{last_swing.score:.0f})",
                        score=last_swing.score
                    ))
                    is_holding = False
        
        return signals
