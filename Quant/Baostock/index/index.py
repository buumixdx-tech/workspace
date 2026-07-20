import baostock as bs
import pandas as pd

def get_index_data():
    # 登录系统
    lg = bs.login()
    print('login respond error_code:' + lg.error_code)
    print('login respond  error_msg:' + lg.error_msg)

    # 定义指数代码和日期范围
    index_code = "sz.399001"
    start_date = "2025-08-01"
    end_date = "2025-08-08"

    # 获取指数日K线数据
    rs = bs.query_history_k_data_plus(
        index_code,
        "code,date,open,high,low,close,preclose,volume,amount,turn,tradestatus,adjustflag",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3"
    )
    
    print('query_history_k_data_plus respond error_code:' + rs.error_code)
    print('query_history_k_data_plus respond  error_msg:' + rs.error_msg)

    # 将数据保存到csv文件
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    # 转换为DataFrame
    result = pd.DataFrame(data_list, columns=rs.fields)
    
    # 保存到csv文件
    result.to_csv('index.csv', index=False, encoding='utf-8')
    
    print("数据已保存到index.csv文件中")
    
    # 登出系统
    bs.logout()

if __name__ == '__main__':
    get_index_data()