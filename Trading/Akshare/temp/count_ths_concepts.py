import requests
from bs4 import BeautifulSoup
import re

def count_ths_concepts():
    url = "http://q.10jqka.com.cn/gn/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"
    }
    
    print(f"Fetching {url}...")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"Failed: {r.status_code}")
            return
            
        soup = BeautifulSoup(r.text, "lxml")
        
        # Find links matching pattern /gn/detail/code/(\d+)/
        links = soup.find_all('a', href=re.compile(r'/gn/detail/code/\d+/'))
        
        unique_concepts = set()
        concept_map = {}
        
        for link in links:
            href = link.get('href')
            name = link.get_text(strip=True)
            
            # Extract code
            match = re.search(r'/code/(\d+)/', href)
            if match:
                code = match.group(1)
                unique_concepts.add(code)
                # Store mapping if name exists and not empty
                if name:
                    concept_map[name] = code
        
        print(f"\n✅ Total unique concept links found: {len(unique_concepts)}")
        print("First 10 examples:")
        for name, code in list(concept_map.items())[:10]:
            print(f"  {name}: {code}")
            
        # Optional: Check coverage against akshare data?
        # That would require akshare call. For now just count page links.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    count_ths_concepts()
