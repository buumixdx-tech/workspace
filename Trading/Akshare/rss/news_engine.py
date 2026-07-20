"""
新闻处理引擎 (Consumer Engine) - 事件驱动版
采用 Named Pipes 信号驱动 + ThreadPoolExecutor 并发处理
"""
import os
import json
import time
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from db_manager import (
    init_db, get_pending_task, mark_task_done, 
    mark_task_error, reset_task_to_pending, get_queue_stats, 
    get_connection, get_all_pending_tasks
)
from dify_caller import call_dify_workflow
from signal_bus import SignalListener, SignalSender, PIPE_TASK_READY, PIPE_RESULT_READY

# 配置
MAX_RETRIES = 3
MAX_WORKERS = 8                # 线程池并发数
FALLBACK_POLL_INTERVAL = 60    # 兜底轮询间隔（秒）
RETRY_DELAYS = [10, 20, 40]    # 指数退避：10s, 20s, 40s

def process_single_task(task):
    """处理单个任务（线程安全）"""
    task_id = task['id']
    title = task.get('title', '')[:30]
    raw_content = task.get('raw_content', '')
    retries = task['retries']
    
    # 简单的去除非法字符，打印安全
    safe_title = title.encode('utf-8', 'ignore').decode('utf-8')
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 处理任务 #{task_id}: {safe_title}...")
    
    # 1. 解析 JSON 内容（直接从数据库读取）
    try:
        news_data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        mark_task_error(task_id, f"JSON 解析失败: {e}", increment_retry=False)
        return False
    
    # 2. 调用 Dify
    success, result = call_dify_workflow(news_data)
    
    if success:
        # 3. 存储结果
        mark_task_done(task_id, result)
        print(f"  ✓ 任务 #{task_id} 处理成功")
        return True
    else:
        # 4. 处理失败
        print(f"  ✗ 任务 #{task_id} 失败: {result}")
        
        if retries < MAX_RETRIES - 1:
            # 还有重试机会
            mark_task_error(task_id, result, increment_retry=True)
            reset_task_to_pending(task_id)
            delay = RETRY_DELAYS[min(retries, len(RETRY_DELAYS) - 1)]
            print(f"  → 将在 {delay} 秒后重试 (第 {retries + 2}/{MAX_RETRIES} 次)")
            time.sleep(delay)
        else:
            # 超过最大重试次数
            mark_task_error(task_id, f"超过最大重试次数: {result}", increment_retry=True)
            print(f"  ✗ 任务 #{task_id} 已放弃（超过最大重试次数）")
        return False

def get_specific_task(task_id):
    """获取指定ID的任务（如果状态允许）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            # 只有 pending 或 error (重试) 的可以手动触发
            # update status
            cursor.execute(
                "UPDATE task_queue SET status = 'processing', updated_at = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), task_id)
            )
            conn.commit()
            return dict(row)
        return None
    finally:
        conn.close()

def run_engine_event_driven():
    """
    事件驱动模式运行引擎
    - 使用 Named Pipes 接收信号
    - 使用 ThreadPoolExecutor 并发处理
    - 保留兜底轮询机制
    """
    print("=" * 50)
    print("新闻处理引擎已启动 (事件驱动模式)")
    print(f"  并发线程数: {MAX_WORKERS}")
    print(f"  兜底轮询间隔: {FALLBACK_POLL_INTERVAL}s")
    print("=" * 50)
    
    # 初始化数据库
    init_db()
    
    # 创建信号监听器
    listener = SignalListener(PIPE_TASK_READY, timeout=FALLBACK_POLL_INTERVAL)
    
    # 创建线程池
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        try:
            while True:
                # 等待信号（或超时）
                signal = listener.wait()
                
                if signal:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 收到信号: {signal}")
                else:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 兜底轮询检查...")
                
                # 批量获取待处理任务
                pending_tasks = get_all_pending_tasks(limit=50)
                
                if not pending_tasks:
                    stats = get_queue_stats()
                    print(f"  暂无待处理任务 (完成:{stats.get('done', 0)} 错误:{stats.get('error', 0)})")
                    continue
                
                print(f"  发现 {len(pending_tasks)} 个待处理任务，开始并发处理...")
                
                # 提交所有任务到线程池
                futures = {executor.submit(process_single_task, task): task for task in pending_tasks}
                
                # 等待本批次完成
                success_count = 0
                for future in as_completed(futures):
                    try:
                        if future.result():
                            success_count += 1
                    except Exception as e:
                        task = futures[future]
                        print(f"  ✗ 任务 #{task['id']} 执行异常: {e}")
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 本批次完成: {success_count}/{len(pending_tasks)} 成功")
                
                # 通知推送器
                if success_count > 0:
                    SignalSender.send(PIPE_RESULT_READY)
                    print("  已发送结果就绪信号")
                    
        except KeyboardInterrupt:
            print("\n正在关闭引擎...")
        finally:
            listener.close()
    
    print("引擎已停止。")

def run_engine_legacy(limit=None, target_ids=None):
    """
    传统模式运行引擎（兼容旧版调用方式）
    
    Args:
        limit: 最大处理数量，None 表示无限
        target_ids: 指定要处理的任务 ID 列表
    """
    print("=" * 50)
    print("新闻处理引擎已启动 (传统模式)")
    if target_ids:
        print(f"模式: 指定任务 ({len(target_ids)} 个)")
    elif limit:
        print(f"模式: 批量处理 (上限 {limit} 个)")
    else:
        print(f"模式: 持续监控 | 轮询间隔: 5s")
    print("=" * 50)
    
    # 初始化数据库（确保表存在）
    init_db()
    
    processed_count = 0
    
    # 如果指定了 ID 列表
    if target_ids:
        for tid in target_ids:
            task = get_specific_task(int(tid))
            if task:
                process_single_task(task)
                processed_count += 1
            else:
                print(f"任务 #{tid} 未找到或不可处理")
        print(f"\n指定任务处理完成。共处理 {processed_count} 个。")
        return

    # 常规循环
    while True:
        # 检查 limit
        if limit is not None and processed_count >= limit:
            print(f"\n已达到处理上限 ({limit})，引擎退出。")
            break

        # 获取待处理任务
        task = get_pending_task()
        
        if task:
            success = process_single_task(task)
            processed_count += 1
        else:
            if limit is not None:
                print("\n没有更多待处理任务，引擎退出。")
                break
                
            # 无任务时显示统计并休眠
            stats = get_queue_stats()
            pending = stats.get('pending', 0)
            done = stats.get('done', 0)
            error = stats.get('error', 0)
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] 等待新任务... (待处理:{pending} 完成:{done} 错误:{error})", end="", flush=True)
            time.sleep(5)

def main():
    global MAX_WORKERS  # 必须在使用变量前声明
    
    parser = argparse.ArgumentParser(description="新闻处理引擎")
    parser.add_argument("--daemon", action="store_true", help="事件驱动模式运行（推荐）")
    parser.add_argument("--once", action="store_true", help="只处理一个任务后退出 (兼容旧参数)")
    parser.add_argument("--limit", type=int, help="处理指定数量的任务后退出")
    parser.add_argument("--ids", type=str, help="处理指定的任务 ID (逗号分隔)，例如: 1,2,5")
    parser.add_argument("--stats", action="store_true", help="显示队列统计后退出")
    parser.add_argument("--workers", type=int, default=8, help="并发线程数 (默认: 8)")
    args = parser.parse_args()
    
    # 更新全局配置
    MAX_WORKERS = args.workers
    
    if args.stats:
        init_db()
        stats = get_queue_stats()
        print("队列统计:")
        for status, count in stats.items():
            print(f"  {status}: {count}")
        return
    
    # 事件驱动模式
    if args.daemon:
        try:
            run_engine_event_driven()
        except KeyboardInterrupt:
            print("\n引擎已停止。")
        return
    
    # 传统模式
    target_ids = []
    if args.ids:
        try:
            target_ids = [int(x.strip()) for x in args.ids.split(',') if x.strip()]
        except:
            print("ID 列表格式错误")
            return

    limit = args.limit
    if args.once:
        limit = 1
        
    try:
        run_engine_legacy(limit=limit, target_ids=target_ids if target_ids else None)
    except KeyboardInterrupt:
        print("\n引擎已停止。")

if __name__ == "__main__":
    main()
