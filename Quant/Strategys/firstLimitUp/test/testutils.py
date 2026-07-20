# test/test_trading_calendar.py
import sys
import os

# 获取项目根目录路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from modules.db import ClickHouseDB
from modules.utils import fetch_trading_calendar

def test_fetch_trading_calendar():
    print("开始测试 fetch_trading_calendar 函数...")
    
    try:
        db = ClickHouseDB()
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 无法连接数据库: {e}")
        return

    # 测试场景
    test_scenarios = [
        ("获取所有交易日", None, None),
        ("指定开始日期", "20250801", None),
        ("指定结束日期", None, "20250815"),
        ("指定日期范围", "20250801", "20250815"),
        ("错误开始日期格式", "2025-08-01", "20250815"),
        ("错误结束日期格式", "20250801", "2025-08-15"),
    ]

    for name, start_date, end_date in test_scenarios:
        print(f"\n--- {name} ---")
        print(f"输入: start_date={start_date}, end_date={end_date}")
        
        try:
            result = fetch_trading_calendar(db, start_date, end_date)
            print(f"返回结果数量: {len(result)}")
            
            if result:
                print(f"前3个日期: {result[:3]}")
                print(f"后3个日期: {result[-3:]}")
                
                # 验证格式
                if len(result) > 0:
                    first_date = result[0]
                    if len(first_date) == 8 and first_date.isdigit():
                        print("✅ 日期格式正确 (YYYYMMDD)")
                    else:
                        print("❌ 日期格式错误")
            else:
                print("⚠️  返回空列表")
                
        except Exception as e:
            print(f"❌ 执行失败: {e}")

    try:
        db.close()
        print("\n数据库连接已关闭")
    except Exception as e:
        print(f"关闭连接时出错: {e}")

def test_edge_cases():
    print("\n" + "="*50)
    print("测试边界情况...")
    
    try:
        db = ClickHouseDB()
        
        # 测试空结果情况
        print("\n--- 测试未来日期范围 ---")
        future_result = fetch_trading_calendar(db, "20300101", "20301231")
        print(f"未来日期范围结果: {len(future_result)} 条记录")
        
        # 测试过去的日期范围
        print("\n--- 测试过去日期范围 ---")
        past_result = fetch_trading_calendar(db, "20200101", "20200131")
        print(f"过去日期范围结果: {len(past_result)} 条记录")
        if past_result:
            print(f"示例日期: {past_result[:3]}")
            
    except Exception as e:
        print(f"边界测试失败: {e}")
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == '__main__':
    test_fetch_trading_calendar()
    test_edge_cases()
    print("\n✅ 测试完成")