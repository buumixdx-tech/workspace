import baostock as bs
import pandas as pd
from clickhouse_driver import Client
from datetime import datetime
import concurrent.futures
import time
import logging
from openpyxl import load_workbook
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('stock_import.log')
    ]
)
logger = logging.getLogger(__name__)

# 全局配置
START_DATE = "2025-07-28"
END_DATE = datetime.today().strftime("%Y-%m-%d")
MAX_WORKERS = 10  # 并发线程数
RETRY_LIMIT = 2

def get_all_stock_codes():
    """从AllA.xlsx获取所有沪深A股代码（处理="XXXXXX"格式）"""
    try:
        # 文件路径处理
        file_path = os.path.join(os.path.dirname(__file__), "AllA.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return []
        
        logger.info(f"正在从 {file_path} 读取股票代码...")
        
        # 使用openpyxl读取Excel
        wb = load_workbook(filename=file_path, read_only=True)
        sheet = wb.active
        
        stock_codes = []
        
        # 从B2单元格开始读取（第2行第2列）
        print("=== 开始提取股票代码 ===")
        stock_codes = []
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, min_col=2, max_col=2), start=2):
            cell_value = str(row[0].value).strip()  # 转为字符串并去除首尾空格
            print(f"行 {row_idx}: 原始值 = {repr(row[0].value)}", end=" -> ")
            
            # 处理 ="XXXXXX" 或 = "XXXXXX" 格式
            if cell_value.startswith('='):
                # 统一去除等号并清理引号
                quoted_part = cell_value[1:].strip()  # 去除等号和后边的空格
                if quoted_part.startswith('"') and quoted_part.endswith('"'):
                    code = quoted_part[1:-1].strip()  # 提取引号内容
                    
                    # 验证6位数字
                    if code.isdigit() and len(code) == 6:
                        # 补全市场前缀
                        if code.startswith('6'):
                            full_code = f"sh.{code}"
                        elif code.startswith(('0', '3')):
                            full_code = f"sz.{code}"
                        else:
                            print(f"[警告]未知市场代码: {code}")
                            continue
                        
                        stock_codes.append(full_code)
                        print(f"提取成功: {full_code}")
                    else:
                        print(f"[忽略]无效代码格式: {code}")
                else:
                    print(f"[忽略]非标准引号格式")
            else:
                print(f"[忽略]非等号开头格式")

        wb.close()

        # 打印最终结果
        print("\n=== 提取结果汇总 ===")
        print(f"成功提取数量: {len(stock_codes)}")
        print("示例代码(前20个):")
        for i, code in enumerate(stock_codes[:20], 1):
            print(f"{i}. {code}")
        if len(stock_codes) > 20:
            print(f"...(共 {len(stock_codes)} 个)")
        
        logger.info(f"成功读取 {len(stock_codes)} 只股票代码")
        return stock_codes
        
    except Exception as e:
        logger.error(f"读取股票代码失败: {str(e)}", exc_info=True)
        return []

def fetch_stock_data(code, start_date, end_date, retry=0):
    """获取单只股票数据"""
    try:
        bs.login()
        
        # 查询字段新增 isST
        rs = bs.query_history_k_data_plus(
            code=code,
            fields="date,open,high,low,close,preclose,volume,amount,turn,tradestatus,isST,adjustflag",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 后复权
        )
        
        if rs.error_code != '0':
            logger.warning(f"股票 {code} 查询失败: {rs.error_msg}")
            return pd.DataFrame()
            
        # 转换为DataFrame
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        df = pd.DataFrame(data_list, columns=rs.fields)
        bs.logout()

        if not df.empty:
            # 数据处理
            df['code'] = code
            
            # 类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'turn', 'amount']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype('uint64')
            df['tradestatus'] = df['tradestatus'].astype('uint8')
            df['isST'] = df['isST'].astype('uint8')  # 确保isST为0/1
            
            # 处理停牌日数据
            df.loc[df['tradestatus'] == '0', ['open', 'high', 'low', 'close', 'volume', 'amount']] = 0
            
            return df[[
                'code', 'date', 'open', 'high', 'low', 'close', 'preclose',
                'volume', 'amount', 'turn', 'tradestatus', 'isST', 'adjustflag'
            ]]
            
        return pd.DataFrame()
        
    except Exception as e:
        if retry < RETRY_LIMIT:
            time.sleep(2)
            return fetch_stock_data(code, start_date, end_date, retry+1)
        logger.error(f"股票 {code} 获取失败(重试{RETRY_LIMIT}次): {str(e)}")
        return pd.DataFrame()

def initialize_database():
    """初始化数据库表结构（更新版）"""
    ch_client = Client(
        host='localhost',
        port=9000,
        user='admin',
        password='admin_password',  
        database='default'
    )
    ch_client.execute("CREATE DATABASE IF NOT EXISTS stock_data")
    ch_client.execute("""
    CREATE TABLE IF NOT EXISTS stock_data.daily_k
    (
        code LowCardinality(String),
        date Date,
        open Float32,
        high Float32,
        low Float32,
        close Float32,
        preclose Float32 COMMENT '前收盘价',
        volume UInt64,
        amount Float64,
        turn Float32 COMMENT '换手率(%)',
        tradestatus UInt8 DEFAULT 1 COMMENT '交易状态(1:正常 0:停牌)',
        isST UInt8 DEFAULT 0 COMMENT '是否ST(0:否 1:是)',
        adjustflag String,
        dt DateTime DEFAULT now()
    )
    ENGINE = ReplacingMergeTree(dt)
    ORDER BY (code, date)
    PARTITION BY toYear(date)
    SETTINGS index_granularity = 1024;
    """)

def bulk_insert_to_clickhouse(client, df):
    """安全写入ClickHouse（解决日期问题）"""
    if df.empty:
        return
        
    try:
        # 确保数据类型正确
        df = df.copy()
        
        # 转换数据为Python原生类型
        data = []
        for _, row in df.iterrows():
            data.append(tuple(
                None if pd.isna(x) else x 
                for x in row.values
            ))
        
        # 分批写入
        batch_size = 10000
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            
            client.execute(
                '''INSERT INTO stock_data.daily_k (
                    code, date, open, high, low, close, preclose,
                    volume, amount, turn, tradestatus, isST, adjustflag
                ) VALUES''',
                batch,
                settings={
                    'max_block_size': batch_size,
                    'input_format_null_as_default': 1
                }
            )
            logger.info(f"已写入批次 {i//batch_size + 1} (行 {i}-{i+len(batch)})")
            
    except Exception as e:
        logger.error(f"写入失败: {str(e)}\n首行数据: {df.iloc[0].to_dict()}")
        raise
def process_stock_data(df, code):
    """增强的日期处理"""
    df = df.copy()
    df['code'] = code
    
    # 确保日期列转换为datetime.date对象
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
    
    # 类型转换映射
    type_map = {
        'open': 'float32',
        'high': 'float32', 
        'low': 'float32',
        'close': 'float32',
        'preclose': 'float32',
        'turn': 'float32',
        'amount': 'float64',
        'volume': 'uint64',
        'tradestatus': 'uint8',
        'isST': 'uint8',
        'adjustflag': 'str'
    }
    
    for col, dtype in type_map.items():
        if col in df.columns:
            try:
                if dtype == 'str':
                    df[col] = df[col].astype(str)
                else:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
            except Exception as e:
                logger.warning(f"列 {col} 转换失败: {str(e)}")
                df[col] = None
    
    return df[[
        'code', 'date', 'open', 'high', 'low', 'close', 'preclose',
        'volume', 'amount', 'turn', 'tradestatus', 'isST', 'adjustflag'
    ]]

def main_initial_import():
    """增强稳定性的主流程"""
    initialize_database()
    all_codes = get_all_stock_codes()
    
    # 配置更稳定的连接
    ch_client = Client(
        host='localhost',
        port=9000,
        user='admin',
        password='admin_password',
        database='stock_data',
        settings={
            'connect_timeout': 30,
            'send_receive_timeout': 60
        }
    )
    
    failed_codes = []
    for idx, code in enumerate(all_codes, 1):  # 测试前100只
        try:
            logger.info(f"\n[{idx}/{len(all_codes)}] 处理 {code}...")
            
            # 获取并处理数据
            df = fetch_stock_data(code, START_DATE, END_DATE)
            if df.empty:
                logger.warning("无有效数据")
                continue
                
            # 转换数据类型
            df = process_stock_data(df, code)
            
            # 写入数据
            bulk_insert_to_clickhouse(ch_client, df)
            
        except Exception as e:
            failed_codes.append(code)
            logger.error(f"处理失败: {str(e)}", exc_info=True)
            time.sleep(5)
    
    # 结果报告
    success = len(all_codes[:100]) - len(failed_codes)
    logger.info(f"\n=== 测试结果 ===")
    logger.info(f"成功率: {success}/100 ({success/100:.0%})")
    if failed_codes:
        logger.info(f"失败代码: {failed_codes[:20]}")
    
    ch_client.disconnect()
def test_single_stock():
    """测试单只股票数据获取"""
    test_code = "sh.600000"  # 浦发银行
    start_date = "2025-07-28"
    end_date = datetime.today().strftime("%Y-%m-%d")
    
    logger.info(f"\n{'='*40}")
    logger.info(f"测试股票: {test_code}")
    logger.info(f"时间范围: {start_date} 至 {end_date}")
    logger.info(f"{'='*40}\n")
    
    # 获取数据
    df = fetch_stock_data(test_code, start_date, end_date)
    
    # 输出结果
    if not df.empty:
        logger.info(f"\n获取成功! 数据样本:\n{df.head(3).to_string()}")
        logger.info(f"\n数据统计:\n{df.describe().to_string()}")
    else:
        logger.warning("未获取到数据")

if __name__ == "__main__":
    # 设置日志级别为DEBUG以查看详细信息
    logger.setLevel(logging.DEBUG)
    # 先测试单只股票
    #test_single_stock()
    # 测试取所有股票
    #get_all_stock_codes()
    main_initial_import()