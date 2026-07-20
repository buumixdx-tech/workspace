import os
import pandas as pd
from datetime import datetime
from market.ck_client import ClickHouseClient

class TopicKnowledgeManager:
    """
    知识库管理工具：负责将 stock_analysis 模块生成的 AI 分析结果 (Excel) 
    导入到 ClickHouse 的 analysis_hot_topic_mapping 表中，
    供实时监控系统 (monitor_service) 进行行情撞击匹配。
    """
    
    def __init__(self):
        self.ck = ClickHouseClient()
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.default_excel_path = os.path.join(self.project_root, "data", "stock_analysis", "result.xlsx")

    def sync_from_excel(self, file_path=None):
        """
        从 Excel 同步 AI 分析结果到数据库
        """
        if file_path is None:
            file_path = self.default_excel_path
            
        if not os.path.exists(file_path):
            print(f"❌ 错误: 未找到分析结果文件: {file_path}")
            return False
            
        print(f"🔄 正在从 {file_path} 同步知识库...")
        
        try:
            # 读取 Excel (默认第一个 Sheet: Analysis)
            df = pd.read_excel(file_path)
            
            if df.empty:
                print("⚠️ Excel 文件为空，跳过同步。")
                return False
                
            # 字段映射与数据清洗
            # Excel 字段: [股票代码, 股票名称, 总市值, 流通市值, 关联热点, 挂钩方式, 信息来源, 关联描述]
            # DB 字段: [topic_name, stock_code, stock_name, reason, update_time]
            
            sync_data = []
            for _, row in df.iterrows():
                topic = str(row.get("关联热点", "")).strip()
                code = str(row.get("股票代码", "")).strip()
                name = str(row.get("股票名称", "")).strip()
                
                method = str(row.get("挂钩方式", "")).strip()
                desc = str(row.get("关联描述", "")).strip()
                # 拼接理由
                reason = f"[{method}] {desc}" if method else desc
                
                if not topic or not code:
                    continue
                    
                sync_data.append({
                    "concept_name": topic,
                    "stock_code": code,
                    "stock_name": name,
                    "reason": reason,
                    "update_time": datetime.now()
                })
            
            if not sync_data:
                print("⚠️ 没有解析到有效的关联数据。")
                return False
                
            # 写入数据库 (ReplacingMergeTree 会根据 (concept_name, stock_code) 自动更新)
            df_sync = pd.DataFrame(sync_data)
            self.ck.insert_df("analysis_hot_topic_mapping", df_sync)
            
            print(f"✅ 同步成功！已导入 {len(df_sync)} 条个股-概念关联知识。")
            return True
            
        except Exception as e:
            print(f"❌ 同步过程中出错: {e}")
            return False
        finally:
            self.ck.close()

    def clear_knowledge(self):
        """清空知识库"""
        self.ck.command("TRUNCATE TABLE analysis_hot_topic_mapping")
        print("🗑️ 知识库已清空。")

if __name__ == "__main__":
    # 手动执行同步
    manager = TopicKnowledgeManager()
    manager.sync_from_excel()
