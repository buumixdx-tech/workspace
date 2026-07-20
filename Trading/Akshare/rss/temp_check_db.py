
import sqlite3
import os

DB_PATH = "news_queue.db"

def check_db():
    if not os.path.exists(DB_PATH):
        print("Database not found")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Checking last 5 tasks in task_queue:")
    cursor.execute("SELECT id, title, title_hash, created_at FROM task_queue ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row['id']}, Title: {row['title'][:20]}..., Hash: {row['title_hash']}, Created: {row['created_at']}")
    
    conn.close()

if __name__ == "__main__":
    check_db()
