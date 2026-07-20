import sys
import os
import json
import base64
import zlib
import struct

# Add parent dir to path to import notification module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notification.compressor_utils import MarketDataPackerV6

def test_packing():
    print("Testing Packer V6...")
    
    # Mock Data
    mock_data = {
        'top_concepts': [
            {'concept_name': '半导体', 'avg_pct_chg': 2.5, 'limit_up_count': 5, 'limit_down_count': 0, 'up_count': 45, 'down_count': 10, 'avg_turnover': 1.2},
            {'concept_name': '酿酒', 'avg_pct_chg': -1.2, 'limit_up_count': 0, 'limit_down_count': 2, 'up_count': 10, 'down_count': 40, 'avg_turnover': 0.8},
        ],
        'boom_concepts': [],
        'lottery_pool': [
            {'code': '600519', 'name': '贵州茅台', 'source_concept': '酿酒', 'reason_bits': 1},
            {'code': '000001', 'name': '平安银行', 'source_concept': '银行', 'reason_bits': 2}
        ],
        'small_cap_pool': [
            {'code': '300059', 'name': '东方财富', 'matched_concept': '半导体', 'reason_bits': 4, '_is_small_cap': True}
        ]
    }

    # Initialize Packer
    packer = MarketDataPackerV6("temp/test_concept_dict.json")
    
    try:
        # Pack
        b64_str = packer.pack(mock_data)
        print(f"✅ Pack Success!")
        print(f"Original Size: {packer.stats['original_bytes']} bytes")
        print(f"Compressed Size: {packer.stats['compressed_bytes']} bytes")
        print(f"Ratio: {packer.stats['compressed_bytes'] / packer.stats['original_bytes']:.2%}")
        print(f"Output String ({len(b64_str)} chars):")
        print(b64_str)
        
        # Verify Integrity (Python side decode check)
        compressed = base64.b64decode(b64_str)
        decompressed = zlib.decompress(compressed)
        print(f"✅ Integrity Check Passed (Decompressed to {len(decompressed)} bytes)")
        
        # Basic Header Check
        ts, c_cnt, s_cnt = struct.unpack('<IBB', decompressed[:6])
        print(f"Header => Timestamp: {ts}, Concepts: {c_cnt}, Stocks: {s_cnt}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_packing()
