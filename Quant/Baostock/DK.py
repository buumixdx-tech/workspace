import baostock as bs
import pandas as pd
import os
from datetime import datetime

# 通过读取config.txt文件中的配置参数获取需要读取的股票代码和起止日期

def get_stock_data():
    # 读取配置文件
    config = {}
    with open('config.txt', 'r') as f:
        for line in f:
            if ':' in line:
                key, value = line.strip().split(':', 1)
                config[key] = value
    
    stock_code = config.get('ID', 'sh.603712')
    start_date = config.get('StartDate', '20250401')
    end_date = config.get('EndDate', '')
    
    # 处理日期格式
    formatted_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    
    # 如果没有提供结束日期，使用当前日期
    if not end_date:
        end_date = datetime.today().strftime('%Y%m%d')
    formatted_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    # 登录系统
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return
    
    # 查询历史K线数据
    rs = bs.query_history_k_data_plus(
        stock_code,
        "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
        start_date=formatted_start,
        end_date=formatted_end,
        frequency="d",
        adjustflag="3"
    )
    
    if rs.error_code != '0':
        print(f"查询失败: {rs.error_msg}")
        bs.logout()
        return
    
    # 处理结果集
    data_list = []
    while (rs.error_code == '0') and rs.next():
        data_list.append(rs.get_row_data())
    
    result = pd.DataFrame(data_list, columns=rs.fields)
    
    # 生成文件名
    stock_part = stock_code.split('.')[1]
    csv_filename = f"{stock_part}_{start_date}_{end_date if end_date else 'latest'}.csv"
    
    # 保存到CSV
    result.to_csv(csv_filename, index=False)
    print(f"数据已保存到: {os.path.abspath(csv_filename)}")
    print(f"共获取 {len(result)} 条记录")
    
    # 登出系统
    bs.logout()

if __name__ == "__main__":
    get_stock_data()