import akshare as ak
import requests

def find_suspended_and_check_tencent():
    print("Fetching spot data from EM to find suspended stocks...")
    try:
        df = ak.stock_zh_a_spot_em()
        # 东方财富接口中，停牌的股票最新价通常是空或者标记为停牌
        # 我们寻找成交量为 0 且 状态包含 '停' 的
        suspended = df[df['成交量'] == 0].head(5)
        if suspended.empty:
            # 如果没找到，尝试找最新价为空的
            suspended = df[df['最新价'].isna()].head(5)
            
        if not suspended.empty:
            for _, row in suspended.iterrows():
                code = row['代码']
                name = row['名称']
                # 转换代码格式为腾讯格式: sh600000 / sz000001
                full_code = ("sh" + code) if code.startswith('6') or code.startswith('688') or code.startswith('9') else ("sz" + code)
                
                print(f"\nChecking suspended stock: {code} ({name}) -> Tencent: {full_code}")
                url = f"http://qt.gtimg.cn/q={full_code}"
                r = requests.get(url)
                if r.status_code == 200:
                    v = r.text.split('=')[1].strip('"').split('~')
                    print(f"v[0] (Status?): {v[0]}")
                    print(f"v[3] (Price): {v[3]}")
                    print(f"v[5] (Open): {v[5]}")
                    print(f"v[6] (Volume): {v[6]}")
                    print(f"Fields count: {len(v)}")
        else:
            print("No suspended stocks found in EM spot data.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_suspended_and_check_tencent()
