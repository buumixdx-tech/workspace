import os
import toml
import pandas as pd
from typing import List, Dict, Optional
from market.ck_client import ClickHouseClient

class RealtimeAnalysisEngine:
    """
    Core engine for realtime stock analysis.
    Implements calculations based on user requirements and strategy configuration.
    """
    
    def __init__(self):
        self.ck = ClickHouseClient()
        # self.p1, self.p2, self.p3 are created dynamically
        self.last_concept_update_time = None # 记录板块名单上次更新的时间
        self.strategy_config = {}
        self._load_config()
        
    def _load_config(self):
        """加载或刷新策略配置"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml")
            with open(config_path, "r", encoding="utf-8") as f:
                full_config = toml.load(f)
                self.strategy_config = full_config.get("strategy", {})
        except Exception as e:
            print(f"Error loading strategy config: {e}")

    def get_latest_snapshot_time(self) -> Optional[str]:
        """获取最近一次个股快照的时间戳"""
        # 认为快照批次在 CK 中是时间对齐的，取最大值即可
        sql = "SELECT max(snapshot_time) as t FROM stock_snapshot_intraday"
        try:
            df = self.ck.query_df(sql)
            if not df.empty and df['t'].iloc[0]:
                return df['t'].iloc[0]
        except Exception:
            pass
        return None

    def calculate_lottery_stocks(self, hot_concept_names: List[str], snapshot_time) -> pd.DataFrame:
        """
        逻辑 1：热门板块里的冲板股票捕捉
        """
        if not hot_concept_names:
            return pd.DataFrame()
            
        names_str = "'" + "','".join(hot_concept_names) + "'"
        
        # 从配置读取阈值 (提供默认值以防配置文件缺失)
        l10_min = self.strategy_config.get("lottery_10cm_min", 7.0)
        l10_max = self.strategy_config.get("lottery_10cm_max", 9.8)
        l20_min = self.strategy_config.get("lottery_20cm_min", 15.0)
        l20_max = self.strategy_config.get("lottery_20cm_max", 19.9)
        
        # 兼容 10cm 和 20cm
        # 300xxx 和 688xxx 是 20cm，bj 是 30cm (暂未单独配置，可按需添加)
        # 这里主要逻辑区分主板 vs 双创
        sql = f"""
        SELECT 
            s.code, 
            s.name, 
            s.pct_chg, 
            s.price, 
            arrayStringConcat(groupArray(c.concept_name), ',') as source_concept,
            0 as reason_bits,
            '冲板捕捉' as strategy_type
        FROM view_concept_components_filtered c
        JOIN stock_snapshot_intraday s ON c.stock_code = s.code
        WHERE c.concept_name IN ({names_str})
          AND s.snapshot_time = '{snapshot_time}'
          AND (
            ((s.code LIKE 'sz.3%' OR s.code LIKE 'sh.68%') AND s.pct_chg >= {l20_min} AND s.pct_chg < {l20_max})
            OR
            (s.code NOT LIKE 'sz.3%' AND s.code NOT LIKE 'sh.68%' AND s.pct_chg >= {l10_min} AND s.pct_chg < {l10_max})
          )
          AND s.is_suspended = 0
          AND s.name NOT LIKE '%ST%'
        GROUP BY s.code, s.name, s.pct_chg, s.price
        ORDER BY pct_chg DESC
        """
        return self.ck.query_df(sql)

    def calculate_knowledge_matches(self, hot_concept_names: List[str], snapshot_time) -> pd.DataFrame:
        """
        逻辑 2：基于离线 AI 知识库匹配。
        """
        if not hot_concept_names:
            return pd.DataFrame()

        names_str = "'" + "','".join(hot_concept_names) + "'"
        
        # 关联知识库与实时行情
        sql = f"""
        SELECT 
            k.stock_code as code, 
            any(k.stock_name) as name, 
            any(s.pct_chg) as pct_chg, 
            any(s.price) as price,
            any(k.concept_name) as matched_concept,
            0 as reason_bits,
            'AI知识库匹配' as strategy_type
        FROM analysis_hot_topic_mapping k
        JOIN stock_snapshot_intraday s ON k.stock_code = s.code
        WHERE k.concept_name IN ({names_str})
          AND s.snapshot_time = '{snapshot_time}'
          AND s.pct_chg > 0
          AND s.is_suspended = 0
        GROUP BY k.stock_code
        ORDER BY pct_chg DESC
        """
        return self.ck.query_df(sql)

    def generate_recommendation(self) -> Optional[Dict]:
        """
        主调度：基于三级动态池逻辑产出推荐
        
        Pool 1: Limit Up >= 3
        Pool 2: Pool 1 & Pct Chg > 3.5%
        Pool 3: Pool 2 & Pct Chg > 5.0%
        """
        # 每次运行前刷新配置，支持热更新
        self._load_config()
        
        snap_time = self.get_latest_snapshot_time()
        if not snap_time:
            return None
            
        # 1. 维护“热门板块”名单缓存
        concept_snap_df = self.ck.query_df("SELECT max(snapshot_time) as t FROM concept_snapshot_intraday")
        latest_concept_time = concept_snap_df['t'].iloc[0] if not concept_snap_df.empty else None
        
        # 即使时间没变，也重新计算一次池子，因为可能配置变了或者需要重新触发
        # 但为了效率，最好 check 时间。这里沿用原逻辑：如果有新数据才计算
        if latest_concept_time and latest_concept_time != self.last_concept_update_time:
            self.last_concept_update_time = latest_concept_time
            
            # Base Query: Limit Up >= P1 Threshold
            p1_lu_min = self.strategy_config.get("pool1_limit_up_min", 3)
            p2_pct_min = self.strategy_config.get("pool2_pct_min", 3.5)
            p3_pct_min = self.strategy_config.get("pool3_pct_min", 5.0)

            base_sql = f"""
                SELECT concept_name, 
                       pct_chg, 
                       limit_up_count, 
                       stock_count
                FROM concept_snapshot_intraday 
                WHERE snapshot_time = '{latest_concept_time}'
                  AND limit_up_count >= {p1_lu_min}
                ORDER BY pct_chg DESC
            """
            base_df = self.ck.query_df(base_sql)
            
            # Pool 1: Limit Up >= N
            self.p1 = base_df
            
            # Pool 2: P1 + Pct > X
            self.p2 = base_df[base_df['pct_chg'] > p2_pct_min] if not base_df.empty else pd.DataFrame()
            
            # Pool 3: P2 + Pct > Y
            self.p3 = self.p2[self.p2['pct_chg'] > p3_pct_min] if not self.p2.empty else pd.DataFrame()
            
        # 如果还在初始化阶段，没有数据
        if not hasattr(self, 'p1') or self.p1.empty:
            return None

        # 准备扫描名单：所有涉及的板块合集 (其实就是 P1 的所有名字)
        hot_concept_names = self.p1['concept_name'].tolist()
        
        # 2. 执行逻辑 A：热门板块内冲板股
        lottery_stocks = self.calculate_lottery_stocks(hot_concept_names, snap_time)
        
        # 3. 执行逻辑 B：AI 知识库与当前热门板块的共振小票
        knowledge_matches = self.calculate_knowledge_matches(hot_concept_names, snap_time)
        
        # --- 交叉去重与归类 ---
        lottery_list = lottery_stocks.to_dict('records') if not lottery_stocks.empty else []
        knowledge_list = knowledge_matches.to_dict('records') if not knowledge_matches.empty else []
        
        final_lottery_pool, final_small_cap_pool = self._deduplicate_pools(lottery_list, knowledge_list)
        
        return {
            'timestamp': snap_time,
            'pool_1': self.p1.to_dict('records'),
            'pool_2': self.p2.to_dict('records'),
            'pool_3': self.p3.to_dict('records'),
            'lottery_pool': final_lottery_pool,
            'small_cap_pool': final_small_cap_pool
        }

    def _deduplicate_pools(self, lottery_list: List[Dict], knowledge_list: List[Dict]) -> tuple:
        """
        核心清洗逻辑：处理冲板池与小票池的交叉
        规则：如果一个票既是小票池匹配的，又是热门板块冲板的，归于 small_cap_pool
        """
        # 建立索引
        knowledge_map = {s['code']: s for s in knowledge_list}
        lottery_map = {s['code']: s for s in lottery_list}
        
        common_codes = set(lottery_map.keys()) & set(knowledge_map.keys())
        
        final_lottery_pool = []
        
        for s in lottery_list:
            if s['code'] in common_codes:
                # 命中交叉：合并信息到小票池对象中
                k_item = knowledge_map[s['code']]
                
                # 1. 标记它是冲板股
                k_item['_is_surging'] = True
                
                # 2. 合并并去重板块标签
                # 目标：如果 matched_concept 里的板块已经在 source_concept 里有了，就去掉
                sc_set = set(s.get('source_concept', '').split(',')) if s.get('source_concept') else set()
                mc_set = set(k_item.get('matched_concept', '').split(',')) if k_item.get('matched_concept') else set()
                
                # 从 matched 中剔除已在 source 中出现的
                final_mc = mc_set - sc_set
                k_item['matched_concept'] = ','.join(final_mc)
                
                # 3. 合并 source_concept (直连板块)
                if s.get('source_concept'):
                    orig = k_item.get('source_concept', '')
                    new_val = s['source_concept']
                    k_item['source_concept'] = (orig + ',' + new_val).strip(',') if orig else new_val

                # 4. 合并 reason_bits
                rb_l = int(s.get('reason_bits', 0) or 0)
                rb_k = int(k_item.get('reason_bits', 0) or 0)
                k_item['reason_bits'] = rb_l | rb_k
                
            else:
                # 非交叉：保留在冲板池
                final_lottery_pool.append(s)
                
        # 小票池列表 (包含已被原地修改的重合项)
        final_small_cap_pool = list(knowledge_map.values())
        
        return final_lottery_pool, final_small_cap_pool

if __name__ == "__main__":
    # Test entry point
    engine = RealtimeAnalysisEngine()
    res = engine.generate_recommendation()
    if res:
        l_count = len(res.get('lottery_pool', []))
        k_count = len(res.get('small_cap_pool', []))
        print(f"[{res['timestamp']}] 推荐池生成: 冲板 {l_count} 只 | AI知识匹配 {k_count} 只")
