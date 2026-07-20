"""
SQLite 数据库管理模块
负责任务队列和结果存储的数据库操作
"""
import sqlite3
import os
import hashlib
from datetime import datetime, timezone, timedelta
from config import DB_PATH

def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库和表结构"""
    conn = get_connection()
    # 启用 WAL 模式以提高并发性能
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    # 任务队列表（包含原始 JSON 内容）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            title_hash TEXT,
            publisher TEXT,
            raw_content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            retries INTEGER DEFAULT 0,
            error_msg TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # LLM 处理结果表（匹配 Dify 输出结构）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            标题 TEXT,
            发布来源 TEXT,
            转载来源 TEXT,
            消息类型 TEXT,
            发布时间 TEXT,
            综述 TEXT,
            影响板块 TEXT,
            直接提到的个股 TEXT,
            可能影响的个股 TEXT,
            原文链接 TEXT,
            重要度 INTEGER DEFAULT 3,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES task_queue(id)
        )
    """)
    
    # 动态检查并增加字段 (针对现有数据库)
    try:
        cursor.execute("SELECT 重要度 FROM news_results LIMIT 1")
    except sqlite3.OperationalError:
        print("正在为 news_results 表添加 '重要度' 字段...")
        cursor.execute("ALTER TABLE news_results ADD COLUMN 重要度 INTEGER DEFAULT 3")
    
    # 推送日志表 (Plan B)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS push_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER,
            channel TEXT,
            status TEXT,
            error_msg TEXT,
            pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (news_id) REFERENCES news_results(id)
        )
    """)
    
    # 创建索引加速查询
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON task_queue(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_hash ON task_queue(title_hash)")
    
    conn.commit()
    conn.close()
    print(f"数据库已初始化: {DB_PATH}")

def get_beijing_now():
    """获取当前北京时间字符串"""
    utc_dt = datetime.now(timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")

def get_content_hash(text):
    """生成文本的 MD5 哈希值"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def check_title_exists(title):
    """检查标题是否已存在（基于哈希）"""
    if not title:
        return False
        
    title_hash = get_content_hash(title)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 检查 task_queue
        cursor.execute("SELECT 1 FROM task_queue WHERE title_hash = ? LIMIT 1", (title_hash,))
        if cursor.fetchone():
            return True
            
        return False
    finally:
        conn.close()

def enqueue_task(news_json, source_publisher=None):
    """将新闻 JSON 加入任务队列
    
    Args:
        news_json: 新闻数据字典或 JSON 字符串
        source_publisher: (可选) 来源名称，格式"媒体名-频道名"
    """
    import json as json_module
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 如果是字典，转换为 JSON 字符串
        if isinstance(news_json, dict):
            title = news_json.get('标题', '')
            content = json_module.dumps(news_json, ensure_ascii=False)
            extracted_pub = f"{news_json.get('信息发布方', '')} - {news_json.get('信息来源方', '')}".strip(' -')
        else:
            content = news_json
            parsed = json_module.loads(news_json)
            title = parsed.get('标题', '')
            extracted_pub = f"{parsed.get('信息发布方', '')} - {parsed.get('信息来源方', '')}".strip(' -')
            
        # 生成哈希
        title_hash = get_content_hash(title)
        
        # 二次检查（防止并发插入）
        cursor.execute("SELECT 1 FROM task_queue WHERE title_hash = ?", (title_hash,))
        if cursor.fetchone():
            print(f"重复任务，跳过: {title[:20]}...")
            return None

        # 优先使用传入的 source_publisher
        publisher = source_publisher if source_publisher else extracted_pub
        
        now = get_beijing_now()
        cursor.execute(
            "INSERT INTO task_queue (title, title_hash, publisher, raw_content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (title, title_hash, publisher, content, now, now)
        )
        conn.commit()
        if cursor.rowcount > 0:
            print(f"任务已入队: {title[:30]}...")
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"入队失败: {e}")
        return None
    finally:
        conn.close()

def get_pending_task():
    """获取一个待处理任务并锁定（状态改为 processing）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 获取一个待处理任务
        cursor.execute(
            "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY created_at LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            # 锁定任务
            cursor.execute(
                "UPDATE task_queue SET status = 'processing', updated_at = ? WHERE id = ?",
                (get_beijing_now(), row['id'])
            )
            conn.commit()
            return dict(row)
        return None
    finally:
        conn.close()

def get_all_pending_tasks(limit: int = 50) -> list:
    """
    批量获取待处理任务并锁定（用于 ThreadPoolExecutor 并发处理）
    
    Args:
        limit: 最大获取数量，默认 50
    
    Returns:
        list[dict]: 任务列表
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY created_at LIMIT ?",
            (limit,)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        
        # 批量锁定
        ids = [r['id'] for r in rows]
        if ids:
            placeholders = ','.join('?' * len(ids))
            cursor.execute(
                f"UPDATE task_queue SET status = 'processing', updated_at = ? WHERE id IN ({placeholders})",
                [get_beijing_now()] + ids
            )
            conn.commit()
        return rows
    finally:
        conn.close()


def mark_task_done(task_id, result):
    """标记任务完成并存储结果"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        now = get_beijing_now()
        # 更新任务状态
        cursor.execute(
            "UPDATE task_queue SET status = 'done', updated_at = ? WHERE id = ?",
            (now, task_id)
        )
        # 存储结果（匹配 Dify 输出结构）
        cursor.execute("""
            INSERT INTO news_results 
            (task_id, 标题, 发布来源, 转载来源, 消息类型, 发布时间, 综述, 
             影响板块, 直接提到的个股, 可能影响的个股, 原文链接, 重要度, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            result.get('标题', ''),
            result.get('发布来源', ''),
            result.get('转载来源', ''),
            result.get('消息类型', ''),
            result.get('发布时间', ''),
            result.get('综述', ''),
            result.get('影响板块', ''),
            result.get('直接提到的个股', ''),
            result.get('可能影响的个股', ''),
            result.get('原文链接', ''),
            result.get('重要度', 3),
            now
        ))
        conn.commit()
        print(f"任务 {task_id} 已完成")
    except sqlite3.Error as e:
        print(f"标记完成失败: {e}")
    finally:
        conn.close()

def mark_task_error(task_id, error_msg, increment_retry=True):
    """标记任务失败"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if increment_retry:
            cursor.execute(
                """UPDATE task_queue 
                   SET status = 'error', error_msg = ?, retries = retries + 1, updated_at = ? 
                   WHERE id = ?""",
                (error_msg, get_beijing_now(), task_id)
            )
        else:
            cursor.execute(
                "UPDATE task_queue SET status = 'error', error_msg = ?, updated_at = ? WHERE id = ?",
                (error_msg, get_beijing_now(), task_id)
            )
        conn.commit()
        print(f"任务 {task_id} 标记为错误: {error_msg}")
    finally:
        conn.close()

def reset_task_to_pending(task_id):
    """将任务重置为待处理状态（用于重试）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE task_queue SET status = 'pending', updated_at = ? WHERE id = ?",
        (get_beijing_now(), task_id)
    )
    conn.commit()
    conn.close()

def get_queue_stats():
    """获取队列统计信息"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM task_queue 
        GROUP BY status
    """)
    stats = {row['status']: row['count'] for row in cursor.fetchall()}
    conn.close()
    return stats

def add_push_log(news_id, channel, status, error_msg=None):
    """记录推送状态"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        now = get_beijing_now()
        cursor.execute(
            "INSERT INTO push_logs (news_id, channel, status, error_msg, pushed_at) VALUES (?, ?, ?, ?, ?)",
            (news_id, channel, status, error_msg, now)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"记录推送日志失败: {e}")
    finally:
        conn.close()

def get_pending_push_tasks(channel, limit=10):
    """获取尚未成功推送给指定渠道的新闻"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 子查询找出已成功推送的 ID，然后排除
        cursor.execute(f"""
            SELECT nr.* 
            FROM news_results nr
            WHERE nr.id NOT IN (
                SELECT news_id FROM push_logs WHERE channel = ? AND status = 'success'
            )
            ORDER BY nr.processed_at ASC
            LIMIT ?
        """, (channel, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("队列统计:", get_queue_stats())
