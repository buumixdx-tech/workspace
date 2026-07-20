"""
时间规则引擎主入口

职责：
1. 系统启动时自动运行
2. 手动触发运行
3. 生成告警报告
4. 提供规则 CRUD 操作
"""

from datetime import datetime
from typing import List, Optional

from models import get_session, TimeRule
from logic.constants import (
    TimeRuleStatus, TimeRuleWarning, TimeRuleRelatedType,
    TimeRuleInherit, EventType
)
from logic.time_rules.event_handler import EventHandler
from logic.time_rules.inheritance import InheritanceResolver
from logic.time_rules.evaluator import RuleEvaluator


class TimeRuleEngine:
    """
    时间规则引擎主入口
    
    提供规则引擎的核心功能：
    - 批量运行规则评估
    - 生成告警和违规报告
    - 规则 CRUD 操作
    - 与系统集成的接口
    """
    
    def __init__(self, session=None):
        self.session = session or get_session()
        self.event_handler = EventHandler(self.session)
        self.inheritance_resolver = InheritanceResolver(self.session)
        self.rule_evaluator = RuleEvaluator(self.session)
    
    def run(self, commit: bool = True) -> dict:
        """
        运行规则引擎 - 评估所有生效规则
        
        流程：
        1. 查询所有非失效状态的规则
        2. 逐条评估，更新状态
        3. 收集告警和违规
        4. 提交数据库更新
        
        Args:
            commit: 是否提交数据库更改
        
        Returns:
            {
                'processed': int,           # 处理规则数量
                'warnings': List[dict],     # 告警列表 (橙色/红色)
                'violations': List[dict],   # 违规列表
                'status_changes': List[dict], # 状态变更列表
                'all_warnings': List[dict]  # 所有告警（含黄色）
            }
        """
        result = {
            'processed': 0,
            'warnings': [],
            'violations': [],
            'status_changes': [],
            'all_warnings': []
        }
        
        # 获取所有需要处理的规则（跳过失效和模板状态）
        active_rules = self.session.query(TimeRule).filter(
            TimeRule.status.notin_(TimeRuleStatus.ENGINE_SKIP)
        ).all()
        
        for rule in active_rules:
            old_status = rule.status
            eval_result = self.rule_evaluator.evaluate_rule(rule)
            result['processed'] += 1
            
            # 记录状态变更
            if eval_result['new_status'] != old_status:
                rule.status = eval_result['new_status']
                
                # 记录时间戳
                if eval_result['new_status'] == TimeRuleStatus.HAS_RESULT:
                    rule.resultstamp = datetime.now()
                elif eval_result['new_status'] == TimeRuleStatus.ENDED:
                    rule.endstamp = datetime.now()
                
                result['status_changes'].append({
                    'rule_id': rule.id,
                    'related_type': rule.related_type,
                    'related_id': rule.related_id,
                    'from_status': old_status,
                    'to_status': eval_result['new_status']
                })
            
            # 收集告警
            warning_info = {
                'rule_id': rule.id,
                'related_type': rule.related_type,
                'related_id': rule.related_id,
                'target_event': rule.target_event,
                'flag_time': eval_result['flag_time'],
                'warning_level': eval_result['warning_level'],
                'party': rule.party,
                'direction': rule.direction
            }
            
            if eval_result['warning_level'] != TimeRuleWarning.GREEN:
                result['all_warnings'].append(warning_info)
            
            if eval_result['warning_level'] in [TimeRuleWarning.ORANGE, TimeRuleWarning.RED]:
                result['warnings'].append(warning_info)
            
            # 收集违规
            if eval_result['is_compliant'] is False:
                result['violations'].append({
                    'rule_id': rule.id,
                    'related_type': rule.related_type,
                    'related_id': rule.related_id,
                    'target_event': rule.target_event,
                    'target_time': eval_result['target_time'],
                    'flag_time': eval_result['flag_time'],
                    'party': rule.party,
                    'direction': rule.direction
                })
        
        if commit:
            self.session.commit()
        
        return result
    
    def evaluate_entity(self, related_type: str, related_id: int, 
                         commit: bool = True) -> dict:
        """
        评估指定实体的所有规则（含继承规则）
        
        Args:
            related_type: 关联对象类型
            related_id: 关联对象ID
            commit: 是否提交更改
        
        Returns:
            评估结果 (同 run 方法)
        """
        result = {
            'processed': 0,
            'warnings': [],
            'violations': [],
            'status_changes': [],
            'all_warnings': []
        }
        
        # 获取有效规则（含继承）
        effective_rules = self.inheritance_resolver.get_effective_rules(
            related_type, related_id
        )
        
        for rule in effective_rules:
            old_status = rule.status
            eval_result = self.rule_evaluator.evaluate_rule(rule)
            result['processed'] += 1
            
            # 只对数据库中的规则记录状态变更
            if rule.id is not None and eval_result['new_status'] != old_status:
                rule.status = eval_result['new_status']
                if eval_result['new_status'] == TimeRuleStatus.HAS_RESULT:
                    rule.resultstamp = datetime.now()
                elif eval_result['new_status'] == TimeRuleStatus.ENDED:
                    rule.endstamp = datetime.now()
                
                result['status_changes'].append({
                    'rule_id': rule.id,
                    'from_status': old_status,
                    'to_status': eval_result['new_status']
                })
            
            # 收集告警和违规（同上）
            if eval_result['warning_level'] in [TimeRuleWarning.ORANGE, TimeRuleWarning.RED]:
                result['warnings'].append({
                    'rule_id': rule.id,
                    'target_event': rule.target_event,
                    'flag_time': eval_result['flag_time'],
                    'warning_level': eval_result['warning_level'],
                    'party': rule.party
                })
            
            if eval_result['is_compliant'] is False:
                result['violations'].append({
                    'rule_id': rule.id,
                    'target_event': rule.target_event,
                    'flag_time': eval_result['flag_time'],
                    'party': rule.party
                })
        
        if commit:
            self.session.commit()
        
        return result
    
    def get_rules_for_entity(self, related_type: str, related_id: int, 
                              include_inherited: bool = True) -> List[TimeRule]:
        """
        获取实体的规则列表
        
        Args:
            related_type: 关联对象类型
            related_id: 关联对象ID
            include_inherited: 是否包含继承规则
        
        Returns:
            规则列表
        """
        if include_inherited:
            return self.inheritance_resolver.get_effective_rules(related_type, related_id)
        else:
            return self.session.query(TimeRule).filter(
                TimeRule.related_type == related_type,
                TimeRule.related_id == related_id,
                TimeRule.status.notin_(TimeRuleStatus.ENGINE_SKIP)
            ).all()
    
    def create_rule(self, related_type: str, related_id: int,
                     target_event: str, direction: str,
                     trigger_event: str = None,
                     tge_param1: str = None, tge_param2: str = None,
                     tae_param1: str = None, tae_param2: str = None,
                     offset: int = None, unit: str = None,
                     flag_time: datetime = None,
                     party: str = None,
                     inherit: int = 0) -> TimeRule:
        """
        创建新规则
        
        Args:
            related_type: 关联对象类型
            related_id: 关联对象ID
            target_event: 目标事件
            direction: 方向 (before/after)
            trigger_event: 触发事件 (使用 "绝对日期" 表示直接指定 flag_time)
            tge_param1, tge_param2: 触发事件参数
            tae_param1, tae_param2: 目标事件参数
            offset: 偏移量
            unit: 偏移量单位
            flag_time: 标杆时间 (绝对日期模式下直接指定)
            party: 责任方
            inherit: 继承等级 (0=自身定制)
        
        Returns:
            新创建的规则对象
        """
        # 验证：绝对日期模式必须提供 flag_time
        if trigger_event == EventType.Special.ABSOLUTE_DATE and not flag_time:
            raise ValueError("绝对日期模式必须提供 flag_time")
        
        rule = TimeRule(
            related_type=related_type,
            related_id=related_id,
            inherit=inherit,
            party=party,
            trigger_event=trigger_event,
            tge_param1=tge_param1,
            tge_param2=tge_param2,
            target_event=target_event,
            tae_param1=tae_param1,
            tae_param2=tae_param2,
            offset=offset,
            unit=unit,
            flag_time=flag_time,
            direction=direction,
            status=TimeRuleStatus.ACTIVE,
            warning=TimeRuleWarning.GREEN,
            timestamp=datetime.now()
        )
        
        # 检查冲突
        conflict = self.inheritance_resolver.check_conflict(rule)
        if conflict:
            # 如果新规则优先级更高，则使冲突规则失效
            if rule.inherit < conflict.inherit:
                conflict.status = TimeRuleStatus.INACTIVE
            else:
                raise ValueError(f"规则与现有规则冲突 (Rule ID: {conflict.id})")
        
        self.session.add(rule)
        self.session.commit()
        return rule
    
    def update_rule(self, rule_id: int, **kwargs) -> Optional[TimeRule]:
        """
        更新规则
        
        Args:
            rule_id: 规则ID
            **kwargs: 要更新的字段
        
        Returns:
            更新后的规则对象
        """
        rule = self.session.query(TimeRule).get(rule_id)
        if not rule:
            return None
        
        # 允许更新的字段
        allowed_fields = [
            'party', 'trigger_event', 'tge_param1', 'tge_param2',
            'target_event', 'tae_param1', 'tae_param2',
            'offset', 'unit', 'flag_time', 'direction', 'status'
        ]
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(rule, key, value)
        
        self.session.commit()
        return rule
    
    def delete_rule(self, rule_id: int) -> bool:
        """
        删除规则
        
        Args:
            rule_id: 规则ID
        
        Returns:
            是否成功删除
        """
        rule = self.session.query(TimeRule).get(rule_id)
        if not rule:
            return False
        
        self.session.delete(rule)
        self.session.commit()
        return True
    
    def toggle_rule_status(self, rule_id: int) -> Optional[TimeRule]:
        """
        切换规则状态 (生效 <-> 失效)
        
        Args:
            rule_id: 规则ID
        
        Returns:
            更新后的规则对象
        """
        rule = self.session.query(TimeRule).get(rule_id)
        if not rule:
            return None
        
        if rule.status == TimeRuleStatus.INACTIVE:
            rule.status = TimeRuleStatus.ACTIVE
        else:
            rule.status = TimeRuleStatus.INACTIVE
        
        self.session.commit()
        return rule
    
    def get_dashboard_summary(self) -> dict:
        """
        获取仪表盘汇总数据
        
        Returns:
            {
                'total_active': int,        # 生效规则总数
                'critical_count': int,      # 红色告警数量
                'urgent_count': int,        # 橙色告警数量
                'attention_count': int,     # 黄色告警数量
                'violation_count': int,     # 违规数量
                'warnings_by_type': dict,   # 按关联类型分组的告警
                'recent_violations': list   # 最近违规记录
            }
        """
        # 运行评估获取最新数据
        run_result = self.run(commit=True)
        
        # 按关联类型分组告警
        warnings_by_type = {}
        for w in run_result['all_warnings']:
            rt = w['related_type']
            if rt not in warnings_by_type:
                warnings_by_type[rt] = []
            warnings_by_type[rt].append(w)
        
        return {
            'total_active': run_result['processed'],
            'critical_count': len([w for w in run_result['all_warnings'] 
                                   if w['warning_level'] == TimeRuleWarning.RED]),
            'urgent_count': len([w for w in run_result['all_warnings'] 
                                 if w['warning_level'] == TimeRuleWarning.ORANGE]),
            'attention_count': len([w for w in run_result['all_warnings'] 
                                    if w['warning_level'] == TimeRuleWarning.YELLOW]),
            'violation_count': len(run_result['violations']),
            'warnings_by_type': warnings_by_type,
            'recent_violations': run_result['violations'][:10]  # 最近10条
        }


# =========================================================================
# 便捷函数 (供外部调用)
# =========================================================================

def run_time_rule_engine(session=None) -> dict:
    """运行时间规则引擎（便捷函数）"""
    engine = TimeRuleEngine(session)
    return engine.run()


def get_entity_warnings(related_type: str, related_id: int, session=None) -> List[dict]:
    """获取指定实体的告警列表（便捷函数）"""
    engine = TimeRuleEngine(session)
    result = engine.evaluate_entity(related_type, related_id)
    return result['all_warnings']
