import sys
import os
import time
import akshare as ak
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the logic function directly
from market.fetch_concept_board_info import fetch_board_info

def test_full_crawl():
    print("Getting concept list from Akshare...")
    try:
        concepts_df = ak.stock_board_concept_name_ths()
        if concepts_df.empty:
            print("Failed to get concept list.")
            return
            
        total = len(concepts_df)
        print(f"Akshare returned {total} concepts.")
        
        print("Fetching details for the FIRST concept only to verify fields...")
        
        # Take the first one
        first_row = concepts_df.iloc[0]
        code = first_row['code']
        name = first_row['name']
        
        print(f"Target: {name} ({code})")
        
        data = fetch_board_info(code, name)
        
        if data:
            print("\n✅ Valid Data Received:")
            for k, v in data.items():
                print(f"  - {k}: {v}")
        else:
            print("\n❌ Failed to fetch data.")

    except Exception as e:
        print(f"Test Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_full_crawl()
