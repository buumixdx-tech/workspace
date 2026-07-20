import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup
import py_mini_racer
from akshare.stock_feature.stock_board_concept_ths import _get_file_content_ths
import os
import time
import re

def get_v_code():
    """Generates the 'v' cookie required by THS."""
    js_content = _get_file_content_ths("ths.js")
    js = py_mini_racer.MiniRacer()
    js.eval(js_content)
    return js.call("v")

def fetch_board_info(concept_code, concept_name):
    """
    Fetches detailed board info for a given THS concept code.
    Returns a dictionary of data.
    """
    # Load User Cookie
    user_cookie = None
    cookie_path = os.path.join("docs", "ths_cookie.txt")
    if os.path.exists(cookie_path):
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    user_cookie = content
        except Exception as e:
            print(f"Error reading cookie file: {e}")

    # Generate v_code
    v_code = get_v_code()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Referer": "http://q.10jqka.com.cn/gn/"
    }

    # Construct Cookie
    if user_cookie:
        if "v=" in user_cookie:
            parts = [p.strip() for p in user_cookie.split(';') if p.strip()]
            new_parts = []
            for p in parts:
                if p.startswith('v='):
                   new_parts.append(f"v={v_code}")
                else:
                   new_parts.append(p)
            if not any(p.startswith('v=') for p in new_parts):
                 new_parts.append(f"v={v_code}")
            headers["Cookie"] = '; '.join(new_parts)
        else:
             headers["Cookie"] = f"{user_cookie}; v={v_code}"
    else:
        headers["Cookie"] = f"v={v_code}"

    url = f"http://q.10jqka.com.cn/gn/detail/code/{concept_code}/"
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"  - Request failed with status {r.status_code}")
            return None
        
        soup = BeautifulSoup(r.text, "lxml")
        data = {"概念名称": concept_name, "概念代码": concept_code}
        
        # 1. Parse Header (board-hq)
        hq_div = soup.find("div", class_="board-hq")
        if hq_div:
            # Index Code
            h3 = hq_div.find("h3")
            if h3:
                span = h3.find("span")
                if span:
                    data["指数代码"] = span.get_text(strip=True)
            
            # Price
            price_span = hq_div.find("span", class_="board-xj")
            if price_span:
                data["当前指数"] = price_span.get_text(strip=True)
            
            # Change
            zdf_p = hq_div.find("p", class_="board-zdf")
            if zdf_p:
                text = zdf_p.get_text(strip=True)
                # Split roughly by whitespace, or regex
                parts = text.split()
                if len(parts) >= 2:
                    data["涨跌额"] = parts[0]
                    data["涨跌幅"] = parts[1]
                else:
                    data["涨跌额"] = text
        else:
            print("  - Warning: 'board-hq' div not found.")

        # 2. Parse Details (board-infos)
        infos_div = soup.find("div", class_="board-infos")
        if infos_div:
            dts = infos_div.find_all("dt")
            dds = infos_div.find_all("dd")
            for dt, dd in zip(dts, dds):
                label = dt.get_text(strip=True)
                
                # Special handling for "涨跌家数"
                if "涨跌家数" in label:
                    rise = dd.find("span", class_="arr-rise-s")
                    fall = dd.find("span", class_="arr-fall-s")
                    rise_count = rise.get_text(strip=True) if rise else "0"
                    fall_count = fall.get_text(strip=True) if fall else "0"
                    data["上涨家数"] = rise_count
                    data["下跌家数"] = fall_count
                else:
                    value = dd.get_text(strip=True)
                    data[label] = value
        else:
             print("  - Warning: 'board-infos' div not found.")
             # print(r.text[:500]) # Debug
             
        return data

    except Exception as e:
        print(f"  - Error fetching info: {e}")
        return None

def main():
    try:
        today = time.strftime("%Y%m%d")
        save_dir = os.path.join("data", "akshare_data")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        print("正在获取所有概念板块名称...")
        concepts_df = ak.stock_board_concept_name_ths()
        
        if concepts_df.empty:
            print("未获取到概念板块列表。")
            return
            
        total = len(concepts_df)
        print(f"共发现 {total} 个概念板块。开始采集详细行情...")
        
        all_data = []
        
        for i, row in concepts_df.iterrows():
            name = row['name']
            code = row['code']
            
            print(f"[{i+1}/{total}] 正在采集: {name} ({code})")
            
            info = fetch_board_info(code, name)
            if info:
                all_data.append(info)
            else:
                print(f"  - 采集失败: {name}")

            # Save incrementally
            if (i + 1) % 10 == 0:
                print("  --- 保存临时数据 ---")
                pd.DataFrame(all_data).to_csv(os.path.join(save_dir, f"concept_board_info_{today}_temp.csv"), index=False, encoding='utf-8-sig')
            
            time.sleep(1) # Polite delay
            
        # Final Save
        if all_data:
            df = pd.DataFrame(all_data)
            output_path = os.path.join(save_dir, f"concept_board_info_{today}.csv")
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"\n采集完成！共 {len(df)} 条记录。")
            print(f"文件保存至: {output_path}")
            
            # Clean temp
            temp_path = os.path.join(save_dir, f"concept_board_info_{today}_temp.csv")
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            print("未采集到有效数据。")

    except Exception as e:
        print(f"程序运行出错: {e}")

if __name__ == "__main__":
    main()
