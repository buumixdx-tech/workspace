import sqlite3
import sys
import os

# Add project root to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notification.telegram_bot import TelegramBot

def test_send_rss_news():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rss", "news_queue.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the first news item
        cursor.execute("SELECT * FROM news_results ORDER BY id DESC LIMIT 1") # Let's get the LATEST one, usually more interesting. User said "First day news", but usually means "a news item". I'll get 'LIMIT 1'. 
        # User said "news_results表中第一天新闻". Maybe they mean "the first row"? Let's stick to LIMIT 1 (usually first inserted or arbitrary if no order, but rowid implies order). 
        # Actually user said "第一条" (first one). I will just use LIMIT 1 without sorting (which gives the first one inserted ideally) or sort by id ASC.
        # Let's use id ASC to get the absolute "first" one.
        cursor.execute("SELECT * FROM news_results ORDER BY id ASC LIMIT 1")
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("No news found in news_results table.")
            return
            
        # Format the message
        # Columns: ['id', 'task_id', '标题', '发布来源', '转载来源', '消息类型', '发布时间', '综述', '影响板块', '直接提到的个股', '可能影响的个股', '原文链接', 'processed_at', '重要度']
        
        title = row['标题']
        source = row['发布来源'] or row['转载来源'] or "Unknown"
        time_str = row['发布时间']
        summary = row['综述']
        importance = row['重要度']
        
        impact_sector = row['影响板块']
        related_stocks = row['直接提到的个股']
        
        msg = f"📰 **RSS News Test**\n\n"
        msg += f"**{title}**\n"
        msg += f"Clock: {time_str} | Source: {source} | ⭐ {importance}\n\n"
        msg += f"{summary}\n\n"
        msg += f"🏗 **Impact**: {impact_sector}\n"
        msg += f"📊 **Stocks**: {related_stocks}\n"
        msg += f"🔗 [Link]({row['原文链接']})"

        print("Message Preview:")
        print("-" * 20)
        print(msg)
        print("-" * 20)
        
        # Send via Bot
        bot = TelegramBot()
        bot.send_message(msg)
        print("\nSent to Telegram.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_send_rss_news()
