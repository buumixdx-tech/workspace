import requests
from datetime import datetime
from typing import List, Dict, Any
from .base import BaseSnapshotProvider

class TencentSnapshotProvider(BaseSnapshotProvider):
    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    @property
    def batch_size(self) -> int:
        return 80  # 腾讯接口对长 URL 支持较好，80 是经验值

    def format_code(self, ck_code: str) -> str:
        # sh.600000 -> sh600000
        return ck_code.replace('.', '')

    def get_batch(self, provider_codes: List[str]) -> str:
        url = f"http://qt.gtimg.cn/q={','.join(provider_codes)}"
        try:
            r = requests.get(url, timeout=self.timeout)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            # 实际生产中可以打 error log，这里暂时静默或 print
            print(f"[Tencent] Request failed: {e}")
        return ""

    def parse(self, text: str, snapshot_time: datetime) -> List[Dict]:
        data = []
        if not text:
            return data
            
        lines = text.strip().split(';')
        for line in lines:
            if '=' not in line: continue
            try:
                parts = line.split('=')
                # 提取 market (from v_sh600000)
                header = parts[0].strip()
                market = header.split('_')[-1][:2] if '_' in header else ""
                
                content = parts[1].strip('"')
                v = content.split('~')
                if len(v) < 30: continue # 腾讯数据通常很长，至少得有30个字段
                
                # 还原 CK 格式: sh.600000
                raw_code = v[2]
                full_code = f"{market}.{raw_code}" if market else raw_code
                
                # 数值解析的安全包装
                try:
                    price = float(v[3])
                    last_close = float(v[4])
                    open_px = float(v[5])
                    volume = int(float(v[6]) * 100) # 手 -> 股
                    
                    # 涨跌
                    change = float(v[31])
                    pct_chg = float(v[32])
                    
                    high = float(v[33])
                    low = float(v[34])
                    
                    amount = float(v[37]) * 10000.0 # 万 -> 元
                    
                    # 新增字段提取 (腾讯接口单位换算)
                    turnover_rate = float(v[38]) if v[38] else 0.0
                    total_market_cap = float(v[45]) * 100000000.0 if v[45] else 0.0 # 亿 -> 元
                    float_market_cap = float(v[44]) * 100000000.0 if v[44] else 0.0 # 亿 -> 元

                    # 停牌判定：开盘价为0 且 成交量为0 (通常在9:25之后判定最准确)
                    # 为了库的鲁棒性，只要满足这两个特征即标记为停牌
                    is_suspended = 1 if (open_px == 0 and volume == 0) else 0

                    # 提取 source_time (v[30]: 20260126130000)
                    # 注意：这是腾讯服务器刷新时间，非撮合时间，但优于 local_time
                    source_time_str = v[30]
                    if len(source_time_str) >= 14:
                        source_time = datetime.strptime(source_time_str[:14], "%Y%m%d%H%M%S")
                    else:
                        source_time = snapshot_time # 降级
                        
                except (ValueError, IndexError):
                    continue

                data.append({
                    'code': full_code,
                    'name': v[1],
                    'snapshot_time': snapshot_time,
                    'source_time': source_time,
                    'price': price,
                    'open': open_px,
                    'high': high,
                    'low': low,
                    'last_close': last_close,
                    'change': change,
                    'pct_chg': pct_chg,
                    'volume': volume,
                    'amount': amount,
                    'turnover_rate': turnover_rate,
                    'total_market_cap': total_market_cap,
                    'float_market_cap': float_market_cap,
                    'is_suspended': is_suspended
                })
            except Exception:
                continue
        return data
