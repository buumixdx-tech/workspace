"""
Jami 消息推送器 - 事件驱动版
监听 Engine 完成信号，自动推送新闻摘要到 Jami
"""
import os
import requests
import time
import argparse
from db_manager import get_connection, add_push_log, get_pending_push_tasks
from config import JAMI_API_URL, MY_JAMI_ID
from signal_bus import SignalListener, PIPE_RESULT_READY

# 配置
FALLBACK_POLL_INTERVAL = 120 # 兜底轮询间隔（秒）
MIN_IMPORTANCE_TO_PUSH = 5    # 只推送重要度 >= 此值的新闻
POKE_INTERVAL = 300           # 如果 5 分钟没有推送，执行一次静默保活探测
JAMI_POKE_URL = JAMI_API_URL.replace("/send", "/poke")

# 全局变量记录最后一次成功互动的时刻
last_interaction_time = 0

def format_jami_message(news):
    lines = []
    # 兼容“重要度”和“重要程度”
    importance = news.get('重要度') or news.get('重要程度', 3)
    stars = "⭐" * int(importance or 3)
    lines.append(f"标题：{news.get('标题') or '无'}")
    lines.append(f"重要度：{stars} ({importance}/5)")

    lines.append(f"发布来源：{news.get('发布来源') or '无'}")
    reprint_source = (news.get('转载来源') or "").strip()
    if reprint_source:
        lines.append(f"转载来源：{reprint_source}")
    lines.append(f"消息类型：{news.get('消息类型') or '无'}")
    lines.append(f"发布时间：{news.get('发布时间') or '无'}")
    lines.append(f"综述：{news.get('综述') or '无'}")
    lines.append(f"影响板块：{news.get('影响板块') or '无'}")
    lines.append(f"直接提到的个股：{news.get('直接提到的个股') or '无'}")
    lines.append(f"可能影响的个股：{news.get('可能影响的个股') or '无'}")
    # 提取链接本身，去除可能附带的正文预览
    raw_link = news.get('原文链接') or ""
    clean_link = raw_link.split(' ')[0] if 'http' in raw_link else raw_link
    lines.append(f"原文链接：<{clean_link or '无'}>")
    return "\n".join(lines)

def silent_poke():
    """发送静默探测信号保活"""
    global last_interaction_time
    print(f"[{time.strftime('%H:%M:%S')}] 正在发送静默保活信号...")
    try:
        res = requests.get(f"{JAMI_POKE_URL}?to={MY_JAMI_ID}", timeout=10)
        if res.status_code == 200:
            print(f"  ✓ 保活信号已送达信号塔")
            last_interaction_time = time.time()
        else:
            print(f"  ✗ 保活失败: HTTP {res.status_code}")
    except Exception as e:
        print(f"  ✗ 保活系统异常: {e}")

def process_push_queue():
    """处理待推送队列"""
    channel = "jami"
    print(f"[{time.strftime('%H:%M:%S')}] 检查 {channel} 待推送任务...")
    
    # 1. 获取尚未成功推送的新闻
    pending_news = get_pending_push_tasks(channel, limit=20)
    
    if not pending_news:
        print("没有发现待推送的新闻。")
        return 0

    print(f"发现 {len(pending_news)} 条待推送新闻。")
    success_count = 0

    for news in pending_news:
        news_id = news['id']
        importance = news.get('重要度') or news.get('重要程度', 3)
        title = news.get('标题', '未命名')
        
        # 重要度过滤：跳过低重要度新闻
        if int(importance) < MIN_IMPORTANCE_TO_PUSH:

            print(f"跳过 #{news_id}: 重要度 {importance} < {MIN_IMPORTANCE_TO_PUSH}")
            continue
            
        message = format_jami_message(news)
        
        print(f"正在推送 #{news_id}: {title[:20]}...")
        
        try:
            payload = {"to": MY_JAMI_ID, "msg": message}
            api_start = time.time()
            # 10 秒超时
            response = requests.post(JAMI_API_URL, json=payload, timeout=10)
            duration = time.time() - api_start
            
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get('success'):
                    print(f"  ✓ 成功！耗时: {duration:.2f}s")
                    add_push_log(news_id, channel, "success")
                    success_count += 1
                else:
                    error_msg = res_json.get('detail', '未知 API 错误')
                    print(f"  ✗ API 报错: {error_msg}")
                    add_push_log(news_id, channel, "failed", error_msg)
            else:
                error_msg = f"HTTP {response.status_code}"
                print(f"  ✗ HTTP 错误: {error_msg}")
                add_push_log(news_id, channel, "failed", error_msg)
                
        except requests.exceptions.Timeout:
            print(f"  ✗ 超时 (10s)")
            add_push_log(news_id, channel, "failed", "timeout")
        except Exception as e:
            print(f"  ✗ 系统错误: {e}")
            add_push_log(news_id, channel, "failed", str(e))
        
        # 频率控制
        time.sleep(1)
    
    if success_count > 0:
        global last_interaction_time
        last_interaction_time = time.time()

    return success_count

def run_pusher_event_driven():
    """
    事件驱动模式运行推送器
    - 监听 Engine 完成信号
    - 收到信号后立即处理推送队列
    """
    print("=" * 50)
    print("Jami 推送器已启动 (事件驱动模式)")
    print(f"  兜底轮询间隔: {FALLBACK_POLL_INTERVAL}s")
    print("=" * 50)
    
    listener = SignalListener(PIPE_RESULT_READY, timeout=FALLBACK_POLL_INTERVAL)
    
    try:
        while True:
            try:
                # 等待信号（或超时）
                signal = listener.wait()
                
                if signal:
                    print(f"\n[{time.strftime('%H:%M:%S')}] 收到信号: {signal}")
                else:
                    print(f"\n[{time.strftime('%H:%M:%S')}] 兜底轮询检查...")
                
                # 处理推送队列
                success_count = process_push_queue()
                
                if success_count > 0:
                    print(f"  本轮推送完成: {success_count} 条成功")
                
                # 链路活跃度检查（如果长时间没发信，执行 Poke）
                if time.time() - last_interaction_time > POKE_INTERVAL:
                    silent_poke()
                    
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] 运行异常: {e}")
                time.sleep(5)  # 发生异常时休息一下重新开始循环
                
    except KeyboardInterrupt:
        print("\n正在关闭推送器...")
    finally:
        listener.close()
    
    print("推送器已停止。")


def main():
    parser = argparse.ArgumentParser(description="Jami 消息推送器")
    parser.add_argument("--daemon", action="store_true", help="事件驱动模式运行（推荐）")
    parser.add_argument("--once", action="store_true", help="只执行一次推送后退出")
    args = parser.parse_args()
    
    if args.daemon:
        run_pusher_event_driven()
    elif args.once:
        process_push_queue()
    else:
        # 默认执行一次（兼容旧行为）
        process_push_queue()

if __name__ == "__main__":
    main()
