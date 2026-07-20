import baostock as bs
import pandas as pd
from datetime import datetime

def test_baostock_holiday_query(stock_code, test_date):
    """
    测试在指定日期（如节假日或非交易日）查询股票数据的行为
    
    :param stock_code: 股票代码，例如 "sh.600000"
    :param test_date: 测试日期，格式 "YYYY-MM-DD"
    """
    print(f"开始测试：股票 {stock_code} 在日期 {test_date} 的查询行为")
    print("-" * 60)

    # 登陆系统
    lg = bs.login()
    print('登录响应 error_code: ' + lg.error_code)
    print('登录响应 error_msg: ' + lg.error_msg)

    if lg.error_code != '0':
        print("登录失败，无法进行测试。")
        return

    # 设置查询的起止日期为同一天（测试日期）
    start_date = test_date
    end_date = test_date

    # 查询日K线数据
    rs = bs.query_history_k_data_plus(
        stock_code,
        "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3"
    )

    print('query_history_k_data_plus 响应 error_code: ' + rs.error_code)
    print('query_history_k_data_plus 响应 error_msg: ' + rs.error_msg)

    # 检查是否有数据返回
    data_list = []
    while (rs.error_code == '0') and rs.next():
        data_list.append(rs.get_row_data())

    if data_list:
        result = pd.DataFrame(data_list, columns=rs.fields)
        print(f"返回了 {len(result)} 条数据记录：")
        print(result)
    else:
        print("在指定日期范围内没有返回任何数据记录。")
        # 特别说明：如果 error_code 为 '0' 但无数据，通常意味着该日期无交易（如周末、节假日）
        if rs.error_code == '0':
            print("注意：Baostock 返回成功 (error_code=0)，但无数据，可能是因为该日期是非交易日。")
        else:
            print("查询失败，具体错误见 error_msg。")

    # 登出系统
    bs.logout()
    print("测试完成。")
    print("=" * 60)


# ------------------ 主程序 ------------------
if __name__ == "__main__":
    # 定义测试参数
    stock_code = "sh.600000"  # 浦发银行
    test_date = "2025-08-09"  # 2025年8月9日，周六，非交易日

    # 执行测试
    test_baostock_holiday_query(stock_code, test_date)

    # 可选：再测试一个交易日作为对比
    # test_baostock_holiday_query(stock_code, "2025-08-08")  # 假设 8月8日是周五，交易日