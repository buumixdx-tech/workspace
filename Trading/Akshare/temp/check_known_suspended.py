import requests

def check_known_suspended():
    # 东旭光电 (000413) 目前是停牌状态 (待核实，深交所很多ST或异常品种停牌)
    # 尝试几只可能停牌的
    codes = ["sz000413", "sz002621", "sh600145", "sh600610"]
    for code in codes:
        url = f"http://qt.gtimg.cn/q={code}"
        r = requests.get(url)
        if r.status_code == 200 and 'v_' in r.text:
            v = r.text.split('=')[1].strip('"').split('~')
            print(f"\nCode: {code} ({v[1]})")
            print(f"v[0] (Status Identifier): {v[0]}")
            print(f"v[3] (Current Price): {v[3]}")
            print(f"v[5] (Open Price): {v[5]}")
            print(f"v[6] (Volume): {v[6]}")
        else:
            print(f"Code {code} not found or empty response")

if __name__ == "__main__":
    check_known_suspended()
