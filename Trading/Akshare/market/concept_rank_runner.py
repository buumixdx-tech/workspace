import sys
import os
import time
import pandas as pd
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import py_mini_racer
# 尽量复用 akshare 的 js
from akshare.stock_feature.stock_board_concept_ths import _get_file_content_ths
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.ck_client import ClickHouseClient

# Configuration
INTERVAL_SECONDS = 600 # 10 minutes

def get_v_code():
    """Generates the 'v' cookie required by THS."""
    js_content = _get_file_content_ths("ths.js")
    js = py_mini_racer.MiniRacer()
    js.eval(js_content)
    return js.call("v")

class ConceptRankRunner:
    def __init__(self):
        self.ck = ClickHouseClient()
        self.user_cookie = self._load_user_cookie()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
            "Referer": "http://q.10jqka.com.cn/gn/"
        }

    def _load_user_cookie(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ths_cookie.txt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except:
                pass
        return None

    def get_concept_list(self):
        """Load all concepts from DB"""
        try:
            df = self.ck.query_df("SELECT code, name FROM finance_concept_main")
            if not df.empty:
                return df[['code', 'name']].to_dict('records')
        except Exception as e:
            print(f"Error loading concepts: {e}")
        return []

    def fetch_single_concept(self, item):
        """
        Fetches details for a single concept page.
        Returns a dict matching concept_snapshot_intraday schema.
        """
        code = item['code']
        # name = item['name']
        
        # Prepare Cookie
        v_code = get_v_code()
        current_headers = self.headers.copy()
        
        if self.user_cookie:
            # Simple merge logic
            if "v=" in self.user_cookie:
                parts = [p.strip() for p in self.user_cookie.split(';') if p.strip()]
                new_parts = [p for p in parts if not p.startswith('v=')]
                new_parts.append(f"v={v_code}")
                current_headers["Cookie"] = '; '.join(new_parts)
            else:
                current_headers["Cookie"] = f"{self.user_cookie}; v={v_code}"
        else:
            current_headers["Cookie"] = f"v={v_code}"
            
        url = f"http://q.10jqka.com.cn/gn/detail/code/{code}/"
        
        try:
            r = requests.get(url, headers=current_headers, timeout=10)
            if r.status_code != 200:
                print(f"Failed {code}: {r.status_code}")
                return None
            
            soup = BeautifulSoup(r.text, "lxml")
            
            # Base data structure
            now = datetime.now()
            data = {
                "concept_code": code,
                "date": now.date(),
                "snapshot_time": now,
                
                "price_index": 0.0,
                "pct_chg": 0.0,
                "change": 0.0,
                "volume": 0.0,
                "amount": 0.0,
                "turnover_rate": 0.0,
                "net_inflow": 0.0,
                "rise_count": 0,
                "fall_count": 0,
                "open": 0.0,
                "high": 0.0,
                "low": 0.0,
                "last_close": 0.0
            }
            
            # 1. Parse Header (board-hq)
            hq_div = soup.find("div", class_="board-hq")
            if hq_div:
                # current index
                price_span = hq_div.find("span", class_="board-xj")
                if price_span:
                    try: data["price_index"] = float(price_span.get_text(strip=True))
                    except: pass
                
                # change & pct_chg
                zdf_p = hq_div.find("p", class_="board-zdf")
                if zdf_p:
                    text = zdf_p.get_text(strip=True)
                    # format: "+12.34 +1.23%" or "12.34 1.23%"
                    parts = text.split()
                    if len(parts) >= 2:
                        try:
                            data["change"] = float(parts[0])
                            data["pct_chg"] = float(parts[1].strip('%'))
                        except: pass
            
            # 2. Parse Infos (board-infos)
            infos_div = soup.find("div", class_="board-infos")
            if infos_div:
                dts = infos_div.find_all("dt")
                dds = infos_div.find_all("dd")
                info_map = {}
                for dt, dd in zip(dts, dds):
                    label = dt.get_text(strip=True)
                    
                    if "涨跌家数" in label:
                        rise = dd.find("span", class_="arr-rise-s")
                        fall = dd.find("span", class_="arr-fall-s")
                        try: data["rise_count"] = int(rise.get_text(strip=True)) if rise else 0
                        except: pass
                        try: data["fall_count"] = int(fall.get_text(strip=True)) if fall else 0
                        except: pass
                    else:
                        info_map[label] = dd.get_text(strip=True)
                
                # Helper to parse values like "12.3亿", "3.4万手", "5.6%"
                def parse_mixed_val(key):
                    val = info_map.get(key, "0")
                    if not val or val == '--': return 0.0
                    
                    unit_mult = 1.0
                    if '万' in val: unit_mult = 1.0 # Keep as unit 万 if schema expects 万?
                    # Schema says: volume (万手), amount (亿元).
                    # fetch_concept_board_info logic implies raw float parse after stripping text.
                    
                    # Clean chars
                    val_clean = val.replace(',', '').replace('%', '').replace('万手', '').replace('亿元', '').replace('亿', '')
                    try:
                        return float(val_clean)
                    except:
                        return 0.0
                        
                data["open"] = parse_mixed_val("今开")
                data["high"] = parse_mixed_val("最高")
                data["low"] = parse_mixed_val("最低")
                data["last_close"] = parse_mixed_val("昨收")
                data["volume"] = parse_mixed_val("成交量(万手)")
                data["amount"] = parse_mixed_val("成交额(亿元)")
                data["turnover_rate"] = parse_mixed_val("换手率")
                data["net_inflow"] = parse_mixed_val("净流入(亿)")

            return data
            
        except Exception as e:
            # print(f"Error fetching {code}: {e}")
            return None

    def fetch_realtime_ranks(self):
        """
        Traverse all concepts to get full snapshot.
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting full concept traversal...")
        
        concepts = self.get_concept_list()
        if not concepts:
            print("No concepts found in DB. Please run Fetcher first.")
            return

        results = []
        # Use limited concurrency. 5 threads * 0.1s delay implies ~20-50 req/s max, likely lower due to net.
        # 400 concepts will take about 1-2 minutes.
        max_workers = 5
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(self.fetch_single_concept, c): c for c in concepts}
            
            completed = 0
            total = len(concepts)
            
            for future in as_completed(future_to_code):
                data = future.result()
                if data:
                    results.append(data)
                
                completed += 1
                if completed % 50 == 0:
                    print(f"  Progress: {completed}/{total}")

        if results:
            df_res = pd.DataFrame(results)
            try:
                self.ck.insert_df("concept_snapshot_intraday", df_res)
                print(f"TRAVERSAL DONE. Updated {len(df_res)} records.")
            except Exception as e:
                print(f"DB Insert Error: {e}")
        else:
            print("TRAVERSAL FAILED. No data fetched.")

    def run(self):
        print(f"Concept Rank Runner V2 (Traversal) Started (Freq: {INTERVAL_SECONDS}s)...")
        while True:
            now_time = datetime.now()
            # Trading Hours check (9:00 - 15:30)
            if not (9 <= now_time.hour <= 15): 
                time.sleep(60); continue
            
            if (now_time.hour == 11 and now_time.minute > 35) or (now_time.hour == 12 and now_time.minute < 55):
                time.sleep(60); continue

            self.fetch_realtime_ranks()
            time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    # Test run
    runner = ConceptRankRunner()
    # runner.fetch_realtime_ranks() # Uncomment to test once
    pass
