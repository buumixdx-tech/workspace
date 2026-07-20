
import struct
import base64
import zlib
import json
from typing import List, Dict, Any
from datetime import datetime
import os

class MarketDataPackerV6:
    """
    极致压缩方案 V6：无股票字典，原始 6 位代码传输。
    1. 股票代码: 3 字节 (Uint24) - 直接存 600000 这种数字
    2. 板块: 2 字节 ID (保留板块字典)
    3. 标志位: 1 字节位掩码
    
    Layout:
    [Magic:2] 'M6'
    [Timestamp:4] Scheme B
    [SecA_Count:2] Top Concepts
    [SecA_Data...]
    [SecB_Count:2] Boom Concepts
    [SecB_Data...]
    [SecC_Count:2] Lottery Stocks
    [SecC_Data...]
    [SecD_Count:2] SmallCap Stocks
    [SecD_Data...]
    """
    
    MAGIC = b'M6'

    def __init__(self, concept_dict_path: str = None):
        self.concept_name_to_id = {}
        if concept_dict_path and os.path.exists(concept_dict_path):
            with open(concept_dict_path, 'r', encoding='utf-8') as f:
                self.concept_name_to_id = json.load(f)
        self.stats = {'original_bytes': 0, 'compressed_bytes': 0}

    @staticmethod
    def encode_stock_code_raw(code: str) -> bytes:
        """
        将 'sh.600000' 提取出 600000 并转为 3 字节
        """
        try:
            digits = "".join(filter(str.isdigit, code))
            num = int(digits)
            # 3 bytes can store up to 16,777,215. Stock codes are < 999999. Safe.
            # Use 'I' (4 bytes) and take last 3. Big Endian.
            return struct.pack('>I', num)[1:] 
        except:
            return b'\x00\x00\x00'

    def pack(self, data: Dict[str, Any]) -> str:
        buf = bytearray()
        buf.extend(self.MAGIC)
        
        # 1. 结构化时间戳 (4B, 32位)
        # 方案 B: [DateOffset:15bit | SecondOfDay:17bit]
        ts_base = datetime(2026, 1, 1)
        ts_now = data.get('timestamp', datetime.now())
        if isinstance(ts_now, str):
            try:
                ts_now = datetime.strptime(ts_now, '%Y-%m-%d %H:%M:%S')
            except:
                ts_now = datetime.now()
        
        if isinstance(ts_now, datetime):
            delta = ts_now - ts_base
            days_offset = delta.days & 0x7FFF
            seconds_of_day = (ts_now.hour * 3600 + ts_now.minute * 60 + ts_now.second) & 0x1FFFF
            ts_val = (days_offset << 17) | seconds_of_day
        else:
            ts_val = 0
            
        buf.extend(struct.pack('>I', ts_val))

        # 2. Section A: 核心异动板块 (Primary Sectors - Merged P1/P2/P3)
        # Merge all pools and deduplicate by concept name, prioritizing higher pool level
        pool_1 = data.get('pool_1', [])
        pool_2 = data.get('pool_2', [])
        pool_3 = data.get('pool_3', [])
        
        # Key=Name, Value={'data': c_obj, 'level': int}
        merged_map = {}
        
        # Helper to merge
        def merge_pool(pool, level):
            for p in pool:
                name = p.get('concept_name')
                if not name: continue
                # Update if new or higher level
                if name not in merged_map:
                    merged_map[name] = {'data': p, 'level': level}
                else:
                    if level > merged_map[name]['level']:
                         merged_map[name]['level'] = level
                         
        merge_pool(pool_1, 1)
        merge_pool(pool_2, 2)
        merge_pool(pool_3, 3)
                
        primary_items = list(merged_map.values())
        
        buf.extend(struct.pack('>H', len(primary_items)))
        for item in primary_items:
            # Pass level to packer
            self._pack_concept(buf, item['data'], level=item['level'])

        # 3. Section B: 预留 (Secondary Sectors - Empty)
        buf.extend(struct.pack('>H', 0))

        # 4. Section C: 冲板股票 (Lottery Pool)
        lottery = data.get('lottery_pool', [])
        buf.extend(struct.pack('>H', len(lottery)))
        
        # 记录冲板池的代码以便后续去重
        lottery_codes = set()
        for s in lottery:
            lottery_codes.add(s['code'])
            # Flag Logic for Lottery
            flag = 0 
            flag |= (1 << 7) # Surging bit
            
            rb = int(s.get('reason_bits', 0) or 0)
            flag |= (rb & 0x3F) # Low 6 bits
            
            self._pack_stock(buf, s, flag)

        # 5. Section D: 小票池股票 (Small Cap Pool)
        small_caps = data.get('small_cap_pool', [])
        
        # 筛选：仅保留不在冲板池中的小票 (物理去重)
        unique_small_caps = [s for s in small_caps if s['code'] not in lottery_codes]
        
        buf.extend(struct.pack('>H', len(unique_small_caps)))
        for s in unique_small_caps:
            flag = 0
            flag |= (1 << 6) # Small Cap bit
            
            if s.get('_is_surging'):
                flag |= (1 << 7)
            
            rb = int(s.get('reason_bits', 0) or 0)
            flag |= (rb & 0x3F)
            
            self._pack_stock(buf, s, flag)

        # Compress
        compressed_data = zlib.compress(buf, level=9)
        
        self.stats['original_bytes'] = len(buf)
        self.stats['compressed_bytes'] = len(compressed_data)
        
        return base64.urlsafe_b64encode(compressed_data).decode('ascii')

    def _pack_concept(self, buf, c, level=0):
        c_id = self.concept_name_to_id.get(c['concept_name'], 0) # 0 if not found
        
        pct = int(float(c.get('pct_chg', 0)) * 100)
        lu = int(c.get('limit_up_count', 0))
        ld = int(c.get('limit_down_count', 0))
        
        # Mapping Schema V6 fields
        # ID(2) Avg(2) LU(1) LD(1) Up(2) Down(2) TO(2) Level(1)
        up = int(c.get('stock_count', 0)) 
        
        rise = int(c.get('rise_count', 0))
        fall = int(c.get('fall_count', 0))
        to = int(float(c.get('turnover_rate', 0)) * 100)
        
        buf.extend(struct.pack('>HhBBHHHB', 
            c_id,
            pct,
            lu,
            ld,
            rise,
            fall,
            to,
            int(level) # Pool Level 1/2/3
        ))

    def _pack_stock(self, buf, s, flag):
        # A. 股票代码 (3字节 Uint24)
        buf.extend(self.encode_stock_code_raw(s['code']))
        
        # B. Flag 字节 (1B)
        buf.append(flag)
        
        # C. 归属板块 
        s_con_names = []
        if s.get('source_concept'):
            s_con_names.extend(s['source_concept'].strip().split(','))
        if s.get('matched_concept'): 
            s_con_names.extend(s['matched_concept'].strip().split(','))
        
        ids = []
        for n in s_con_names:
            n = n.strip()
            if n in self.concept_name_to_id:
                ids.append(self.concept_name_to_id[n])
        
        ids = list(set(ids)) # Dedup
        
        # JS expects: Count(1B) + IDs(2B each)
        count = min(len(ids), 255)
        buf.append(count) 
        for i in ids[:count]:
            buf.extend(struct.pack('>H', i))
