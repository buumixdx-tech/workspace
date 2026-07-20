import requests
from bs4 import BeautifulSoup
import re
import sys
import os
import traceback

# Add path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import fetch logic
from market.fetch_concept_board_info import fetch_board_info

def get_concept_list_manual():
    """Manually scrape THS concept list page since AKShare is failing."""
    url = "http://q.10jqka.com.cn/gn/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"
    }
    
    print(f"Fetching concept list from {url}...")
    concepts = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"Failed to fetch list: {r.status_code}")
            return []
            
        soup = BeautifulSoup(r.text, "lxml")
        links = soup.find_all('a', href=re.compile(r'/gn/detail/code/\d+/'))
        
        seen_codes = set()
        for link in links:
            href = link.get('href')
            name = link.get_text(strip=True)
            match = re.search(r'/code/(\d+)/', href)
            if match and name:
                code = match.group(1)
                if code not in seen_codes:
                    seen_codes.add(code)
                    concepts.append({'code': code, 'name': name})
                    
        print(f"✅ Found {len(concepts)} concepts manually.")
        return concepts
        
    except Exception as e:
        print(f"List fetch error: {e}")
        return []

def test_full_link():
    # 1. Get List
    concepts = get_concept_list_manual()
    if not concepts:
        print("Cannot proceed without concept list.")
        return

    # 2. Test Fetching First Item
    first = concepts[0]
    print(f"\nTesting detail fetch for: {first['name']} ({first['code']})...")
    
    try:
        data = fetch_board_info(first['code'], first['name'])
        
        if data:
            print("\n✅ SUCCESS! Data retrieved:")
            for k, v in data.items():
                print(f"  - {k}: {v}")
        else:
            print("\n❌ Failed to fetch detail data.")
            
    except Exception as e:
        print(f"Detail fetch error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_full_link()
