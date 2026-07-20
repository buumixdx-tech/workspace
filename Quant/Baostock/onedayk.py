import baostock as bs
import pandas as pd
import os

def download_data(date):
    # 登录 Baostock
    bs.login()

    # 获取指定日期的所有股票信息
    stock_rs = bs.query_all_stock(date)
    stock_df = stock_rs.get_data()
    
    data_df = pd.DataFrame()  # 初始化空DataFrame用于存储数据
    
    print(f"开始下载 {date} 的所有股票日K线数据...")
    for code in stock_df["code"]:
        print(f"Downloading: {code}")
        k_rs = bs.query_history_k_data_plus(
            code, 
            "date,code,open,high,low,close", 
            start_date=date, 
            end_date=date
        )
        daily_data = k_rs.get_data()
        if not daily_data.empty:  # 确保有数据再合并
            data_df = pd.concat([data_df, daily_data], ignore_index=True)
    
    # 退出登录
    bs.logout()
    
    # 设置输出文件路径为脚本所在目录下的 CSV 文件
    script_dir = os.path.dirname(os.path.abspath(__file__))  # 获取脚本所在目录
    output_file = os.path.join(script_dir, "demo_assignDayData.csv")
    
    # 导出到CSV，编码为gbk以兼容中文环境
    data_df.to_csv(output_file, encoding="gbk", index=False)
    
    print(f"数据已成功保存至：{output_file}")
    print(f"共获取 {len(data_df)} 条记录")
    print(data_df.head())  # 打印前几行预览

if __name__ == '__main__':
    # 获取指定日期全部股票的日K线数据
    download_data("2025-09-12")