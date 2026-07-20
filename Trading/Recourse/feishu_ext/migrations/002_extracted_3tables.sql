-- ============================================================================
-- Migration 002: extracted 3-table schema
--
-- Context:
--   feishu_sync 完全不感知 extracted 系列表(store.py 里所有相关代码已删除).
--   feishu_preprocess 拥有这三张表的全部生命周期.
--
-- Owner: feishu_preprocess (NOT feishu_sync, NOT feishu_search)
--
-- Applied: 2026-06-19 (jcloud + local demo)
-- ============================================================================

-- 主表:每条 LLM 抽取过的消息 1 行
CREATE TABLE IF NOT EXISTS extracted (
    msg_rowid          INTEGER PRIMARY KEY,                  -- = messages.rowid (1:1 锚定)
    ts                 INTEGER NOT NULL,                      -- 副本(范围查询/ORDER BY)
    info_type          TEXT    NOT NULL,                      -- 10 类之一
    category           TEXT    NOT NULL DEFAULT '',           -- 行业/细分赛道
    summary            TEXT    NOT NULL DEFAULT '',           -- ≤30 字
    source_run_id      TEXT,                                  -- 哪次 pipeline 跑的
    posted_to_lightrag INTEGER NOT NULL DEFAULT 0,            -- 0/1
    post_track_id      TEXT,                                  -- lightrag track_id
    posted_at          TEXT,                                  -- POST 成功时间
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_extracted_ts ON extracted(ts);

-- M:N:股票
CREATE TABLE IF NOT EXISTS extracted_stocks (
    msg_rowid INTEGER NOT NULL,
    stock     TEXT    NOT NULL,
    PRIMARY KEY (msg_rowid, stock)
);
CREATE INDEX IF NOT EXISTS idx_stocks_stock ON extracted_stocks(stock);

-- M:N:概念/技术术语
CREATE TABLE IF NOT EXISTS extracted_terms (
    msg_rowid INTEGER NOT NULL,
    term      TEXT    NOT NULL,
    PRIMARY KEY (msg_rowid, term)
);
CREATE INDEX IF NOT EXISTS idx_terms_term ON extracted_terms(term);