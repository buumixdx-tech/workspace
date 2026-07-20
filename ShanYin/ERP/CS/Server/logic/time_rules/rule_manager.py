"""
规则管理器：负责处理规则的层级分发、同步与自动生成
"""
from models import get_session, Business, SupplyChain, VirtualContract, Logistics, TimeRule
from logic.constants import (
    TimeRuleRelatedType, TimeRuleInherit, TimeRuleStatus, 
    TimeRuleDirection, TimeRuleOffsetUnit, EventType, TimeRuleParty
)

class RuleManager:
    """
    负责规则的物理生成。
    当父级对象创建或更新时，或者子级对象创建时，自动维护 TimeRule 表中的记录。
    """
    
    def __init__(self, session=None):
        self.session = session or get_session()

    def sync_from_parent(self, child_type: str, child_id: int):
        """
        核心方法：当创建一个子实体(如VC或物流)时，从父级同步规则。
        """
        if child_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            self._sync_vc_from_parent(child_id)
        elif child_type == TimeRuleRelatedType.LOGISTICS:
            self._sync_logistics_from_parent(child_id)

    def propagate_from_parent(self, parent_type: str, parent_id: int):
        """
        向下传播：当父级(Business/SupplyChain/VC)的模板规则改变时，同步更新所有子级的实例规则。
        """
        if parent_type in [TimeRuleRelatedType.BUSINESS, TimeRuleRelatedType.SUPPLY_CHAIN]:
            vcs = self.session.query(VirtualContract).filter(
                (VirtualContract.business_id == parent_id) if parent_type == TimeRuleRelatedType.BUSINESS 
                else (VirtualContract.supply_chain_id == parent_id)
            ).all()
            for vc in vcs:
                self._sync_vc_from_parent(vc.id)
        
        elif parent_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            logs = self.session.query(Logistics).filter(Logistics.virtual_contract_id == parent_id).all()
            for log in logs:
                self._sync_logistics_from_parent(log.id)

    def _sync_vc_from_parent(self, vc_id: int):
        """从所属的 Business 或 SupplyChain 物理同步模板规则"""
        vc = self.session.query(VirtualContract).get(vc_id)
        if not vc: return

        # 1. 查找父级
        parents = []
        if vc.business_id:
            parents.append((TimeRuleRelatedType.BUSINESS, vc.business_id))
        if vc.supply_chain_id:
            parents.append((TimeRuleRelatedType.SUPPLY_CHAIN, vc.supply_chain_id))
        
        for p_type, p_id in parents:
            # 查找该父级下所有针对 VC 的模板规则 (inherit=NEAR)
            templates = self.session.query(TimeRule).filter(
                TimeRule.related_type == p_type,
                TimeRule.related_id == p_id,
                TimeRule.inherit == TimeRuleInherit.NEAR,
                TimeRule.status == TimeRuleStatus.TEMPLATE
            ).all()
            
            for tmpl in templates:
                self._upsert_child_rule(tmpl, vc_id, TimeRuleRelatedType.VIRTUAL_CONTRACT)

    def _sync_logistics_from_parent(self, logistics_id: int):
        """从所属的 VC 物理同步模板规则"""
        log = self.session.query(Logistics).get(logistics_id)
        if not log or not log.virtual_contract_id: return
        
        vc = self.session.query(VirtualContract).get(log.virtual_contract_id)
        if not vc: return

        # 1. 直接来自 VC 的模板 (inherit=NEAR)
        vc_templates = self.session.query(TimeRule).filter(
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.related_id == vc.id,
            TimeRule.inherit == TimeRuleInherit.NEAR,
            TimeRule.status == TimeRuleStatus.TEMPLATE
        ).all()
        
        # 2. 穿透来自 Business/SupplyChain 的模板 (inherit=FAR)
        grandparents = []
        if vc.business_id: grandparents.append((TimeRuleRelatedType.BUSINESS, vc.business_id))
        if vc.supply_chain_id: grandparents.append((TimeRuleRelatedType.SUPPLY_CHAIN, vc.supply_chain_id))
        
        for gp_type, gp_id in grandparents:
            gp_templates = self.session.query(TimeRule).filter(
                TimeRule.related_type == gp_type,
                TimeRule.related_id == gp_id,
                TimeRule.inherit == TimeRuleInherit.FAR,
                TimeRule.status == TimeRuleStatus.TEMPLATE
            ).all()
            vc_templates.extend(gp_templates)

        for tmpl in vc_templates:
            self._upsert_child_rule(tmpl, logistics_id, TimeRuleRelatedType.LOGISTICS)

    def _upsert_child_rule(self, template: TimeRule, child_id: int, child_type: str):
        """根据模板物理更新或创建子规则条目"""
        # 查找现有的子规则（基于触发和目标事件匹配）
        # 继承来的规则子级 inherit 保持不变，但 status 变为 ACTIVE
        existing = self.session.query(TimeRule).filter(
            TimeRule.related_type == child_type,
            TimeRule.related_id == child_id,
            TimeRule.trigger_event == template.trigger_event,
            TimeRule.target_event == template.target_event,
            TimeRule.inherit == template.inherit  # 匹配继承深度
        ).first()

        if not existing:
            existing = TimeRule(
                related_id=child_id,
                related_type=child_type,
                inherit=template.inherit,
                trigger_event=template.trigger_event,
                target_event=template.target_event,
                status=TimeRuleStatus.ACTIVE  # 实例层级转为激活
            )
            self.session.add(existing)

        # 同步其余字段
        existing.party = template.party
        existing.tge_param1 = template.tge_param1
        existing.tge_param2 = template.tge_param2
        existing.tae_param1 = template.tae_param1
        existing.tae_param2 = template.tae_param2
        existing.offset = template.offset
        existing.unit = template.unit
        existing.direction = template.direction
        # flag_time 不同步，由引擎在子级独立计算
        
        self.session.flush()

    def _map_trigger_name(self, name):
        """翻译 UI 描述或常量到内部事件 ID"""
        from logic.constants import SettlementRule # 延时导入避免循环
        
        mapping = {
            # 文字描述
            "入库日": EventType.VCLevel.SUBJECT_SIGNED,
            "发货日": EventType.VCLevel.SUBJECT_SHIPPED,
            "合同签订日": EventType.ContractLevel.CONTRACT_SIGNED,
            "发货": EventType.VCLevel.SUBJECT_SHIPPED,
            "签收": EventType.VCLevel.SUBJECT_SIGNED,
            
            # 常量映射
            SettlementRule.TRIGGER_INBOUND: EventType.VCLevel.SUBJECT_SIGNED,
            SettlementRule.TRIGGER_SHIPPED: EventType.VCLevel.SUBJECT_SHIPPED
        }
        return mapping.get(name)

    def generate_rules_from_payment_terms(
        self,
        related_id: int,
        related_type: str,
        payment_terms: dict,
        entity_type: str,  # TimeRuleRelatedType.BUSINESS 或 TimeRuleRelatedType.SUPPLY_CHAIN
        party: str = None
    ) -> int:
        """
        根据结算条款自动生成时间规则

        规则生成逻辑：
          3.2  预付比例 > 0 → 生成预付约束规则：
                 CASH_PREPAID → SUBJECT_SHIPPED (direction=AFTER, offset=0)
          3.3  生成结算规则：
                 SUBJECT_FINISH → SUBJECT_CASH_FINISH (direction=BEFORE, offset=账期天数)

        字段赋值规范：
          - tae_param1：所有自动生成的规则统一赋值为 "付款条款生成"，tae_param2 固定为 None
          - 规则1（预付约束）：tge_param1 = 纯百分数字符串（如 "40%"），供规则引擎数值计算
          - 规则2（结算规则）：tge_param1 = None，账期天数承载于 offset 字段

        Args:
            related_id: 关联对象 ID
            related_type: 关联类型 (TimeRuleRelatedType.BUSINESS 或 SUPPLY_CHAIN)
            payment_terms: 结算条款字典，包含:
                - prepayment_ratio: 预付款比例 (0-1)
                - balance_period: 尾款账期 (天)
                - day_rule: 计日规则 (自然日/工作日)
                - start_trigger: 起算锚点 (入库/发货)
            entity_type: 实体类型，用 TimeRuleRelatedType.BUSINESS / SUPPLY_CHAIN
            party: 责任方（默认自动判断：business→客户，supply_chain→我方）

        Returns:
            int: 生成的规则数量
        """
        from logic.constants import SettlementRule

        if not payment_terms:
            return 0

        # VC 和 Logistics 不通过付款条款生成规则
        if entity_type in (TimeRuleRelatedType.VIRTUAL_CONTRACT, TimeRuleRelatedType.LOGISTICS):
            return 0

        # 责任方：business→客户，supply_chain→我方
        if party is None:
            party = TimeRuleParty.CUSTOMER if entity_type == TimeRuleRelatedType.BUSINESS else TimeRuleParty.OURSELVES

        prepay_ratio = payment_terms.get("prepayment_ratio", 0)
        balance_days = payment_terms.get("balance_period", 30)
        day_rule_str = payment_terms.get("day_rule", SettlementRule.NATURAL_DAY)

        # 计日规则
        unit = TimeRuleOffsetUnit.WORK_DAY if day_rule_str == SettlementRule.WORK_DAY else TimeRuleOffsetUnit.NATURAL_DAY

        # 结算规则 trigger：入库 → SUBJECT_FINISH
        trigger_event = EventType.VCLevel.SUBJECT_FINISH

        rules_created = 0

        # 3.2 预付比例 > 0 → 生成预付约束 (CASH_PREPAID → SUBJECT_SHIPPED)
        if prepay_ratio and prepay_ratio > 0:
            existing_prepay = self.session.query(TimeRule).filter(
                TimeRule.related_id == related_id,
                TimeRule.related_type == related_type,
                TimeRule.trigger_event == EventType.VCLevel.CASH_PREPAID,
                TimeRule.target_event == EventType.VCLevel.SUBJECT_SHIPPED
            ).first()
            if not existing_prepay:
                self.session.add(TimeRule(
                    related_id=related_id,
                    related_type=related_type,
                    inherit=TimeRuleInherit.NEAR,
                    party=TimeRuleParty.OURSELVES,  # 我方发货，受预付约束
                    trigger_event=EventType.VCLevel.CASH_PREPAID,
                    tge_param1=f"{int(prepay_ratio * 100)}%",  # 纯百分数字符串，供规则引擎计算
                    tge_param2=None,
                    target_event=EventType.VCLevel.SUBJECT_SHIPPED,
                    tae_param1="付款条款生成",
                    tae_param2=None,
                    offset=0,
                    unit=unit,
                    direction=TimeRuleDirection.AFTER,
                    status=TimeRuleStatus.TEMPLATE
                ))
                rules_created += 1

        # 3.3 结算规则 (SUBJECT_FINISH → SUBJECT_CASH_FINISH, direction=BEFORE)
        existing_balance = self.session.query(TimeRule).filter(
            TimeRule.related_id == related_id,
            TimeRule.related_type == related_type,
            TimeRule.target_event == EventType.VCLevel.SUBJECT_CASH_FINISH,
            TimeRule.inherit == TimeRuleInherit.NEAR
        ).first()

        if not existing_balance:
            self.session.add(TimeRule(
                related_id=related_id,
                related_type=related_type,
                inherit=TimeRuleInherit.NEAR,
                party=party,
                trigger_event=trigger_event,
                tge_param1=None,  # 账期时长在 offset 中体现
                tge_param2=None,
                target_event=EventType.VCLevel.SUBJECT_CASH_FINISH,
                tae_param1="付款条款生成",
                tae_param2=None,
                offset=balance_days,
                unit=unit,
                direction=TimeRuleDirection.BEFORE,
                status=TimeRuleStatus.TEMPLATE
            ))
            rules_created += 1

        if rules_created > 0:
            self.session.flush()

        return rules_created

    def save_template_rules(
        self,
        related_id: int,
        related_type: str,
        rules: list
    ) -> int:
        """
        保存用户定义的初始模板规则

        Args:
            related_id: 关联对象 ID
            related_type: 关联类型 (TimeRuleRelatedType.SUPPLY_CHAIN 等)
            rules: 规则列表，每条规则包含:
                - party: 责任方
                - trigger_event: 触发事件
                - offset: 偏移天数
                - unit: 单位 (TimeRuleOffsetUnit)
                - direction: 方向 (TimeRuleDirection)
                - target_event: 目标事件

        Returns:
            int: 保存的规则数量
        """
        if not rules:
            return 0

        from logic.constants import TimeRuleInherit, TimeRuleStatus

        rules_created = 0
        for rule in rules:
            tr = TimeRule(
                related_id=related_id,
                related_type=related_type,
                inherit=TimeRuleInherit.SELF,
                party=rule.get('责任方'),
                trigger_event=rule.get('触发事件'),
                tge_param1=None,
                tge_param2=None,
                target_event=rule.get('目标事件'),
                tae_param1="初始模板",
                tae_param2=None,
                offset=rule.get('偏移', 0),
                unit=rule.get('单位'),
                direction=rule.get('方向'),
                status=TimeRuleStatus.TEMPLATE
            )
            self.session.add(tr)
            rules_created += 1

        if rules_created > 0:
            self.session.flush()

        return rules_created

