import hashlib
import json
from datetime import datetime

class StateManager:
    """
    Manages the state of sent notifications to prevent spam.
    Uses in-memory content fingerprinting to detect meaningful changes.
    """
    
    def __init__(self):
        self.seen_sectors_p1 = set()
        self.seen_sectors_p2 = set()
        self.seen_sectors_p3 = set()
        
    def extract_new_items(self, report_data: dict) -> dict:
        """
        Compare current report_data against seen state.
        Returns a new report_data dict containing ONLY newly entered sectors and
        stocks belonging to those new sectors.
        Returns None if no new sectors are found.
        """
        current_p1 = {c['concept_name'] for c in report_data.get('pool_1', [])}
        current_p2 = {c['concept_name'] for c in report_data.get('pool_2', [])}
        current_p3 = {c['concept_name'] for c in report_data.get('pool_3', [])}
        
        # Calculate Diffs (New items only)
        new_p1_names = current_p1 - self.seen_sectors_p1
        new_p2_names = current_p2 - self.seen_sectors_p2
        new_p3_names = current_p3 - self.seen_sectors_p3
        
        # If no new sectors in any pool, return None
        if not (new_p1_names or new_p2_names or new_p3_names):
            return None
            
        # Update State
        self.seen_sectors_p1.update(new_p1_names)
        self.seen_sectors_p2.update(new_p2_names)
        self.seen_sectors_p3.update(new_p3_names)
        
        # Construct Diff Report
        diff_report = {
            'timestamp': report_data.get('timestamp'),
            'pool_1': [c for c in report_data.get('pool_1',[]) if c['concept_name'] in new_p1_names],
            'pool_2': [c for c in report_data.get('pool_2',[]) if c['concept_name'] in new_p2_names],
            'pool_3': [c for c in report_data.get('pool_3',[]) if c['concept_name'] in new_p3_names],
        }
        
        # Filter Stocks: Only include stocks whose "source_concept" or "matched_concept"
        # includes one of the NEWLY entered sectors.
        # Note: Since the pools are nested (P3 < P2 < P1), we care about any new entry.
        # Union of all new names implies the "New Hot Zones".
        all_new_concepts = new_p1_names | new_p2_names | new_p3_names
        
        def is_relevant(stock_item):
            # Check source_concept
            sc = stock_item.get('source_concept', '')
            if any(n in sc for n in all_new_concepts):
                return True
            # Check matched_concept
            mc = stock_item.get('matched_concept', '')
            if any(n in mc for n in all_new_concepts):
                return True
            return False
            
        diff_report['lottery_pool'] = [s for s in report_data.get('lottery_pool', []) if is_relevant(s)]
        diff_report['small_cap_pool'] = [s for s in report_data.get('small_cap_pool', []) if is_relevant(s)]
        
        return diff_report

    # Legacy method for compatibility if needed (but we are replacing usage)
    def should_send(self, report_data: dict) -> bool:
        return False
