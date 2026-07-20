"""
时间规则引擎模块

模块结构:
- event_handler: 事件处理模块，查询事件发生时间
- inheritance: 继承解析器，处理规则继承和冲突
- evaluator: 规则评估器，计算 flag_time 和合规性
- engine: 主引擎入口
"""

from logic.time_rules.engine import TimeRuleEngine
from logic.time_rules.event_handler import EventHandler
from logic.time_rules.inheritance import InheritanceResolver
from logic.time_rules.evaluator import RuleEvaluator
from logic.time_rules.rule_manager import RuleManager
from logic.time_rules.actions import save_rule_action, delete_rule_action, persist_draft_rules_action
from logic.time_rules.queries import get_rules_for_entity, get_rule_by_id
from logic.time_rules.schemas import TimeRuleSchema

__all__ = [
    'TimeRuleEngine', 'EventHandler', 'InheritanceResolver', 
    'RuleEvaluator', 'RuleManager', 'save_rule_action', 
    'delete_rule_action', 'persist_draft_rules_action',
    'get_rules_for_entity', 'get_rule_by_id',
    'TimeRuleSchema'
]
