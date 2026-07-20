import requests
import pandas as pd
from datetime import datetime

def test_tencent_full_fields():
    # 测试几个有代表性的标的：平安银行 (sz000001), 贵州茅台 (sh600519), 工业富联 (sh601138)
    codes = ["sz000001", "sh600519", "sh601138"]
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    
    print(f"Requesting: {url}")
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            print(f"Error: Status code {r.status_code}")
            return
            
        text = r.text.strip()
        lines = text.split(';')
        
        results = []
        for line in lines:
            if '=' not in line: continue
            
            parts = line.split('=')
            content = parts[1].strip('"')
            v = content.split('~')
            
            if len(v) < 48: 
                print(f"Warning: Unexpected fields count {len(v)} for {v[1] if len(v)>1 else 'unknown'}")
                continue
            
            # 腾讯接口字段解析
            price = float(v[3]) if v[3] else 0
            total_market_cap_100m = float(v[45]) if v[45] else 0
            float_market_cap_100m = float(v[44]) if v[44] else 0
            
            # 换算股数 (亿 -> 万股 或 股)
            # 计算得到的总股本 (单位：亿股)
            calc_total_shares = (total_market_cap_100m / price) if price > 0 else 0
            # 计算得到的流通股本 (单位：亿股)
            calc_float_shares = (float_market_cap_100m / price) if price > 0 else 0
            
            info = {
                "代码": v[2],
                "名称": v[1],
                "现价": v[3],
                "总市值(亿)": v[45],
                "流通市值(亿)": v[44],
                "推算总股本(亿)": round(calc_total_shares, 4),
                "推算流通股(亿)": round(calc_float_shares, 4),
                "PE": v[39],
                "换手": v[38]
            }
            results.append(info)

            
        df = pd.DataFrame(results)
        print("\n--- 腾讯接口提取结果 ---")
        print(df.to_string(index=False))
        
        # 验证是否为有效数字
        for field in ["市盈率(PE)", "市净率(PB)", "换手率(%)", "振幅(%)", "总市值(亿)", "流通市值(亿)"]:
            try:
                val = float(df.iloc[0][field])
                print(f"✅ 字段 [{field}] 解析成功: {val}")
            except:
                print(f"❌ 字段 [{field}] 不是有效数字: {df.iloc[0][field]}")

    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_tencent_full_fields()
