"""
继承解析器模块

职责：
1. 解析规则继承关系
2. 检测规则冲突
3. 返回有效规则集合
"""

from typing import List, Optional

from models import get_session, TimeRule, VirtualContract, Logistics
from logic.constants import (
    TimeRuleRelatedType, TimeRuleInherit, TimeRuleStatus
)


class InheritanceResolver:
    """
    规则继承解析器
    
    继承关系层级:
    - 第一层: 业务 / 供应链
    - 第二层: 虚拟合同 (从业务或供应链继承)
    - 第三层: 物流 (从虚拟合同、业务或供应链继承)
    
    继承优先级 (inherit 字段):
    - 0: 自身定制 (最高优先级)
    - 1: 近继承 (如 VC 从 Business 继承)
    - 2: 远继承 (如 Logistics 从 Business 穿透继承)
    """
    
    def __init__(self, session=None):
        self.session = session or get_session()
    
    def get_effective_rules(self, related_type: str, related_id: int) -> List[TimeRule]:
        """
        获取对象的有效规则集合 (含继承规则，已去冲突)
        
        Args:
            related_type: 关联对象类型
            related_id: 关联对象ID
        
        Returns:
            去重和冲突解决后的有效规则列表
        """
        all_rules = []
        
        # Step 1: 获取自身定制规则
        self_rules = self._get_self_rules(related_type, related_id)
        all_rules.extend(self_rules)
        
        # Step 2: 获取继承规则
        inherited_rules = self._get_inherited_rules(related_type, related_id)
        all_rules.extend(inherited_rules)
        
        # Step 3: 冲突检测与解决
        return self._resolve_conflicts(all_rules)
    
    def _get_self_rules(self, related_type: str, related_id: int) -> List[TimeRule]:
        """获取对象自身的定制规则 (inherit=0)"""
        return self.session.query(TimeRule).filter(
            TimeRule.related_type == related_type,
            TimeRule.related_id == related_id,
            TimeRule.inherit == TimeRuleInherit.SELF,
            TimeRule.status != TimeRuleStatus.INACTIVE  # 只要不是失效就可以（包含模板和生效）
        ).all()
    
    def _get_inherited_rules(self, related_type: str, related_id: int) -> List[TimeRule]:
        """
        获取继承的规则
        
        根据关联类型，向上溯源获取继承规则
        """
        inherited = []
        
        if related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            inherited = self._get_vc_inherited_rules(related_id)
        elif related_type == TimeRuleRelatedType.LOGISTICS:
            inherited = self._get_logistics_inherited_rules(related_id)
        # Business 和 SupplyChain 位于顶层，不继承其他规则
        
        return inherited
    
    def _get_vc_inherited_rules(self, vc_id: int) -> List[TimeRule]:
        """获取虚拟合同的继承规则"""
        inherited = []
        vc = self.session.query(VirtualContract).get(vc_id)
        if not vc:
            return inherited
        
        # 从业务继承
        if vc.business_id:
            biz_rules = self._get_rules_targeting_type(
                TimeRuleRelatedType.BUSINESS,
                vc.business_id,
                target_type=TimeRuleRelatedType.VIRTUAL_CONTRACT
            )
            for rule in biz_rules:
                # 创建一个克隆规则，重新设置关联信息
                inherited.append(self._create_inherited_rule(
                    rule, vc_id, TimeRuleRelatedType.VIRTUAL_CONTRACT, TimeRuleInherit.NEAR
                ))
        
        # 从供应链继承
        if vc.supply_chain_id:
            sc_rules = self._get_rules_targeting_type(
                TimeRuleRelatedType.SUPPLY_CHAIN,
                vc.supply_chain_id,
                target_type=TimeRuleRelatedType.VIRTUAL_CONTRACT
            )
            for rule in sc_rules:
                inherited.append(self._create_inherited_rule(
                    rule, vc_id, TimeRuleRelatedType.VIRTUAL_CONTRACT, TimeRuleInherit.NEAR
                ))
        
        return inherited
    
    def _get_logistics_inherited_rules(self, logistics_id: int) -> List[TimeRule]:
        """获取物流的继承规则"""
        inherited = []
        logistics = self.session.query(Logistics).get(logistics_id)
        if not logistics or not logistics.virtual_contract_id:
            return inherited
        
        vc = self.session.query(VirtualContract).get(logistics.virtual_contract_id)
        if not vc:
            return inherited
        
        # 从虚拟合同继承 (近继承)
        vc_rules = self._get_rules_targeting_type(
            TimeRuleRelatedType.VIRTUAL_CONTRACT,
            vc.id,
            target_type=TimeRuleRelatedType.LOGISTICS
        )
        for rule in vc_rules:
            inherited.append(self._create_inherited_rule(
                rule, logistics_id, TimeRuleRelatedType.LOGISTICS, TimeRuleInherit.NEAR
            ))
        
        # 从业务穿透继承 (远继承)
        if vc.business_id:
            biz_rules = self._get_rules_targeting_type(
                TimeRuleRelatedType.BUSINESS,
                vc.business_id,
                target_type=TimeRuleRelatedType.LOGISTICS
            )
            for rule in biz_rules:
                inherited.append(self._create_inherited_rule(
                    rule, logistics_id, TimeRuleRelatedType.LOGISTICS, TimeRuleInherit.FAR
                ))
        
        # 从供应链穿透继承 (远继承)
        if vc.supply_chain_id:
            sc_rules = self._get_rules_targeting_type(
                TimeRuleRelatedType.SUPPLY_CHAIN,
                vc.supply_chain_id,
                target_type=TimeRuleRelatedType.LOGISTICS
            )
            for rule in sc_rules:
                inherited.append(self._create_inherited_rule(
                    rule, logistics_id, TimeRuleRelatedType.LOGISTICS, TimeRuleInherit.FAR
                ))
        
        return inherited
    
    def _get_rules_targeting_type(self, source_type: str, source_id: int, 
                                   target_type: str) -> List[TimeRule]:
        """
        获取某个来源对象针对特定目标类型制定的规则
        
        逻辑：通过 source_type 和 target_type 的层级差来确定需要的 inherit 级别
        - Business -> VC: NEAR (1)
        - Business -> Logistics: FAR (2)
        - SupplyChain -> VC: NEAR (1)
        - SupplyChain -> Logistics: FAR (2)
        - VC -> Logistics: NEAR (1)
        """
        # 确定层级关系
        target_inherit = None
        
        if source_type in [TimeRuleRelatedType.BUSINESS, TimeRuleRelatedType.SUPPLY_CHAIN]:
            if target_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
                target_inherit = TimeRuleInherit.NEAR
            elif target_type == TimeRuleRelatedType.LOGISTICS:
                target_inherit = TimeRuleInherit.FAR
        elif source_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            if target_type == TimeRuleRelatedType.LOGISTICS:
                target_inherit = TimeRuleInherit.NEAR
        
        if target_inherit is None:
            return []

        return self.session.query(TimeRule).filter(
            TimeRule.related_type == source_type,
            TimeRule.related_id == source_id,
            TimeRule.inherit == target_inherit,
            TimeRule.status != TimeRuleStatus.INACTIVE
        ).all()
    
    def _create_inherited_rule(self, source_rule: TimeRule, new_related_id: int,
                                new_related_type: str, inherit_level: int) -> TimeRule:
        """
        基于源规则创建继承规则（内存对象，不持久化）
        
        注意：这个方法创建的是临时对象，用于运行时计算
        真正的继承规则是动态解析的，而不是存储在数据库中
        """
        # 创建一个新的规则对象（不添加到 session）
        inherited = TimeRule(
            related_id=new_related_id,
            related_type=new_related_type,
            inherit=inherit_level,
            party=source_rule.party,
            trigger_event=source_rule.trigger_event,
            tge_param1=source_rule.tge_param1,
            tge_param2=source_rule.tge_param2,
            target_event=source_rule.target_event,
            tae_param1=source_rule.tae_param1,
            tae_param2=source_rule.tae_param2,
            offset=source_rule.offset,
            unit=source_rule.unit,
            flag_time=source_rule.flag_time,
            direction=source_rule.direction,
            status=TimeRuleStatus.ACTIVE  # 继承后的规则在实例层级生效
        )
        # 标记来源规则 ID (用于调试/展示)
        inherited._source_rule_id = source_rule.id
        return inherited
    
    def _resolve_conflicts(self, rules: List[TimeRule]) -> List[TimeRule]:
        """
        解决规则冲突
        
        冲突定义：触发事件相同 + 目标事件相同
        解决策略：保留 inherit 值最小的 (优先级最高)
        
        Args:
            rules: 所有规则列表（含自身和继承）
        
        Returns:
            去冲突后的有效规则列表
        """
        # 按 (trigger_event, target_event) 分组
        groups = {}
        for rule in rules:
            key = (rule.trigger_event, rule.target_event)
            if key not in groups:
                groups[key] = []
            groups[key].append(rule)
        
        effective_rules = []
        for key, group_rules in groups.items():
            if len(group_rules) == 1:
                effective_rules.append(group_rules[0])
            else:
                # 按优先级排序 (inherit 值越小优先级越高)
                sorted_rules = sorted(group_rules, key=lambda r: r.inherit)
                winner = sorted_rules[0]
                effective_rules.append(winner)
                
                # 标记被覆盖的规则 (仅对数据库中的规则进行标记)
                for loser in sorted_rules[1:]:
                    if loser.id is not None:  # 有 ID 说明是数据库记录
                        loser.status = TimeRuleStatus.INACTIVE
        
        return effective_rules
    
    def check_conflict(self, new_rule: TimeRule, existing_rules: List[TimeRule] = None) -> Optional[TimeRule]:
        """
        检查新规则是否与现有规则冲突
        
        Args:
            new_rule: 待检查的新规则
            existing_rules: 现有规则列表（不传则从数据库查询）
        
        Returns:
            冲突的规则，无冲突返回 None
        """
        if existing_rules is None:
            existing_rules = self.get_effective_rules(
                new_rule.related_type, new_rule.related_id
            )
        
        for rule in existing_rules:
            if (rule.trigger_event == new_rule.trigger_event and 
                rule.target_event == new_rule.target_event and
                rule.id != new_rule.id):
                return rule
        return None
