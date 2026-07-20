import requests
import pandas as pd
from datetime import datetime
import time
import sys
import os
import py_mini_racer
from io import StringIO
from bs4 import BeautifulSoup

# Try to import _get_file_content_ths from akshare
try:
    from akshare.stock_feature.stock_board_concept_ths import _get_file_content_ths
except ImportError:
    # If not found, we implement a simple loader assuming ths.js is available or we need to find it
    # But usually akshare is installed.
    print("Warning: Could not import _get_file_content_ths")
    sys.exit(1)

def get_v_code():
    """Generates the 'v' cookie required by THS."""
    js_content = _get_file_content_ths("ths.js")
    js = py_mini_racer.MiniRacer()
    js.eval(js_content)
    return js.call("v")

def test_pagination():
    print("Testing THS Concept Board pagination (No Login)...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Referer": "http://q.10jqka.com.cn/gn/"
    }
    
    total_records = 0
    max_pages = 10 # Try to fetch up to 10 pages (~500 concepts)
    
    for page in range(1, max_pages + 1):
        v_code = get_v_code()
        headers["Cookie"] = f"v={v_code}"
        
        # URL for Concept Board Rankings
        url = f"http://q.10jqka.com.cn/gn/index/field/199112/order/desc/page/{page}/ajax/1/"
        
        print(f"Fetching Page {page}...", end=" ")
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                print(f"Failed (Status: {r.status_code})")
                break
                
            soup = BeautifulSoup(r.text, "lxml")
            tables = soup.find_all("table")
            
            if not tables:
                print("No table found (Likely end of data or blocked).")
                # print(r.text[:500]) # Debug HTML
                break
                
            df = pd.read_html(StringIO(str(tables[0])))[0]
            # print(f"Columns found: {df.columns}") # Debug columns
            
            count = len(df)
            total_records += count
            
            # Try to get name dynamically
            # Debug: what is inside?
            print(f"DataFrame Content:\n{df.to_string()}")
            
            first_col = df.columns[1] # Usually Index 0 is '序号', 1 is '板块' or similar
            first_val = df.iloc[0, 1] if count > 0 else "N/A"
            
            print(f"Success! Got {count} rows. First ({first_col}): {first_val}")
            
            if count < 20: # Assuming page size is at least 20 or 50
                print("  - Page seems incomplete or last page.")
                
            # If we get duplicate data or empty, it means we hit a limit?
            # THS usually returns empty table or same page if blocked?
            # Let's check first item code or name to ensure uniqueness if needed, but simple count is enough for connectivity test.
            
            time.sleep(1.5) # Be nice
            
        except Exception as e:
            print(f"Error: {e}")
            break
            
    print("-" * 30)
    print(f"Test Complete. Total concepts fetched: {total_records}")
    if total_records > 300:
        print("✅ Pagination works! We can see full market data.")
    else:
        print("⚠️ Warning: Data count seems low. Check if limited.")

if __name__ == "__main__":
    test_pagination()
