# main.py
import os
from datetime import datetime

# --- 1. 导入必要的模块 ---
# 假设项目根目录在 Python 路径中，或者脚本运行时在根目录
# 如果需要手动添加项目根目录到路径，可以取消下面几行的注释
# import sys
# project_root = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, project_root)

from modules.db import ClickHouseDB
from modules.config_loader import load_config
# 或者使用 flu.py 中定义的 get_config 函数
# from strategies.flu import get_config # 如果你把它移到了策略模块或 utils

from strategies.FirstLimitUpStrategy import FirstLimitUpStrategy

def load_strategy_config(config_file_name: str = 'flu.ini') -> dict:
    """
    加载策略配置文件。
    """
    try:
        # 使用 config_loader 加载配置
        config_parser = load_config(config_file_name)
        # 转换为普通字典
        config_dict = dict(config_parser['latest']) # 假设配置在 DEFAULT section
        
        # 可以在这里添加额外的配置处理或验证
        # 例如，将字符串 'None' 转换为 None
        # if config_dict.get('end_date', '').lower() == 'none':
        #     config_dict['end_date'] = None
        return config_dict
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        raise

def main():
    """
    主函数：执行首板回调策略。
    """
    print("--- 开始执行首板回调策略 ---")
    start_time = datetime.now()
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    db = None
    try:
        # --- 2. 准备依赖项 ---
        # 2.1. 创建数据库连接
        print("正在连接数据库...")
        db = ClickHouseDB()
        print("数据库连接成功。")

        # 2.2. 加载配置
        print("正在加载配置...")
        config = load_strategy_config('flu.ini')
        print(f"配置加载成功: {config}")

        # 2.3. (可选) 指定选股范围
        # selected_stocks = ['sz.002767','sz.300943','sh.600748','sh.600001'] # 示例
        selected_stocks = None # 设置为 None 表示全市场选股

        # --- 3. 创建策略实例 ---
        print("正在创建策略实例...")
        strategy = FirstLimitUpStrategy(
            db=db,
            config=config,
            stock_codes=selected_stocks # 传入选股范围
        )
        print(f"策略实例创建成功: {strategy.get_name()}")

        # --- 4. 执行策略 ---
        print("正在执行策略...")
        # run() 返回的是 ['策略日期', '股票代码'] 的 DataFrame
        result_df = strategy.run()
        print("策略执行完成。")

        # --- 5. 输出结果 (可选) ---
        print("\n--- 策略执行结果 ---")
        if not result_df.empty:
            print(f"共选出 {len(result_df)} 只稳定回调股票。")
            print("前10只股票:")
            print(result_df.head(10))
            
            # --- 6. 保存结果到 Excel ---
            print("\n正在保存结果到 Excel...")
            # 调用策略自己的 save_results 方法
            # save_results 会使用存储在策略实例中的完整数据 (self._full_results_df)
            # 和 T 日 (self._t_date_str) 来生成文件和内容
            strategy.save_results(result_df) # result_df 参数在此实现中未直接使用
            print("结果保存完成。")
            
        else:
            print("策略未选出任何稳定回调股票。")
            # 仍然可以调用 save_results 来生成一个只有参数的空文件
            strategy.save_results(result_df)
            print("已生成空结果文件(仅包含参数)。")


    except Exception as e:
        print(f"执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # --- 7. 清理资源 ---
        if db:
            try:
                db.close()
                print("数据库连接已关闭。")
            except Exception as e:
                print(f"关闭数据库连接时出错: {e}")

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\n--- 策略执行结束 ---")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {duration}")


if __name__ == '__main__':
    main()