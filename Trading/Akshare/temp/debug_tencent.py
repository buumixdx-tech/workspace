import requests

def debug_tencent_response():
    # 找几个典型股票：浦发银行(sh600000), 贵州茅台(sh600519), 以及你刚才看到异常的 sz301609 (山大电力)
    codes = "sh600000,sh600519,sz301609"
    url = f"http://qt.gtimg.cn/q={codes}"
    
    print(f"Fetching: {url}")
    try:
        r = requests.get(url, timeout=5)
        text = r.text
        lines = text.strip().split(';')
        
        for line in lines:
            if '=' not in line: continue
            parts = line.split('=')
            header = parts[0].strip()
            content = parts[1].strip('"')
            v = content.split('~')
            
            print(f"\n--- {header} ---")
            for i, val in enumerate(v):
                print(f"[{i}] {val}")
                
    except Exception as e:
        print(e)

if __name__ == "__main__":
    debug_tencent_response()
