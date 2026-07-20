import requests

def debug_tencent_all_fields(code):
    url = f"http://qt.gtimg.cn/q={code}"
    r = requests.get(url)
    if r.status_code == 200:
        content = r.text.split('=')[1].strip('"').split('~')
        print(f"--- Fields for {code} (Total: {len(content)}) ---")
        for i, val in enumerate(content):
            print(f"[{i}]: {val}")

if __name__ == "__main__":
    # 找几只股票看看，包括可能停牌的（虽然今天很难说谁停牌）
    # 我们看 000001 (常态), 以及尝试找一个可能停牌的
    debug_tencent_all_fields("sz000001")
