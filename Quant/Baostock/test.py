import baostock as bs

# 登录
bs.login()

# 查询股票基础信息
rs = bs.query_stock_basic()
print("错误代码:", rs.error_code)
print("错误信息:", rs.error_msg)

# 打印前10条记录
for i in range(10):
    if rs.next():
        print(rs.get_row_data())

# 登出
bs.logout()