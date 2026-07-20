
import sqlite3
import os

DB_PATH = "news_queue.db"

def check_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM task_queue WHERE title_hash IS NULL OR title_hash = ''")
    empty_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM task_queue")
    total_count = cursor.fetchone()[0]
    
    print(f"Total records: {total_count}")
    print(f"Records with empty title_hash: {empty_count}")
    
    if empty_count > 0:
        print("Sample IDs with empty hash:")
        cursor.execute("SELECT id, created_at FROM task_queue WHERE title_hash IS NULL OR title_hash = '' LIMIT 5")
        for row in cursor.fetchall():
            print(f"ID: {row[0]}, Created: {row[1]}")
            
    conn.close()

if __name__ == "__main__":
    check_db()
