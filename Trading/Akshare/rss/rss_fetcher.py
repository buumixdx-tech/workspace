import os
import json
import pandas as pd
import feedparser
import requests
import urllib3
import hashlib
import time
import calendar
from datetime import datetime, timedelta, timezone

from config import RSSHUB_BASE_URL, RSS_FILE_PATH, BASE_DIR
from db_manager import enqueue_task, init_db, check_title_exists
from signal_bus import notify_engine

# 禁用自签名证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_rss(url):
    """抓取 RSS 内容"""
    full_url = f"{RSSHUB_BASE_URL}{url}" if url.startswith("/") else url
    try:
        response = requests.get(full_url, verify=False, timeout=15)
        response.raise_for_status()
        return feedparser.parse(response.text)
    except Exception as e:
        print(f"抓取失败 {full_url}: {e}")
        return None

def format_to_beijing_time(struct_time, raw_text):
    """将 struct_time (UTC) 转换为北京时间字符串"""
    if struct_time:
        try:
            # 1. 将 UTC 的 struct_time 转为秒数
            seconds = calendar.timegm(struct_time)
            # 2. 转为带 UTC 时区的 datetime
            dt_utc = datetime.fromtimestamp(seconds, tz=timezone.utc)
            # 3. 转为北京时间 (UTC+8)
            dt_beijing = dt_utc.astimezone(timezone(timedelta(hours=8)))
            return dt_beijing.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    return raw_text # 如果解析失败则返回原始文本

def main():
    if not os.path.exists(RSS_FILE_PATH):
        print(f"错误: 找不到文件 {RSS_FILE_PATH}")
        return

    # 1. 初始化数据库（确保表结构存在）
    init_db()

    # 2. 抓取所有源
    try:
        df = pd.read_excel(RSS_FILE_PATH, sheet_name="rss", header=None)
    except Exception as e:
        print(f"读取 Excel 失败: {e}")
        return

    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for index, row in df.iterrows():
        source_name = str(row[0]).strip()   # A列: 信息发布方 (如 财联社)
        channel_name = str(row[1]).strip()  # B列: 频道
        rss_url = str(row[2]).strip()       # C列: URL
        
        if not rss_url or rss_url in ["nan", "None"]: continue
            
        print(f"正在抓取: {source_name} - {channel_name}")
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue

        for entry in feed.entries:
            title = entry.get('title', '').strip()
            if not title: continue
            
            # 3. 实时去重检查 (直接查库)
            if check_title_exists(title):
                continue

            # 处理发布时间
            pub_struct = entry.get('published_parsed') or entry.get('updated_parsed')
            raw_pub_text = entry.get('published', entry.get('updated', '未知'))
            beijing_time = format_to_beijing_time(pub_struct, raw_pub_text)

            # 标准化格式
            item = {
                "标题": title,
                "发布时间": beijing_time,
                "信息发布方": source_name,
                "信息来源方": entry.get('author', None), 
                "原文链接": entry.get('link', ''),
                "内容": entry.get('summary', entry.get('description', '')),
                "抓取时间": fetch_time,
                "_internal_publisher": f"{source_name}-{channel_name}"
            }
            
            # 4. 直接入队
            # 提取并移除内部 publisher 字段
            pub = item.pop("_internal_publisher", None)
            enqueue_task(item, source_publisher=pub)

    print(f"所有 RSS 源处理完成。")
    
    # 发送信号唤醒 Engine
    if notify_engine():
        print("已发送任务就绪信号。")

if __name__ == "__main__":
    main()
