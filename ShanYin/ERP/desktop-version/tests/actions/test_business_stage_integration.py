"""
业务阶段推进集成测试
对比 system_events 与 business.details.history 的记录完整性

测试场景：
1. Business1: 逐步推进到"业务开展"
2. Business2: 推进到"客户反馈"时，update到"业务暂停"
3. Business3: 逐步推进到"业务开展"，然后update到"业务终止"
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Business, ChannelCustomer, SystemEvent
from logic.business import (
    create_business_action,
    advance_business_stage_action,
    update_business_status_action,
    CreateBusinessSchema,
    AdvanceBusinessStageSchema,
    UpdateBusinessStatusSchema,
)
from logic.constants import BusinessStatus


class TestBusinessStageIntegration:
    """业务阶段推进集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        """每个测试前创建独立的3个客户和3个业务"""
        self.session = db_session

        # 记录当前已有客户数量，以便精确取新创建的
        before_count = self.session.query(ChannelCustomer).count()

        # 创建3个客户
        for i in range(1, 4):
            c = ChannelCustomer(name=f"集成测试客户{i}", info=f"测试客户{i}")
            self.session.add(c)
        self.session.flush()

        # 只取新创建的3个
        after_customers = self.session.query(ChannelCustomer).filter(
            ChannelCustomer.name.like("集成测试客户%")
        ).order_by(ChannelCustomer.id).all()
        self.customers = after_customers[max(0, len(after_customers) - 3):]
        assert len(self.customers) == 3, f"期望3个客户，实际{len(self.customers)}个"

        # 记录当前已有业务数量
        before_biz_count = self.session.query(Business).count()

        # 创建3个业务
        self.businesses = []
        for c in self.customers:
            payload = CreateBusinessSchema(customer_id=c.id)
            result = create_business_action(self.session, payload)
            assert result.success is True
            self.businesses.append(result.data["business_id"])

        assert len(self.businesses) == 3

        # 映射
        self.biz1_id = self.businesses[0]
        self.biz2_id = self.businesses[1]
        self.biz3_id = self.businesses[2]

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------

    def biz(self, biz_id):
        return self.session.query(Business).get(biz_id)

    def events(self, biz_id):
        return self.session.query(SystemEvent).filter(
            SystemEvent.aggregate_type == "Business",
            SystemEvent.aggregate_id == biz_id
        ).order_by(SystemEvent.id).all()

    def print_snapshot(self, biz_id, label=""):
        b = self.biz(biz_id)
        evts = self.events(biz_id)
        history = b.details.get("history", []) if b.details else []
        print(f"\n{'='*65}")
        print(f"[{label}] Business(id={biz_id})")
        print(f"  status = {b.status}")
        print(f"  details.history ({len(history)}条):")
        for h in history:
            print(f"    {h['from']} -> {h['to']}  @ {h['time']}")
        print(f"  system_events ({len(evts)}条):")
        for e in evts:
            p = e.payload if isinstance(e.payload, dict) else json.loads(e.payload)
            print(f"    [{e.id}] {e.event_type}: from={p.get('from')} to={p.get('to')}")
        print(f"{'='*65}\n")

    def advance(self, biz_id, target, comment=""):
        payload = AdvanceBusinessStageSchema(
            business_id=biz_id,
            next_status=target,
            comment=comment or f"->{target}",
            payment_terms={"prepayment_ratio": 0.0, "balance_period": 30, "day_rule": "自然日", "start_trigger": "入库日"} if target == BusinessStatus.ACTIVE else None
        )
        result = advance_business_stage_action(self.session, payload)
        if not result.success:
            print(f"  [advance ERROR] {result.error}")
        return result

    def direct_update(self, biz_id, target):
        payload = UpdateBusinessStatusSchema(business_id=biz_id, status=target)
        result = update_business_status_action(self.session, payload)
        if not result.success:
            print(f"  [update ERROR] {result.error}")
        return result

    # -------------------------------------------------------------------------
    # 场景1: Business1 逐步推进到"业务开展"
    # -------------------------------------------------------------------------

    def test_scenario1_full_advance(self):
        """逐步推进: DRAFT->EVALUATION->FEEDBACK->LANDING->ACTIVE"""
        print("\n\n" + "#"*65)
        print("# 场景1: Business1 全流程推进到 ACTIVE")
        print("#"*65)

        steps = [
            (BusinessStatus.EVALUATION, "客户有意向"),
            (BusinessStatus.FEEDBACK, "客户反馈积极"),
            (BusinessStatus.LANDING, "合作落地确认"),
            (BusinessStatus.ACTIVE, "正式开展"),
        ]

        for target, comment in steps:
            print(f">> advance({self.biz1_id}) -> {target}")
            r = self.advance(self.biz1_id, target, comment)
            assert r.success is True
            self.print_snapshot(self.biz1_id, f"after {target}")

        # 最终验证
        b = self.biz(self.biz1_id)
        evts = self.events(self.biz1_id)
        history = b.details.get("history", [])
        event_transitions = [(e.payload.get("from") if isinstance(e.payload, dict) else json.loads(e.payload).get("from"),
                              e.payload.get("to") if isinstance(e.payload, dict) else json.loads(e.payload).get("to")) for e in evts]

        print("\n>>> 场景1 汇总:")
        print(f"    status           = {b.status}")
        print(f"    history 条数     = {len(history)}")
        print(f"    events 条数      = {len(evts)}")
        print(f"    差值(Events-History) = {len(evts) - len(history)}")
        print(f"    history transitions: {[h['to'] for h in history]}")
        print(f"    events transitions:  {[t[1] for t in event_transitions]}")

        assert b.status == BusinessStatus.ACTIVE
        assert len(history) == len(evts), f"history({len(history)}) != events({len(evts)})"

    # -------------------------------------------------------------------------
    # 场景2: Business2 推进到"客户反馈"后 direct_update 到"业务暂停"
    # -------------------------------------------------------------------------

    def test_scenario2_advance_then_direct_update_paused(self):
        """推进到FEEDBACK后，使用update_business_status_action改为PAUSED"""
        print("\n\n" + "#"*65)
        print("# 场景2: Business2 推进到FEEDBACK后 direct_update -> PAUSED")
        print("#"*65)

        steps = [
            (BusinessStatus.EVALUATION, "客户有意向"),
            (BusinessStatus.FEEDBACK, "客户反馈积极"),
        ]

        for target, comment in steps:
            print(f">> advance({self.biz2_id}) -> {target}")
            r = self.advance(self.biz2_id, target, comment)
            assert r.success is True
            self.print_snapshot(self.biz2_id, f"after {target}")

        # 此时应该: history=3条, events=3条
        b2 = self.biz(self.biz2_id)
        e2 = self.events(self.biz2_id)
        print(f"\n>> 推进完成后: history={len(b2.details.get('history', []))}条, events={len(e2)}条")

        # direct_update 到 PAUSED (不走 advance，不写 history)
        print(f">> direct_update({self.biz2_id}) -> PAUSED")
        r = self.direct_update(self.biz2_id, BusinessStatus.PAUSED)
        assert r.success is True
        self.print_snapshot(self.biz2_id, "after direct_update to PAUSED")

        # 最终验证
        b = self.biz(self.biz2_id)
        evts = self.events(self.biz2_id)
        history = b.details.get("history", [])
        history_tos = [h["to"] for h in history]
        event_types = [e.event_type for e in evts]
        event_tos = [(e.payload.get("to") if isinstance(e.payload, dict) else json.loads(e.payload).get("to")) for e in evts]

        print("\n>>> 场景2 汇总:")
        print(f"    status                    = {b.status}")
        print(f"    history 条数              = {len(history)}")
        print(f"    events 条数               = {len(evts)}")
        print(f"    差值(Events-History)      = {len(evts) - len(history)}")
        print(f"    history 中的 to 值        = {history_tos}")
        print(f"    events 中的 event_type    = {event_types}")
        print(f"    events 中的 to 值         = {event_tos}")
        print(f"    PAUSED 是否在 history 中? = {BusinessStatus.PAUSED in history_tos}")
        print(f"    BUSINESS_STATUS_CHANGED in events? = {'BUSINESS_STATUS_CHANGED' in event_types}")

        assert b.status == BusinessStatus.PAUSED
        assert BusinessStatus.PAUSED in history_tos, "PAUSED 应写入 history"
        assert "BUSINESS_STATUS_CHANGED" in event_types, "system_events 应有 BUSINESS_STATUS_CHANGED"

    # -------------------------------------------------------------------------
    # 场景3: Business3 推进到"业务开展"后 direct_update 到"业务终止"
    # -------------------------------------------------------------------------

    def test_scenario3_advance_then_direct_update_terminated(self):
        """推进到ACTIVE后，使用update_business_status_action改为TERMINATED"""
        print("\n\n" + "#"*65)
        print("# 场景3: Business3 推进到ACTIVE后 direct_update -> TERMINATED")
        print("#"*65)

        steps = [
            (BusinessStatus.EVALUATION, "客户有意向"),
            (BusinessStatus.FEEDBACK, "客户反馈积极"),
            (BusinessStatus.LANDING, "合作落地确认"),
            (BusinessStatus.ACTIVE, "正式开展"),
        ]

        for target, comment in steps:
            print(f">> advance({self.biz3_id}) -> {target}")
            r = self.advance(self.biz3_id, target, comment)
            assert r.success is True
            self.print_snapshot(self.biz3_id, f"after {target}")

        # direct_update 到 TERMINATED
        print(f">> direct_update({self.biz3_id}) -> TERMINATED")
        r = self.direct_update(self.biz3_id, BusinessStatus.TERMINATED)
        assert r.success is True
        self.print_snapshot(self.biz3_id, "after direct_update to TERMINATED")

        # 最终验证
        b = self.biz(self.biz3_id)
        evts = self.events(self.biz3_id)
        history = b.details.get("history", [])
        history_tos = [h["to"] for h in history]
        event_types = [e.event_type for e in evts]
        event_tos = [(e.payload.get("to") if isinstance(e.payload, dict) else json.loads(e.payload).get("to")) for e in evts]

        print("\n>>> 场景3 汇总:")
        print(f"    status                    = {b.status}")
        print(f"    history 条数              = {len(history)}")
        print(f"    events 条数               = {len(evts)}")
        print(f"    差值(Events-History)      = {len(evts) - len(history)}")
        print(f"    history 中的 to 值        = {history_tos}")
        print(f"    events 中的 event_type    = {event_types}")
        print(f"    events 中的 to 值         = {event_tos}")
        print(f"    TERMINATED 是否在 history 中? = {BusinessStatus.TERMINATED in history_tos}")
        print(f"    BUSINESS_STATUS_CHANGED in events? = {'BUSINESS_STATUS_CHANGED' in event_types}")

        assert b.status == BusinessStatus.TERMINATED
        assert BusinessStatus.TERMINATED in history_tos, "TERMINATED 应写入 history"
        assert "BUSINESS_STATUS_CHANGED" in event_types, "system_events 应有 BUSINESS_STATUS_CHANGED"

    # -------------------------------------------------------------------------
    # 综合比对报告
    # -------------------------------------------------------------------------

    def test_final_comparison(self):
        """最终比对三个 business 的 events vs history"""
        print("\n\n" + "#"*65)
        print("# 综合比对报告")
        print("#"*65)

        for biz_id, label in [
            (self.biz1_id, "Business1-全流程推进"),
            (self.biz2_id, "Business2-推进后UPDATE_PAUSED"),
            (self.biz3_id, "Business3-推进后UPDATE_TERMINATED"),
        ]:
            b = self.biz(biz_id)
            evts = self.events(biz_id)
            history = b.details.get("history", []) if b.details else []

            history_tos = set(h["to"] for h in history)
            event_tos = set((e.payload.get("to") if isinstance(e.payload, dict) else json.loads(e.payload).get("to")) for e in evts)

            print(f"\n【{label}】 id={biz_id}")
            print(f"  status = {b.status}")
            print(f"  history({len(history)}) vs events({len(evts)}), 差值={len(evts)-len(history)}")
            print(f"  history.to: {sorted(history_tos)}")
            print(f"  events.to:  {sorted(event_tos)}")

            diff = history_tos - event_tos
            if diff:
                print(f"  ⚠️  history有但events无: {diff}")
            diff2 = event_tos - history_tos
            if diff2:
                print(f"  ⚠️  events有但history无: {diff2}")
            if not diff and not diff2 and len(history) == len(evts):
                print(f"  ✅ 完全一致")
