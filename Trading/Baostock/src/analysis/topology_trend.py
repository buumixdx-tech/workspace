import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import math

@dataclass
class SwingPoint:
    index: int
    date: str
    price: float
    type: str  # 'HIGH' or 'LOW'
    
    # Analysis Metrics (Populated later)
    amplitude: float = 0.0 # Percent change from prev point
    duration: int = 0      # Bar count from prev point
    vol_sum: float = 0.0   # Cumulative Volume
    amt_sum: float = 0.0   # Cumulative Amount
    efficiency: float = 0.0 # Abs(PriceChange) / VolSum (Scaled)
    
    # Backtest Readiness (Confirmation Lag)
    conf_index: int = -1  # Index where this swing was confirmed
    conf_date: str = ""   # Date where this swing was confirmed
    is_real: bool = True # False for the trailing temporary point
    
    # Quantitative Score
    score: float = 0.0    # -100 (Bear) to 100 (Bull)
    
    # Interpretation Signals
    signal_type: str = "" # 'BEAR_DIV', 'BULL_DIV', 'CLIMAX', etc.
    signal_text: str = "" # User friendly text
    
    # Stage Description (New)
    desc_text: str = ""   # Short Chinese description of the stage (e.g. "主升浪")
    
class TopologicalTrendIdentifier:
    def __init__(self, data: pd.DataFrame):
        """
        Args:
            data (pd.DataFrame): Must contain 'date', 'high', 'low', 'close' columns.
        """
        self.raw_data = data.copy().reset_index(drop=True)
        self.clean_data = None
        
    def preprocess_inclusion(self) -> pd.DataFrame:
        """
        Step 1: Inclusion Processing (K-line merging).
        Removes 'inside bars' to reduce noise.
        Standard ChanLun inclusion logic.
        """
        df = self.raw_data.copy()
        output_bars = []
        
        # We need at least 2 bars
        if len(df) < 2:
            self.clean_data = df
            return df

        # Initial direction (0: tentative, 1: up, -1: down)
        # We start by assuming first two define direction or just Up
        direction = 1 
        
        # Convert to records for faster iteration
        bars = df.to_dict('records')
        
        # Initialize with first bar
        current_bar = bars[0].copy()
        
        for i in range(1, len(bars)):
            next_bar = bars[i].copy()
            
            # Check for inclusion
            # Case 1: Next inside Current
            next_in_curr = (next_bar['high'] <= current_bar['high']) and (next_bar['low'] >= current_bar['low'])
            # Case 2: Current inside Next
            curr_in_next = (current_bar['high'] <= next_bar['high']) and (current_bar['low'] >= next_bar['low'])
            
            if next_in_curr or curr_in_next:
                # Inclusion detected, perform merge based on current direction
                if direction == 1: # Up Trend
                    new_high = max(current_bar['high'], next_bar['high'])
                    new_low = max(current_bar['low'], next_bar['low'])
                else: # Down Trend
                    new_high = min(current_bar['high'], next_bar['high'])
                    new_low = min(current_bar['low'], next_bar['low'])
                
                # Update 'next_bar' to be the merged bar (it effectively becomes the new 'current' in next iter)
                # We usually keep the date of the later bar or the extreme? 
                # ChanLun typically creates a virtual bar. We'll assign properties to next_bar.
                next_bar['high'] = new_high
                next_bar['low'] = new_low
                # We keep the volume/close of the later bar usually, or accumulate. 
                # For high/low detection, only high/low matter.
                
                # The 'current_bar' is effectively absorbed into 'next_bar' for the purpose of the ongoing chain,
                # BUT in strict implementations, we emit the modified bar?
                # Actually, standard logic:
                # If relationship found, signal is 'merge'. We do NOT output current_bar yet.
                # We update next_bar values and move on.
                current_bar = next_bar
            else:
                # No inclusion.
                # Determine new direction if applicable
                # Simple logic: If High rose and Low rose -> Up?
                # Strict ChanLun: Direction is determined by the relationship between valid distinct bars.
                if (next_bar['high'] > current_bar['high']) and (next_bar['low'] > current_bar['low']):
                    direction = 1
                elif (next_bar['high'] < current_bar['high']) and (next_bar['low'] < current_bar['low']):
                    direction = -1
                
                # Output the finished 'current_bar'
                output_bars.append(current_bar)
                current_bar = next_bar

        # Append last bar
        output_bars.append(current_bar)
        
        self.clean_data = pd.DataFrame(output_bars)
        return self.clean_data

    def identify_swings(self, threshold_method='atr', threshold_value=1.5) -> List[SwingPoint]:
        """
        Step 2 & 3: Identify Local Extrema and Filter by Threshold (Topological Simplification).
        
        threshold_method: 'fixed' (percentage), 'val' (absolute value), 'atr' (dynamic volatility)
        threshold_value: if 'atr', multiplies ATR. If 'fixed', 0.05 means 5%.
        """
        if self.clean_data is None:
            self.preprocess_inclusion()
            
        df = self.clean_data.reset_index(drop=True)
        highs = df['high'].values
        lows = df['low'].values
        dates = df['date'].values
        
        # 1. Identify raw fractals (Top/Bottom)
        # Top: H[i-1] < H[i] > H[i+1]
        # Bottom: L[i-1] > L[i] < L[i+1]
        # Note: After inclusion processing, we shouldn't have consecutive Equal highs involving containment, 
        # but adjacent bars can still be equal. We handle strict inequality or equality.
        
        potential_swings = []
        
        for i in range(1, len(df) - 1):
            # Top
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                potential_swings.append(SwingPoint(i, dates[i], highs[i], 'HIGH'))
            # Bottom
            elif lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                potential_swings.append(SwingPoint(i, dates[i], lows[i], 'LOW'))
                
        # 2. Filter / Connect Logic (ZigZag-like) to ensure Alternating High/Low
        # and enforce threshold.
        
        # Calculate Threshold
        noise_threshold = 0.0
        if len(df) <= 1:
            noise_threshold = threshold_value
        elif threshold_method == 'atr':
            # Calculate ATR simple approx
            # TR calculation: max(H-L, |H-C_prev|, |L-C_prev|)
            prev_close = df['close'].shift(1)
            tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev_close.fillna(lows[0])), 
                                                    np.abs(lows - prev_close.fillna(highs[0]))))
            avg_tr = np.mean(tr) 
            noise_threshold = avg_tr * threshold_value
        elif threshold_method == 'fixed':
            # Percentage of price
            avg_price = np.mean(df['close'])
            noise_threshold = avg_price * threshold_value
        else:
             noise_threshold = threshold_value
             
        final_swings = []
        
        # Initial search state
        # Find first significant point
        # We'll iteratively build the zigzag
        
        # Pointer to last confirmed swing
        last_swing = None
        
        # Temporary extreme search
        # If we are looking for a High, we track the max price seen since the last Low.
        # If price drops by X from that max, the max is confirmed.
        
        # Initialization
        # Determine initial direction based on first few bars
        # Simple start: Find first min or max that breaks threshold
        
        current_trend = 0 # 1: Up (Looking for High), -1: Down (Looking for Low)
        lowest_since_high = lows[0]
        highest_since_low = highs[0]
        lowest_idx = 0
        highest_idx = 0
        
        # We need a robust loop. The ZigZag algorithm is usually:
        for i in range(len(df)):
            price_h = highs[i]
            price_l = lows[i]
            
            if current_trend == 0:
                # Startup phase
                if price_h >  lows[0] + noise_threshold:
                    # Going Up
                    current_trend = 1
                    last_swing = SwingPoint(0, dates[0], lows[0], 'LOW') # Anchor at start
                    last_swing.conf_index = 0
                    last_swing.conf_date = dates[0]
                    final_swings.append(last_swing)
                    highest_since_low = price_h
                    highest_idx = i
                elif price_l < highs[0] - noise_threshold:
                    # Going Down
                    current_trend = -1
                    last_swing = SwingPoint(0, dates[0], highs[0], 'HIGH') # Anchor at start
                    last_swing.conf_index = 0
                    last_swing.conf_date = dates[0]
                    final_swings.append(last_swing)
                    lowest_since_high = price_l
                    lowest_idx = i
            
            elif current_trend == 1: # Uptrend, looking for High
                if price_h > highest_since_low:
                    highest_since_low = price_h
                    highest_idx = i
                
                # Reversal condition
                # If price drops from highest by threshold
                # CONSTRAINT: We cannot reverse on the SAME bar that set the High.
                # This prevents "High -> Low on same day" vertical lines.
                if i > highest_idx and price_l < highest_since_low - noise_threshold:
                    # Confirm the High
                    # Record Confirmation Time (Current bar i)
                    new_swing = SwingPoint(highest_idx, dates[highest_idx], highest_since_low, 'HIGH')
                    new_swing.conf_index = i
                    new_swing.conf_date = dates[i]
                    
                    final_swings.append(new_swing)
                    last_swing = new_swing
                    
                    # Switch to Down
                    current_trend = -1
                    lowest_since_high = price_l
                    lowest_idx = i
                    
            elif current_trend == -1: # Downtrend, looking for Low
                if price_l < lowest_since_high:
                    lowest_since_high = price_l
                    lowest_idx = i
                
                # Reversal condition
                # CONSTRAINT: We cannot reverse on the SAME bar that set the Low.
                if i > lowest_idx and price_h > lowest_since_high + noise_threshold:
                    # Confirm the Low
                    # Record Confirmation Time (Current bar i)
                    new_swing = SwingPoint(lowest_idx, dates[lowest_idx], lowest_since_high, 'LOW')
                    new_swing.conf_index = i
                    new_swing.conf_date = dates[i]
                    
                    final_swings.append(new_swing)
                    last_swing = new_swing
                    
                    # Switch to Up
                    current_trend = 1
                    highest_since_low = price_h
                    highest_idx = i
                    
        # Handle trailing edge
        # Always add the last bar as a swing point to close the loop
        if final_swings:
            last_confirmed = final_swings[-1]
            last_bar_idx = len(df) - 1
            last_bar_date = dates[last_bar_idx]
            
            # If the last bar is already the last swing, do nothing
            if last_confirmed.index != last_bar_idx:
                # Determine type based on previous swing
                # If last was LOW, we are currently in an UP leg -> treat last bar as HIGH
                # If last was HIGH, we are currently in a DOWN leg -> treat last bar as LOW
                if last_confirmed.type == 'LOW':
                    # Current leg is UP, so the end is a tentative HIGH
                    # We use the HIGH price of the last bar usually? 
                    # OR we follow the current trend state?
                    # Since we are forcing a point, using the Close or extreme is a choice.
                    # Using the High for a potential High is consistent.
                    final_swing = SwingPoint(last_bar_idx, last_bar_date, highs[last_bar_idx], 'HIGH')
                    final_swing.conf_index = last_bar_idx
                    final_swing.conf_date = last_bar_date
                    final_swing.is_real = False # Flag as tentative/visual only
                    final_swings.append(final_swing)
                else:
                    # Current leg is DOWN, so end is a tentative LOW
                    final_swing = SwingPoint(last_bar_idx, last_bar_date, lows[last_bar_idx], 'LOW')
                    final_swing.conf_index = last_bar_idx
                    final_swing.conf_date = last_bar_date
                    final_swing.is_real = False # Flag as tentative/visual only
                    final_swings.append(final_swing)
        
        return final_swings

    def optimize_threshold_elbow(self, method='atr', start=0.5, end=4.0, step=0.1) -> Tuple[float, Dict]:
        """
        Implements the 'Elbow Method' to find the optimal threshold.
        
        Logic:
        1. Iterate through a range of thresholds (x-axis).
        2. Count the number of identified swings (y-axis).
        3. The curve will be decaying (Hyperbolic-like).
        4. Find the point of maximum curvature (Elbow) using the Kneedle algorithm concept
           (Max distance from the line connecting start and end points).
           
        Returns:
            best_threshold (float): The optimal multiplier/value.
            debug_data (dict): Data for plotting the curve (x, y, elbow_index).
        """
        thresholds = np.arange(start, end + step, step)
        segment_counts = []
        
        for val in thresholds:
            swings = self.identify_swings(threshold_method=method, threshold_value=val)
            # Count segments (swings - 1), but swings count is fine as proxy
            segment_counts.append(len(swings))
            
        # --- Kneedle Algorithm (Vector Projection) ---
        x = thresholds
        y = np.array(segment_counts)
        
        if len(x) < 3 or y[0] == y[-1]:
            # Degenerate case, return middle or start
            return x[0], {"x": x, "y": y}
            
        # 1. Normalize to [0, 1]
        x_norm = (x - x.min()) / (x.max() - x.min())
        y_norm = (y - y.min()) / (y.max() - y.min())
        
        # 2. Vector from Start(0, y_0) to End(1, y_n)
        # Note: Since Y is decreasing, Start is (0, 1) usually, End is (1, 0) in normalized space if fully utilized
        # Actually standard formula: vector V = P_end - P_start
        # We want point P on curve that maximizes distance to line P_start->P_end
        
        # Line eq: Ax + By + C = 0
        # P1(x1, y1), P2(x2, y2). 
        # (y1 - y2)x + (x2 - x1)y + x1y2 - x2y1 = 0
        
        x1, y1 = x_norm[0], y_norm[0]
        x2, y2 = x_norm[-1], y_norm[-1]
        
        distances = []
        for i in range(len(x_norm)):
            px, py = x_norm[i], y_norm[i]
            # Distance from point to line defined by P1 and P2
            # d = |(y2-y1)x0 - (x2-x1)y0 + x2y1 - y2x1| / sqrt((y2-y1)^2 + (x2-x1)^2)
            # Simplified since we just want max, denominator is constant.
            # But standard implementation:
            num = np.abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
            distances.append(num)
            
        elbow_idx = np.argmax(distances)
        best_threshold = x[elbow_idx]
        
        return best_threshold, {
            "x": x,
            "y": y,
            "elbow_idx": elbow_idx,
            "elbow_x": best_threshold,
            "elbow_y": y[elbow_idx]
        }
        
    def analyze_volume_price(self, swings: List[SwingPoint]) -> List[SwingPoint]:
        """
        Calculates volume/price dynamics for each wave segment defined by the swings.
        Populates metrics into the SwingPoint objects.
        """
        if not swings or len(swings) < 2:
            return swings
            
        df = self.raw_data  # Use raw data to get volume
        
        # We iterate from the 2nd point, looking back at the segment formed with prev point
        for i in range(1, len(swings)):
            start_p = swings[i-1]
            end_p = swings[i]
            
            # Slice data [start : end+1] (Inclusive)
            # Note: start_p.index and end_p.index are indices in 'clean_data' if inclusion used?
            # Wait, identify_swings uses 'clean_data' indices.
            # BUT, clean_data has 'date'. We should map back to raw_data via Date for accurate Volume sum.
            # Using simple index slicing on raw_data might be off if raw_data != clean_data (due to inclusion).
            # Robust way: Filter raw_data by Date Range.
            
            segment_mask = (df['date'] >= start_p.date) & (df['date'] <= end_p.date)
            segment_df = df.loc[segment_mask]
            
            if segment_df.empty:
                continue
                
            # Calcs
            vol_sum = segment_df['volume'].sum()
            amt_sum = segment_df['amount'].sum()
            duration = len(segment_df)
            
            price_change = end_p.price - start_p.price
            amplitude = (price_change / start_p.price) if start_p.price != 0 else 0
            
            # Efficiency: Price Movement per Unit of Volume
            # Scaled to avoid tiny numbers: (PercentChange * 100) / (Vol / 1M) -> just a heuristic score
            # A simple physics view: Displacement / Effort
            # We use Abs(Amplitude) because efficiency is scalar.
            # Avoid div by zero
            eff = 0.0
            if vol_sum > 0:
                eff = abs(price_change) / vol_sum * 1000000 # Normalized roughly
            
            # Store in the END point (representing the wave that just finished)
            end_p.amplitude = amplitude
            end_p.duration = duration
            end_p.vol_sum = vol_sum
            end_p.amt_sum = amt_sum
            end_p.efficiency = eff
            
        return swings

    def analyze_signals(self, swings: List[SwingPoint]) -> List[SwingPoint]:
        """
        Inter-Wave Analysis: Compares wave N with wave N-2 to detect divergences.
        Populates signal_type and signal_text.
        """
        if not swings or len(swings) < 3:
            return swings
            
        # Iterate starting from 3rd point (Index 2) to have a comparison (Index 0)
        # We compare leg ending at i (end_p) with leg ending at i-2 (prev_p)
        for i in range(2, len(swings)):
            curr = swings[i]
            prev = swings[i-2]
            
            # Must be same type to compare (High vs High, Low vs Low)
            if curr.type != prev.type:
                continue
                
            # 1. Bearish Divergence (顶背离)
            # Occurs at Swing Highs
            if curr.type == 'HIGH':
                # Condition: Price made a Higher High
                if curr.price > prev.price:
                    # Check Energy (Volume)
                    # If Volume is significantly lower (< 80% of prev), it indicates exhaustion
                    if curr.vol_sum < prev.vol_sum * 0.8:
                        curr.signal_type = "BEAR_DIV"
                        curr.signal_text = "⚠️量价顶背离"
                    
                    # Also check Efficiency: If Price moved less but Vol was high (Churning)? 
                    # If Efficiency dropped significantly while Price is higher? 
                    # Typically Divergence is Price Up, Indicator Down.
                    
            # 2. Bullish Divergence / Absorption (底背离/承接)
            # Occurs at Swing Lows
            elif curr.type == 'LOW':
                # Condition: Price made a Lower Low
                if curr.price < prev.price:
                    # Logic: If Trend is strong, Volume should increase on drops? 
                    # Actually, "Stopping Volume" or "Absorption" is often:
                    # Price goes lower, but selling pressure (Volume) dries up.
                    if curr.vol_sum < prev.vol_sum * 0.7:
                        curr.signal_type = "BULL_DIV"
                        curr.signal_text = "✅缩量新低(惜售)"
                    # OR: High Volume but Price didn't drop much (Efficiency Low)
                    # This means huge effort to push down but support is strong.
                    # Hard to quantify simply, stick to Volume Divergence.

        return swings
    
    def calculate_trend_score(self, swings: List[SwingPoint]) -> List[SwingPoint]:
        """
        Calculates a composite 'Health Score' (-100 to 100) for each wave.
        Base Logic:
        - Up Wave (High): Positive Score
        - Down Wave (Low): Negative Score
        - Magnitude: Determined by Amplitude, Efficiency, and Signals.
        """
        if not swings:
            return swings
            
        for s in swings:
            # Base Direction
            base_score = 50 if s.type == 'HIGH' else -50
            
            # 1. Momentum Factor (Amplitude)
            # Cap amplitude bonus at +/- 20
            # E.g. A 10% move -> +10 points
            amp_points = s.amplitude * 100 
            # Clamp to reasonable impact
            amp_points = max(-30, min(30, amp_points))
            
            # 2. Efficiency Factor
            # High Efficiency (>2.0) adds points to the direction
            # Low Efficiency (<0.5) subtracts points (indicates struggle)
            eff_bonus = 0
            if s.efficiency > 2.0:
                eff_bonus = 10
            elif s.efficiency < 0.5 and s.vol_sum > 0:
                eff_bonus = -15 # Churning warning
                
            # Directional application of efficiency
            # If UP wave and efficient -> Good (+10)
            # If UP wave and inefficient -> Bad (-15)
            # If DOWN wave and efficient -> Strong Down (More Negative)
            if s.type == 'HIGH':
                base_score += amp_points + eff_bonus
            else:
                base_score += amp_points - eff_bonus # amp is negative for Low, so adding it makes score lower (correct)
                
            # 3. Divergence Penalty/Bonus (Heavy Weight)
            if s.signal_type == "BEAR_DIV":
                base_score -= 40 # Strong penalty for Up wave
            elif s.signal_type == "BULL_DIV":
                base_score += 40 # Strong support for Down wave (makes it less negative, closer to 0 or positive)
            
            # Final Clamp -100 to 100
            s.score = max(-100, min(100, base_score))
            
            # --- Generate Description Logic ---
            tags = []
            
            # 1. Trend Strength Tags
            if s.score >= 80:
                tags.append("🔥主升")
            elif 20 <= s.score < 80:
                tags.append("↗稳健")
            elif -20 < s.score < 20:
                tags.append("↝震荡")
            elif -80 < s.score <= -20:
                tags.append("↘走弱")
            elif s.score <= -80:
                tags.append("❄️主跌")
                
            # 2. Efficiency Tags
            if s.efficiency > 3.0:
                tags.append("🚀轻盈") # Very little volume needed to move price
            elif s.efficiency < 0.6 and s.vol_sum > 0:
                # If Moving Up but heavy
                if s.type == 'HIGH':
                    tags.append("🐢滞涨")
                # If Moving Down but heavy (Support?)
                elif s.type == 'LOW':
                    tags.append("🛡️抵抗")
            
            # 3. Add Warnings
            if s.signal_text:
                tags.append(s.signal_text)
                
            s.desc_text = " ".join(tags)
            
        return swings
