# main.py

from modules.core_driver import run_backtest

if __name__ == "__main__":
    print("🚀 启动量化回测系统...")
    config_file_path = "config/backtesting_config.yaml"
    
    try:
        # 运行回测
        driver = run_backtest(config_file_path)
        
        # 可选：打印摘要统计
        stats = driver.get_summary_stats()
        print("\n📈 回测摘要:")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}" if 'ratio' in key else f"  {key}: {value:,.2f}")
            else:
                print(f"  {key}: {value}")
                
        print("\n✅ 回测系统执行完毕。")
        
    except Exception as e:
        print(f"❌ 回测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
