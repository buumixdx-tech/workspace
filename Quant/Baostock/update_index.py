import baostock as bs
import pandas as pd
from clickhouse_driver import Client
from datetime import datetime, timedelta
import time
import logging
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('update_index.log')
    ]
)
logger = logging.getLogger(__name__)

# 全局配置
RETRY_LIMIT = 3
BATCH_SIZE = 1000

# 主要指数代码列表（可根据需要扩展）
INDEX_CODES = [
    'sh.000001',  # 上证指数
    'sz.399001',  # 深证成指
]

def get_existing_index_date_range():
    """获取ClickHouse中指数数据的日期范围"""
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
            WHERE database = 'stock_data' AND name = 'index_k'
        """)
        
        if table_exists[0][0] == 0:
            logger.error("表 stock_data.index_k 不存在")
            ch_client.disconnect()
            return None, None
        
        min_date_result = ch_client.execute("""
            SELECT min(date) 
            FROM stock_data.index_k 
            WHERE date > '1990-01-01'
        """)
        min_date = min_date_result[0][0] if min_date_result and min_date_result[0][0] else None
        
        max_date_result = ch_client.execute("SELECT max(date) FROM stock_data.index_k")
        max_date = max_date_result[0][0] if max_date_result and max_date_result[0][0] else None
        
        ch_client.disconnect()
        logger.info(f"现有指数数据日期范围: {min_date} 到 {max_date}")
        return min_date, max_date
    except Exception as e:
        logger.error(f"获取现有指数日期范围失败: {str(e)}", exc_info=True)
        return None, None

def fetch_index_data(code, start_date, end_date, retry=0):
    """获取单只指数数据"""
    try:
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"登录BaoStock失败: {lg.error_msg}")
            return pd.DataFrame()
        
        rs = bs.query_history_k_data_plus(
            code=code,
            fields="date,code,open,high,low,close,preclose,volume,turn,tradestatus",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 后复权
        )
        
        if rs.error_code != '0':
            logger.warning(f"指数 {code} 查询失败: {rs.error_msg}")
            bs.logout()
            return pd.DataFrame()
            
        data = []
        while rs.next():
            data.append(rs.get_row_data())
        
        bs.logout()
        
        if not data:
            return pd.DataFrame()
            
        columns = rs.fields
        df = pd.DataFrame(data, columns=columns)
        
        # 数据处理
        numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'turn']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype('uint64')
        df['tradestatus'] = df['tradestatus'].astype('uint8')
        
        # 处理非交易日数据
        df.loc[df['tradestatus'] == 0, ['open', 'high', 'low', 'close', 'volume']] = 0
        
        return df
    except Exception as e:
        if retry < RETRY_LIMIT:
            time.sleep(2)
            return fetch_index_data(code, start_date, end_date, retry+1)
        logger.error(f"获取指数 {code} 数据失败(重试{RETRY_LIMIT}次): {str(e)}")
        return pd.DataFrame()

def process_index_data(df):
    """指数数据处理"""
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
        'volume': 'uint64',
        'tradestatus': 'uint8'
    }
    
    for col, dtype in type_map.items():
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
            except Exception as e:
                logger.warning(f"列 {col} 转换失败: {str(e)}")
                df[col] = None
    
    return df[[
        'code', 'date', 'open', 'high', 'low', 'close', 'preclose',
        'volume', 'turn', 'tradestatus'
    ]]

def bulk_insert_index_to_clickhouse(client, df):
    """高效写入ClickHouse指数表"""
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
                '''INSERT INTO stock_data.index_k (
                    code, date, open, high, low, close, preclose,
                    volume, turn, tradestatus
                ) VALUES''',
                batch,
                settings={
                    'max_block_size': BATCH_SIZE,
                    'input_format_null_as_default': 1
                }
            )
            total_inserted += len(batch)
            
        logger.info(f"成功写入 {total_inserted} 条指数数据")
        return total_inserted
    except Exception as e:
        logger.error(f"批量写入指数数据失败: {str(e)}")
        raise

def update_index_data(start_date, end_date):
    """更新指数数据主流程"""
    logger.info(f"开始更新指数数据: {start_date} 到 {end_date}")
    
    ch_client = Client(
        host='localhost',
        port=9000,
        user='admin',
        password='admin_password',
        database='stock_data',
        settings={
            'connect_timeout': 30,
            'send_receive_timeout': 120
        }
    )
    
    total_rows = 0
    failed_codes = []
    
    for code in INDEX_CODES:
        logger.info(f"处理指数: {code}")
        
        # 获取指数数据
        df = fetch_index_data(code, start_date, end_date)
        if df.empty:
            logger.warning(f"指数 {code} 无数据（可能是非交易日）")
            failed_codes.append(code)
            continue
            
        # 数据处理
        df = process_index_data(df)
        if df.empty:
            failed_codes.append(code)
            continue
            
        # 写入ClickHouse
        try:
            rows_inserted = bulk_insert_index_to_clickhouse(ch_client, df)
            total_rows += rows_inserted
            logger.info(f"指数 {code} 写入 {rows_inserted} 条数据")
        except Exception as e:
            logger.error(f"写入指数 {code} 失败: {str(e)}")
            failed_codes.append(code)
    
    ch_client.disconnect()
    return total_rows, failed_codes

def main():
    """主函数：更新指数数据"""
    logger.info("="*50)
    logger.info("开始更新指数数据...")
    logger.info("="*50)
    
    # 获取现有数据范围
    _, max_date = get_existing_index_date_range()
    
    if max_date is None:
        # 如果表不存在或为空，从较早期开始获取
        start_date = "1990-01-01"
        logger.info("指数表为空或不存在，将从历史数据开始获取")
    else:
        # 转换日期格式
        if isinstance(max_date, str):
            max_date = datetime.strptime(max_date, "%Y-%m-%d").date()
        
        # 计算需要更新的日期范围
        start_date = max_date + timedelta(days=1)
        end_date = datetime.today().strftime("%Y-%m-%d")
        
        if start_date > datetime.today().date():
            logger.info(f"指数数据已更新到最新日期 {max_date}")
            return
    
    end_date = datetime.today().strftime("%Y-%m-%d")
    logger.info(f"需要更新的指数数据范围: {start_date} 到 {end_date}")
    
    # 更新指数数据
    start_time = time.time()
    total_rows, failed_codes = update_index_data(
        str(start_date), 
        end_date
    )
    duration = time.time() - start_time
    
    # 结果报告
    success_rate = ((len(INDEX_CODES) - len(failed_codes)) / len(INDEX_CODES)) * 100 if INDEX_CODES else 0
    logger.info(f"""
{'='*50}
指数数据更新完成报告
{'='*50}
起始日期: {start_date}
结束日期: {end_date}
总指数数: {len(INDEX_CODES)}
成功处理: {len(INDEX_CODES) - len(failed_codes)}
失败数量: {len(failed_codes)}
总行数: {total_rows}
成功率: {success_rate:.2f}%
耗时: {duration:.2f}秒
{'='*50}""")
    
    if failed_codes:
        logger.info(f"失败的指数代码: {failed_codes}")

if __name__ == "__main__":
    main()