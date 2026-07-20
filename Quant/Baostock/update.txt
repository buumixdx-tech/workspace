import baostock as bs
import pandas as pd
from clickhouse_driver import Client
from datetime import datetime, timedelta
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
        logging.FileHandler('update_import.log')
    ]
)
logger = logging.getLogger(__name__)

# 全局配置
MAX_WORKERS = 16  # 优化并发线程数
RETRY_LIMIT = 3  # 增加重试次数
BATCH_SIZE = 8000  # ClickHouse批量插入大小
CHUNK_SIZE = 500  # 每次查询的股票数量分块

def get_all_stock_codes():
    """从AllA.xlsx获取所有沪深A股代码（处理="XXXXXX"格式）"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), "AllA.xlsx")
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return []
        
        logger.info(f"正在从 {file_path} 读取股票代码...")
        wb = load_workbook(filename=file_path, read_only=True)
        sheet = wb.active
        stock_codes = []
        
        for row in sheet.iter_rows(min_row=2, min_col=2, max_col=2):
            cell_value = str(row[0].value).strip()
            if cell_value.startswith('='):
                quoted_part = cell_value[1:].strip()
                if quoted_part.startswith('"') and quoted_part.endswith('"'):
                    code = quoted_part[1:-1].strip()
                    if code.isdigit() and len(code) == 6:
                        if code.startswith('6'):
                            stock_codes.append(f"sh.{code}")
                        elif code.startswith(('0', '3')):
                            stock_codes.append(f"sz.{code}")
        
        wb.close()
        logger.info(f"成功读取 {len(stock_codes)} 只股票代码")
        return stock_codes
    except Exception as e:
        logger.error(f"读取股票代码失败: {str(e)}", exc_info=True)
        return []

def get_existing_date_range():
    """获取ClickHouse中已有的日期范围"""
    try:
        ch_client = Client(
            host='localhost',
            port=9000,
            user='admin',
            password='admin_password',
            database='stock_data'
        )
        
        table_exists = ch_client.execute("""
            SELECT count() 
            FROM system.tables 
            WHERE database = 'stock_data' AND name = 'daily_k'
        """)
        
        if table_exists[0][0] == 0:
            logger.error("表 stock_data.daily_k 不存在")
            ch_client.disconnect()
            return None, None
        
        min_date_result = ch_client.execute("""
            SELECT min(date) 
            FROM stock_data.daily_k 
            WHERE date > '1990-01-01'
        """)
        min_date = min_date_result[0][0] if min_date_result and min_date_result[0][0] else None
        
        max_date_result = ch_client.execute("SELECT max(date) FROM stock_data.daily_k")
        max_date = max_date_result[0][0] if max_date_result and max_date_result[0][0] else None
        
        ch_client.disconnect()
        logger.info(f"现有有效数据日期范围: {min_date} 到 {max_date}")
        return min_date, max_date
    except Exception as e:
        logger.error(f"获取现有日期范围失败: {str(e)}", exc_info=True)
        return None, None

def fetch_stock_data_batch(codes, start_date, end_date, retry=0):
    """批量获取多只股票数据"""
    try:
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"登录BaoStock失败: {lg.error_msg}")
            return pd.DataFrame()
        
        all_data = []
        
        for code in codes:
            rs = bs.query_history_k_data_plus(
                code=code,
                fields="date,code,open,high,low,close,preclose,volume,amount,turn,tradestatus,isST,adjustflag",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"  # 后复权
            )
            
            if rs.error_code != '0':
                logger.warning(f"股票 {code} 查询失败: {rs.error_msg}")
                continue
                
            while rs.next():
                all_data.append(rs.get_row_data())
        
        bs.logout()
        
        if not all_data:
            return pd.DataFrame()
            
        columns = rs.fields
        df = pd.DataFrame(all_data, columns=columns)
        
        # 数据处理
        numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'turn', 'amount']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype('uint64')
        df['tradestatus'] = df['tradestatus'].astype('uint8')
        df['isST'] = df['isST'].astype('uint8')
        
        # 处理停牌日数据
        df.loc[df['tradestatus'] == 0, ['open', 'high', 'low', 'close', 'volume', 'amount']] = 0
        
        return df[[
            'code', 'date', 'open', 'high', 'low', 'close', 'preclose',
            'volume', 'amount', 'turn', 'tradestatus', 'isST', 'adjustflag'
        ]]
    except Exception as e:
        if retry < RETRY_LIMIT:
            time.sleep(2)
            return fetch_stock_data_batch(codes, start_date, end_date, retry+1)
        logger.error(f"批量获取股票数据失败(重试{RETRY_LIMIT}次): {str(e)}")
        return pd.DataFrame()

def process_stock_data(df):
    """数据处理"""
    if df.empty:
        return df
        
    df = df.copy()
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
    
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

def bulk_insert_to_clickhouse(client, df):
    """高效写入ClickHouse"""
    if df.empty:
        return 0
        
    try:
        data = [
            tuple(None if pd.isna(x) else x for x in row.values)
            for _, row in df.iterrows()
        ]
        
        total_inserted = 0
        for i in range(0, len(data), BATCH_SIZE):
            batch = data[i:i+BATCH_SIZE]
            client.execute(
                '''INSERT INTO stock_data.daily_k (
                    code, date, open, high, low, close, preclose,
                    volume, amount, turn, tradestatus, isST, adjustflag
                ) VALUES''',
                batch,
                settings={
                    'max_block_size': BATCH_SIZE,
                    'input_format_null_as_default': 1,
                    'deduplicate_blocks_in_dependent_materialized_views': 0
                }
            )
            total_inserted += len(batch)
            
        logger.info(f"成功写入 {total_inserted} 条最新数据")
        return total_inserted
    except Exception as e:
        logger.error(f"批量写入失败: {str(e)}")
        raise

def update_latest_data(start_date, end_date, stock_codes):
    """更新最新数据主流程"""
    logger.info(f"开始更新最新数据: {start_date} 到 {end_date}")
    
    ch_client = Client(
        host='localhost',
        port=9000,
        user='admin',
        password='admin_password',
        database='stock_data',
        settings={
            'connect_timeout': 30,
            'send_receive_timeout': 120,
            'distributed_aggregation_memory_efficient': 1
        }
    )
    
    total_rows = 0
    failed_codes = []
    
    # 分块处理
    for i in range(0, len(stock_codes), CHUNK_SIZE):
        chunk_codes = stock_codes[i:i+CHUNK_SIZE]
        logger.info(f"处理股票代码块 {i//CHUNK_SIZE + 1} (共{len(stock_codes)//CHUNK_SIZE + 1}块)")
        
        # 批量获取数据
        df = fetch_stock_data_batch(chunk_codes, start_date, end_date)
        if df.empty:
            logger.warning(f"代码块 {i//CHUNK_SIZE + 1} 无数据（可能是非交易日）")
            continue
            
        # 数据处理
        df = process_stock_data(df)
        if df.empty:
            continue
            
        # 写入ClickHouse
        try:
            rows_inserted = bulk_insert_to_clickhouse(ch_client, df)
            total_rows += rows_inserted
        except Exception as e:
            logger.error(f"写入代码块 {i//CHUNK_SIZE + 1} 失败: {str(e)}")
            failed_codes.extend(chunk_codes)
    
    ch_client.disconnect()
    return total_rows, failed_codes

def main():
    """主函数：更新最新数据"""
    logger.info("="*50)
    logger.info("开始更新最新数据...")
    logger.info("="*50)
    
    # 获取现有数据范围
    _, max_date = get_existing_date_range()
    
    if max_date is None:
        logger.error("无法获取现有数据范围，可能是数据库为空")
        return
    
    # 转换日期格式
    if isinstance(max_date, str):
        max_date = datetime.strptime(max_date, "%Y-%m-%d").date()
    
    # 计算需要更新的日期范围
    start_date = max_date + timedelta(days=1)
    end_date = datetime.today().strftime("%Y-%m-%d")
    
    if start_date > datetime.today().date():
        logger.info(f"数据已更新到最新日期 {max_date}")
        return
    
    logger.info(f"需要更新的数据范围: {start_date} 到 {end_date}")
    
    # 获取所有股票代码
    all_codes = get_all_stock_codes()
    if not all_codes:
        logger.error("无法获取股票代码列表，终止操作")
        return
    
    # 更新最新数据
    start_time = time.time()
    total_rows, failed_codes = update_latest_data(
        str(start_date), 
        end_date, 
        all_codes
    )
    duration = time.time() - start_time
    
    # 结果报告
    success_rate = ((len(all_codes) - len(failed_codes)) / len(all_codes)) * 100 if all_codes else 0
    logger.info(f"""
{'='*50}
最新数据更新完成报告
{'='*50}
起始日期: {start_date}
结束日期: {end_date}
总股票数: {len(all_codes)}
成功处理: {len(all_codes) - len(failed_codes)}
失败数量: {len(failed_codes)}
总行数: {total_rows}
成功率: {success_rate:.2f}%
耗时: {duration:.2f}秒
{'='*50}""")
    
    if failed_codes:
        logger.info(f"失败代码示例(前10个): {failed_codes[:10]}")

if __name__ == "__main__":
    main()