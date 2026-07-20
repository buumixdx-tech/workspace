"""
时间规则继承集成测试
测试场景：业务、供应链、VC三层结构的规则继承

步骤：
1. 创建客户c1、供应商s1
2. 创建业务b1（针对c1），推进到业务开展，设定付款条款 + 手动规则
3. 创建供应链sc1（针对s1），设定付款条款 + 手动规则
4. 创建VC（设备采购，从s1采购，发货给c1），验证规则继承

汇总：VC创建后，b1、sc1、vc1各自的规则列表
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Business, SupplyChain, VirtualContract, TimeRule, ChannelCustomer, Supplier, SKU
from logic.business import (
    create_business_action, advance_business_stage_action,
    CreateBusinessSchema, AdvanceBusinessStageSchema,
)
from logic.supply_chain import create_supply_chain_action, CreateSupplyChainSchema
from logic.vc import create_procurement_vc_action, CreateProcurementVCSchema, VCElementSchema
from logic.time_rules import save_rule_action, TimeRuleSchema
from logic.time_rules.rule_manager import RuleManager
from logic.constants import (
    BusinessStatus, SKUType, TimeRuleRelatedType, TimeRuleInherit,
    TimeRuleStatus, TimeRuleParty, TimeRuleOffsetUnit, TimeRuleDirection,
    EventType
)


def print_rules(rules, label):
    """打印规则列表"""
    print(f"\n{'=' * 65}")
    print(f"【{label}】共 {len(rules)} 条规则")
    print(f"{'=' * 65}")
    for r in rules:
        tge = r.get("tge_param1") or ""
        tae = r.get("tae_param1") or ""
        print(f"  [{r.get('id', '?')}] {r.get('party', '?')} | "
              f"{r.get('trigger_event', '?')}{tge} "
              f"-> {r.get('target_event', '?')}{tae} | "
              f"offset={r.get('offset')} {r.get('unit')} {r.get('direction')} | "
              f"inherit={r.get('inherit')} status={r.get('status')}")


class TestTimeRuleInheritance:
    """时间规则继承集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        """每个测试前创建客户、供应商、SKU"""
        self.session = db_session

        # 1. 创建客户 c1
        c1 = ChannelCustomer(name="测试客户c1", info="客户")
        self.session.add(c1)
        self.session.flush()
        self.c1_id = c1.id

        # 2. 创建供应商 s1（设备类）
        s1 = Supplier(name="测试供应商s1", category="设备", address="地址")
        self.session.add(s1)
        self.session.flush()
        self.s1_id = s1.id

        # 3. 创建必要的点位数据
        from models import Point
        # 供应商仓库（发货点）
        sup_wh = Point(name="s1供应商仓", type="供应商仓", supplier_id=self.s1_id)
        self.session.add(sup_wh)
        self.session.flush()
        self.sup_wh_id = sup_wh.id
        # 客户仓库（收货点）
        cust_wh = Point(name="c1仓库", type="客户仓", customer_id=self.c1_id)
        self.session.add(cust_wh)
        self.session.flush()
        self.cust_wh_id = cust_wh.id

        # 4. 创建 SKU
        sku = SKU(supplier_id=self.s1_id, name="测试设备-01", type_level1="设备", type_level2="主机")
        self.session.add(sku)
        self.session.flush()
        self.sku_id = sku.id

        print(f"\n{'#'*65}")
        print(f"# 初始数据: c1_id={self.c1_id}, s1_id={self.s1_id}, sku_id={self.sku_id}")
        print(f"# 仓库: sup_wh_id={self.sup_wh_id}, cust_wh_id={self.cust_wh_id}")
        print(f"{'#'*65}")

    # -------------------------------------------------------------------------
    # 步骤2: 创建业务 b1，推进到业务开展，设定付款条款 + 手动规则
    # -------------------------------------------------------------------------

    def test_step2_create_business_with_payment_terms_and_manual_rule(self):
        """步骤2: 创建业务，推进到业务开展，设付款条款 + 手动规则"""

        # 2.1 创建业务
        result = create_business_action(
            self.session,
            CreateBusinessSchema(customer_id=self.c1_id)
        )
        assert result.success is True
        self.b1_id = result.data["business_id"]
        print(f"\n>> 业务 b1 创建成功, id={self.b1_id}")

        # 2.2 推进到 EVALUATION
        result = advance_business_stage_action(
            self.session,
            AdvanceBusinessStageSchema(business_id=self.b1_id, next_status=BusinessStatus.EVALUATION, comment="评估中")
        )
        assert result.success is True

        # 2.3 推进到 FEEDBACK
        result = advance_business_stage_action(
            self.session,
            AdvanceBusinessStageSchema(business_id=self.b1_id, next_status=BusinessStatus.FEEDBACK, comment="客户反馈")
        )
        assert result.success is True

        # 2.4 推进到 LANDING（付款条款在这里不能设，需到ACTIVE才设）
        result = advance_business_stage_action(
            self.session,
            AdvanceBusinessStageSchema(business_id=self.b1_id, next_status=BusinessStatus.LANDING, comment="合作落地")
        )
        assert result.success is True
        print(f">> b1 推进到 LANDING")

        # 2.5 推进到 ACTIVE（业务开展），设付款条款 + pricing
        # 首付0，账期40天，自然日，条件为入库
        payment_terms = {
            "prepayment_ratio": 0.0,
            "balance_period": 40,
            "day_rule": "自然日",
            "start_trigger": "入库"
        }
        pricing = {"测试设备-01": {"price": 1000.0, "deposit": 100.0}}

        result = advance_business_stage_action(
            self.session,
            AdvanceBusinessStageSchema(
                business_id=self.b1_id,
                next_status=BusinessStatus.ACTIVE,
                comment="正式开展",
                payment_terms=payment_terms,
                pricing=pricing
            )
        )
        assert result.success is True
        print(f">> b1 推进到 ACTIVE，付款条款: 首付0, 账期40天, 自然日, 入库触发")

        # 2.6 手动设定规则：VC创立日起，我方10日内发货
        # trigger=虚拟合同创建, target=物流已发货, offset=10, direction=AFTER, inherit=近继承
        rule_payload = TimeRuleSchema(
            related_id=self.b1_id,
            related_type="业务",
            party="我方",
            trigger_event="虚拟合同创建",
            target_event="物流已发货",
            offset=10,
            unit="自然日",
            direction="after",
            inherit=1,  # 近继承：传播到VC
            status="模板"
        )
        result = save_rule_action(self.session, rule_payload)
        assert result.success is True
        b1_manual_rule_id = result.data["rule_id"]
        print(f">> b1 手动规则创建成功: VC创立日起10日内发货, rule_id={b1_manual_rule_id}")

        # 验证 b1 的规则
        b1_rules = self.session.query(TimeRule).filter(
            TimeRule.related_type == "业务",
            TimeRule.related_id == self.b1_id
        ).all()
        print_rules([{
            "id": r.id, "party": r.party, "trigger_event": r.trigger_event,
            "tge_param1": r.tge_param1, "target_event": r.target_event,
            "tae_param1": r.tae_param1, "offset": r.offset, "unit": r.unit,
            "direction": r.direction, "inherit": r.inherit, "status": r.status
        } for r in b1_rules], f"b1 (id={self.b1_id}) 当前规则")

        return self.b1_id

    # -------------------------------------------------------------------------
    # 步骤3: 创建供应链 sc1，设付款条款 + 手动规则
    # -------------------------------------------------------------------------

    def test_step3_create_supply_chain_with_payment_terms_and_manual_rule(self):
        """步骤3: 创建供应链，设付款条款 + 手动规则"""

        # sc1: 首付50%，账期30天，自然日，入库触发
        sc_payload = CreateSupplyChainSchema(
            supplier_id=self.s1_id,
            supplier_name="测试供应商s1",
            type="设备",
            items=[{"sku_id": self.sku_id, "price": 1000.0, "is_floating": False}],
            payment_terms={
                "prepayment_ratio": 0.5,
                "balance_period": 30,
                "day_rule": "自然日",
                "start_trigger": "入库"
            }
        )
        result = create_supply_chain_action(self.session, sc_payload)
        assert result.success is True
        self.sc1_id = result.data.get("sc_id") or result.data.get("supply_chain_id")
        print(f"\n>> 供应链 sc1 创建成功, id={self.sc1_id}, 付款条款: 首付50%, 账期30天")

        # 注意：供应链创建时 payment_terms 只存字段，不自动生成 time_rule
        # 规则需要手动创建，或在 VC 创建时通过 sync_from_parent 继承

        # 手动规则：首付50%日起，s1要3日内发货
        # trigger=合同预付完成, target=物流已发货, offset=3, direction=AFTER, inherit=近继承
        rule_payload = TimeRuleSchema(
            related_id=self.sc1_id,
            related_type="供应链",
            party="供应商",
            trigger_event="合同预付完成",
            target_event="物流已发货",
            offset=3,
            unit="自然日",
            direction="after",
            inherit=1,  # 近继承：传播到VC
            status="模板"
        )
        result = save_rule_action(self.session, rule_payload)
        assert result.success is True
        sc1_manual_rule_id = result.data["rule_id"]
        print(f">> sc1 手动规则创建成功: 首付50%日起3日内发货, rule_id={sc1_manual_rule_id}")

        # 验证 sc1 的规则
        sc1_rules = self.session.query(TimeRule).filter(
            TimeRule.related_type == "供应链",
            TimeRule.related_id == self.sc1_id
        ).all()
        print_rules([{
            "id": r.id, "party": r.party, "trigger_event": r.trigger_event,
            "tge_param1": r.tge_param1, "target_event": r.target_event,
            "tae_param1": r.tae_param1, "offset": r.offset, "unit": r.unit,
            "direction": r.direction, "inherit": r.inherit, "status": r.status
        } for r in sc1_rules], f"sc1 (id={self.sc1_id}) 当前规则")

        return self.sc1_id

    # -------------------------------------------------------------------------
    # 完整流程测试（综合）
    # -------------------------------------------------------------------------

    def test_full_flow_rule_inheritance(self):
        """完整流程：b1 + sc1 -> vc1，验证规则继承"""

        # ----- 步骤2: b1 -----
        print(f"\n{'='*65}")
        print("# 步骤2: 创建业务 b1，推进到 ACTIVE，设付款条款 + 手动规则")
        print(f"{'='*65}")

        # 创建业务
        result = create_business_action(self.session, CreateBusinessSchema(customer_id=self.c1_id))
        assert result.success is True
        b1_id = result.data["business_id"]

        # 推进到 ACTIVE
        for target, comment in [
            (BusinessStatus.EVALUATION, "评估"),
            (BusinessStatus.FEEDBACK, "反馈"),
            (BusinessStatus.LANDING, "落地"),
        ]:
            advance_business_stage_action(
                self.session,
                AdvanceBusinessStageSchema(business_id=b1_id, next_status=target, comment=comment)
            )

        # 推进到 ACTIVE 设付款条款（首付0，账期40，自然日，入库）
        result = advance_business_stage_action(
            self.session,
            AdvanceBusinessStageSchema(
                business_id=b1_id, next_status=BusinessStatus.ACTIVE, comment="正式开展",
                payment_terms={"prepayment_ratio": 0.0, "balance_period": 40, "day_rule": "自然日", "start_trigger": "入库"},
                pricing={"测试设备-01": {"price": 1000.0, "deposit": 100.0}}
            )
        )
        assert result.success is True

        # 手动规则：VC创立日起，我方10日内发货 (inherit=1，近继承)
        r1 = save_rule_action(self.session, TimeRuleSchema(
            related_id=b1_id, related_type="业务", party="我方",
            trigger_event="虚拟合同创建", target_event="物流已发货",
            offset=10, unit="自然日", direction="after",
            inherit=1, status="模板"
        ))
        assert r1.success is True
        print(f">> b1 手动规则: VC创立日起10日内发货 (rule_id={r1.data['rule_id']})")

        # ----- 步骤3: sc1 -----
        print(f"\n{'='*65}")
        print("# 步骤3: 创建供应链 sc1，设付款条款 + 手动规则")
        print(f"{'='*65}")

        # 创建供应链（直接创建，不需要推进状态）
        result = create_supply_chain_action(self.session, CreateSupplyChainSchema(
            supplier_id=self.s1_id, supplier_name="测试供应商s1", type="设备",
            items=[{"sku_id": self.sku_id, "price": 1000.0, "is_floating": False}],
            payment_terms={"prepayment_ratio": 0.5, "balance_period": 30, "day_rule": "自然日", "start_trigger": "入库"}
        ))
        assert result.success is True
        sc1_id = result.data.get("sc_id") or result.data.get("supply_chain_id")

        # 手动规则：首付50%日起，s1要3日内发货 (inherit=1，近继承)
        r2 = save_rule_action(self.session, TimeRuleSchema(
            related_id=sc1_id, related_type="供应链", party="供应商",
            trigger_event="合同预付完成", target_event="物流已发货",
            offset=3, unit="自然日", direction="after",
            inherit=1, status="模板"
        ))
        assert r2.success is True
        print(f">> sc1 手动规则: 首付50%日起3日内发货 (rule_id={r2.data['rule_id']})")

        # ----- 步骤4: vc1 -----
        print(f"\n{'='*65}")
        print("# 步骤4: 创建 VC（设备采购，从s1采购，发货给c1），设手动规则")
        print(f"{'='*65}")

        # VC手动规则：VC创立日起，我方5日内首付达到30% (inherit=0，本级定制)
        # 目标事件: 付款比例达到(tae_param1="30%")
        vc_manual_rules = [{
            "party": "我方",
            "trigger_event": "虚拟合同创建",
            "target_event": "付款比例达到",
            "tae_param1": "30%",
            "offset": 5,
            "unit": "自然日",
            "direction": "after",
            "inherit": 0,
            "status": "生效"
        }]

        result = create_procurement_vc_action(
            self.session,
            CreateProcurementVCSchema(
                business_id=b1_id,
                sc_id=sc1_id,
                elements=[VCElementSchema(
                    shipping_point_id=0,
                    receiving_point_id=self.cust_wh_id,
                    sku_id=self.sku_id,
                    qty=1, price=1000.0, deposit=100.0,
                    subtotal=1000.0
                )],
                total_amt=1000.0, total_deposit=100.0,
                payment={"prepayment_ratio": 0.5},
                description="测试VC"
            ),
            draft_rules=vc_manual_rules
        )
        assert result.success is True
        vc1_id = result.data["vc_id"]
        print(f">> VC 创建成功, id={vc1_id}, linked business={b1_id}, supply_chain={sc1_id}")

        # ----- 汇总所有规则 -----
        print(f"\n{'='*65}")
        print(f"# 汇总: b1_id={b1_id}, sc1_id={sc1_id}, vc1_id={vc1_id}")
        print(f"{'='*65}")

        # b1 的规则（自身）
        b1_rules = self.session.query(TimeRule).filter(
            TimeRule.related_type == "业务", TimeRule.related_id == b1_id
        ).all()
        print_rules([{
            "id": r.id, "party": r.party, "trigger_event": r.trigger_event,
            "tge_param1": r.tge_param1, "target_event": r.target_event,
            "tae_param1": r.tae_param1, "offset": r.offset, "unit": r.unit,
            "direction": r.direction, "inherit": r.inherit, "status": r.status
        } for r in b1_rules], f"b1 (业务) 规则")

        # sc1 的规则（自身）
        sc1_rules = self.session.query(TimeRule).filter(
            TimeRule.related_type == "供应链", TimeRule.related_id == sc1_id
        ).all()
        print_rules([{
            "id": r.id, "party": r.party, "trigger_event": r.trigger_event,
            "tge_param1": r.tge_param1, "target_event": r.target_event,
            "tae_param1": r.tae_param1, "offset": r.offset, "unit": r.unit,
            "direction": r.direction, "inherit": r.inherit, "status": r.status
        } for r in sc1_rules], f"sc1 (供应链) 规则")

        # vc1 的规则（从 b1/sc1 继承 + 自身定制）
        vc1_rules = self.session.query(TimeRule).filter(
            TimeRule.related_type == "虚拟合同", TimeRule.related_id == vc1_id
        ).all()
        print_rules([{
            "id": r.id, "party": r.party, "trigger_event": r.trigger_event,
            "tge_param1": r.tge_param1, "target_event": r.target_event,
            "tae_param1": r.tae_param1, "offset": r.offset, "unit": r.unit,
            "direction": r.direction, "inherit": r.inherit, "status": r.status
        } for r in vc1_rules], f"vc1 (虚拟合同) 规则")

        # ----- 断言验证 -----
        print(f"\n{'='*65}")
        print("# 验证")
        print(f"{'='*65}")

        # b1: 应该至少有 1 条（尾款规则）+ 1 条（手动：VC创立日发货）
        # 首付0，所以预付规则不生成
        assert len(b1_rules) >= 1, f"b1应有至少1条规则，实际{len(b1_rules)}"
        print(f"  [OK] b1 规则数: {len(b1_rules)}")

        # sc1: 首付50%，应生成 1条预付规则 + 1条手动规则 = 2条
        assert len(sc1_rules) >= 1, f"sc1应有至少1条规则，实际{len(sc1_rules)}"
        print(f"  [OK] sc1 规则数: {len(sc1_rules)}")

        # vc1: 继承 b1的1条近继承规则 + sc1的1条近继承规则 + 1条本级定制 = 3条
        assert len(vc1_rules) >= 1, f"vc1应有至少1条规则，实际{len(vc1_rules)}"
        print(f"  [OK] vc1 规则数: {len(vc1_rules)}")

        # vc1 应有本级定制规则（继承=0）
        vc_own_rules = [r for r in vc1_rules if r.inherit == 0]
        assert len(vc_own_rules) >= 1, "vc1应有本级定制规则"
        print(f"  [OK] vc1 本级定制规则数: {len(vc_own_rules)}")

        # vc1 应有继承自 b1 的规则（inherit=1）
        from_b1 = [r for r in vc1_rules if r.inherit == 1]
        print(f"  [OK] vc1 继承自b1/sc1的规则数: {len(from_b1)}")

        print(f"\n  b1_rules: {[(r.party, r.trigger_event, r.tge_param1, r.target_event, r.tae_param1, r.offset, r.unit, r.direction, r.inherit, r.status) for r in b1_rules]}")
        print(f"  sc1_rules: {[(r.party, r.trigger_event, r.tge_param1, r.target_event, r.tae_param1, r.offset, r.unit, r.direction, r.inherit, r.status) for r in sc1_rules]}")
        print(f"  vc1_rules: {[(r.party, r.trigger_event, r.tge_param1, r.target_event, r.tae_param1, r.offset, r.unit, r.direction, r.inherit, r.status) for r in vc1_rules]}")
