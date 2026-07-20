"""
事件系统单元测试
测试事件发布、订阅、分发机制
"""

import pytest
from datetime import datetime
from logic.events.dispatcher import emit_event
from logic.events import listeners
from models import SystemEvent
from logic.constants import SystemEventType, SystemAggregateType


class TestEventDispatcher:
    """事件发布器测试"""

    def test_emit_event_creates_record(self, db_session, sample_virtual_contract):
        """✅ 发布事件会创建数据库记录"""
        # When
        event = emit_event(
            db_session,
            SystemEventType.VC_CREATED,
            SystemAggregateType.VIRTUAL_CONTRACT,
            sample_virtual_contract.id,
            {"test": "data"}
        )

        # Then: 事件应被持久化
        db_session.flush()
        saved_event = db_session.query(SystemEvent).filter(
            SystemEvent.id == event.id
        ).first()
        
        assert saved_event is not None
        assert saved_event.event_type == SystemEventType.VC_CREATED
        assert saved_event.payload == {"test": "data"}

    def test_emit_event_with_multiple_payloads(self, db_session, sample_virtual_contract):
        """✅ 事件可携带复杂 payload"""
        # Given
        payload = {
            "from": "DRAFT",
            "to": "ACTIVE",
            "amount": 10000,
            "items": [{"id": 1, "name": "设备A"}]
        }

        # When
        event = emit_event(
            db_session,
            SystemEventType.VC_STATUS_TRANSITION,
            SystemAggregateType.VIRTUAL_CONTRACT,
            sample_virtual_contract.id,
            payload
        )

        # Then
        db_session.flush()
        assert event.payload == payload


class TestEventListeners:
    """事件监听器测试"""

    def test_register_and_dispatch_listener(self, db_session, sample_virtual_contract):
        """✅ 注册监听器并接收事件"""
        # Given: 定义一个监听器函数
        received_events = []
        
        def test_listener(session, event):
            received_events.append(event.event_type)
        
        # 注册监听器
        listeners.register_listener(SystemEventType.VC_CREATED, test_listener)

        try:
            # When: 发布事件
            emit_event(
                db_session,
                SystemEventType.VC_CREATED,
                SystemAggregateType.VIRTUAL_CONTRACT,
                sample_virtual_contract.id,
                {}
            )

            # Then: 监听器应收到事件
            assert SystemEventType.VC_CREATED in received_events
        finally:
            # 清理：移除监听器
            listeners.unregister_listener(SystemEventType.VC_CREATED, test_listener)

    def test_multiple_listeners_receive_same_event(self, db_session, sample_virtual_contract):
        """✅ 多个监听器可接收同一事件"""
        # Given
        call_count = {"listener1": 0, "listener2": 0}
        
        def listener1(session, event):
            call_count["listener1"] += 1
        
        def listener2(session, event):
            call_count["listener2"] += 1
        
        listeners.register_listener("TEST_EVENT", listener1)
        listeners.register_listener("TEST_EVENT", listener2)

        try:
            # When
            emit_event(
                db_session,
                "TEST_EVENT",
                SystemAggregateType.VIRTUAL_CONTRACT,
                sample_virtual_contract.id,
                {}
            )

            # Then: 两个监听器都应被调用
            assert call_count["listener1"] == 1
            assert call_count["listener2"] == 1
        finally:
            listeners.unregister_listener("TEST_EVENT", listener1)
            listeners.unregister_listener("TEST_EVENT", listener2)

    def test_listener_error_does_not_interrupt_others(self, db_session, sample_virtual_contract):
        """✅ 监听器错误不会中断其他监听器"""
        # Given
        results = []
        
        def failing_listener(session, event):
            results.append("failing")
            raise RuntimeError("Intentional error")
        
        def success_listener(session, event):
            results.append("success")
        
        listeners.register_listener("ERROR_TEST", failing_listener)
        listeners.register_listener("ERROR_TEST", success_listener)

        try:
            # When: 发布事件
            emit_event(
                db_session,
                "ERROR_TEST",
                SystemAggregateType.VIRTUAL_CONTRACT,
                sample_virtual_contract.id,
                {}
            )

            # Then: 成功的监听器仍应被调用
            assert "success" in results
            assert "failing" in results
        finally:
            listeners.unregister_listener("ERROR_TEST", failing_listener)
            listeners.unregister_listener("ERROR_TEST", success_listener)

    def test_get_registered_listeners(self, db_session, sample_virtual_contract):
        """✅ 获取已注册的监听器统计"""
        # Given: 注册一些监听器
        def dummy_listener(session, event):
            pass
        
        listeners.register_listener("STATS_TEST", dummy_listener)

        try:
            # When
            stats = listeners.get_registered_listeners()

            # Then
            assert "STATS_TEST" in stats
            assert stats["STATS_TEST"] >= 1
        finally:
            listeners.unregister_listener("STATS_TEST", dummy_listener)


class TestEventTypes:
    """事件类型测试"""

    def test_all_event_types_can_be_emitted(self, db_session, sample_virtual_contract):
        """✅ 所有定义的事件类型都可以发布"""
        # Given
        event_types = [
            SystemEventType.VC_CREATED,
            SystemEventType.VC_STATUS_TRANSITION,
            SystemEventType.VC_GOODS_CLEARED,
            SystemEventType.VC_DEPOSIT_CLEARED,
            SystemEventType.LOGISTICS_STATUS_CHANGED,
        ]

        # When & Then: 每个事件类型都应能成功发布
        for event_type in event_types:
            event = emit_event(
                db_session,
                event_type,
                SystemAggregateType.VIRTUAL_CONTRACT,
                sample_virtual_contract.id,
                {"test": event_type}
            )
            assert event.id is not None