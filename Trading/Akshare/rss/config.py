"""
RSS System Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database
DB_PATH = os.path.join(BASE_DIR, "news_queue.db")

# RSS Feeds
RSS_FILE_PATH = os.path.join(BASE_DIR, "rss.xlsx")
RSSHUB_BASE_URL = "http://localhost:12000"

# Dify Configuration
DIFY_API_URL = "http://localhost/v1/workflows/run"
DIFY_API_KEY = "app-pYkBaZwd8CYlVOcMVYl6Gn5l"

# Jami Configuration
JAMI_API_URL = "http://localhost:5000/send"
MY_JAMI_ID = "f48d4bb77d7a0a8710d89d5bdadbbeb9ebfbbca9"  # 请替换为您个人的 Jami ID
