-- ============================================================================
-- Migration 004: 删除废弃的 LightRAG 推送状态列
--
-- Context:
--   feishu_ext 已不再向 LightRAG 推送，post_to_lightrag / post_track_id / posted_at
--   三个字段已无任何代码引用（纯历史遗留死列）。
--   extracted 表当前 schema（feishu_db_writer.py）已不包含这三列，
--   生产库存在是因为 CREATE TABLE IF NOT EXISTS 不会重建已有表。
--
-- Owner: feishu_preprocess
--
-- Applied: 2026-07-03
--
-- Prerequisite: SQLite ≥ 3.35.0 (ALTER TABLE DROP COLUMN 要求)
--   验证方法: sqlite3 --version
-- ============================================================================

-- 注意：SQLite 3.35+ 支持 DROP COLUMN，但不认 IF EXISTS 子句。
-- 验证列存在再删（避免重跑报错）
ALTER TABLE extracted DROP COLUMN posted_to_lightrag;
ALTER TABLE extracted DROP COLUMN post_track_id;
ALTER TABLE extracted DROP COLUMN posted_at;
