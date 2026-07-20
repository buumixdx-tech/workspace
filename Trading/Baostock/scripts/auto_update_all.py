import os
import sys
import time
from datetime import datetime
import traceback

# Force standard output to use UTF-8 encoding to prevent UnicodeEncodeError on Windows
# This is crucial when running in environments with GBK default encoding (like Chinese Windows)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Resolve project root and add to sys.path
# Script is located in scripts/, so root is one level up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import ETL modules from the src package
try:
    from src.etl import etl_securities
    from src.etl import etl_kline_loader
    from src.etl import etl_factors
except ImportError as e:
    print(f"[FATAL] Failed to import ETL modules: {e}")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Project Root: {PROJECT_ROOT}")
    sys.exit(1)

def run_pipeline():
    """
    Executes the full data maintenance pipeline:
    1. Update Securities List (Detect IPOs/Delistings)
    2. Incremental K-Line Update (Fetch missing daily data)
    3. Incremental Factor Update (Update adjustment factors)
    """
    print("-" * 60)
    print(f"[START] Automated Data Maintenance Pipeline")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    overall_start = time.time()

    # Step 1: Securities List
    # We must update the list first so the loader knows about new stock codes
    print("\n[STEP 1/3] Refreshing Securities Info...")
    try:
        success, msg = etl_securities.run_etl()
        status = "[OK]" if success else "[FAILED]"
        print(f"{status} {msg}")
        if not success:
            print("[WARN] Securities update failed, proceeding to next step with existing list...")
    except Exception:
        print(f"[ERROR] Step 1 crashed:\n{traceback.format_exc()}")

    # Step 2: Incremental K-Line Loading
    # Fetch daily k-lines for all active stocks and indices
    print("\n[STEP 2/3] Loading Incremental K-Line Data...")
    try:
        # mode='incremental' ensures we only fetch missing data from max(date)
        success, msg = etl_kline_loader.run_etl(mode='incremental')
        status = "[OK]" if success else "[FAILED]"
        print(f"{status} {msg}")
    except Exception:
        print(f"[ERROR] Step 2 crashed:\n{traceback.format_exc()}")

    # Step 3: Incremental Factor Loading
    # Update factors to support hfq/qfq calculations in tools
    print("\n[STEP 3/3] Loading Incremental Adjustment Factors...")
    try:
        success, msg = etl_factors.run_etl(mode='incremental')
        status = "[OK]" if success else "[FAILED]"
        print(f"{status} {msg}")
    except Exception:
        print(f"[ERROR] Step 3 crashed:\n{traceback.format_exc()}")

    # Final Summary
    overall_duration = (time.time() - overall_start) / 60
    print("\n" + "-" * 60)
    print(f"[FINISH] Pipeline Completed")
    print(f"Total Duration: {overall_duration:.2f} minutes")
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

if __name__ == "__main__":
    # Required for Windows multiprocessing (used in etl_kline_loader)
    import multiprocessing
    multiprocessing.freeze_support()
    
    run_pipeline()
