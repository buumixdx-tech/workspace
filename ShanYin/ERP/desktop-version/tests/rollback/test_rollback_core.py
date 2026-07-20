"""
核心回滚函数单元测试
测试 serialize_model / serialize_session_new_records / serialize_dirty_records
"""
import pytest
from datetime import datetime
from decimal import Decimal
from tests.rollback.conftest import create_vc, create_finance_account, create_financial_journal


# ============ serialize_model ============

class TestSerializeModel:
    def test_serialize_simple_fields(self, session, base_data):
        """测试简单字段序列化"""
        from logic.transactions import serialize_model

        vc = create_vc(session, base_data.business.id, type="设备采购")
        result = serialize_model(vc)

        assert result["id"] == vc.id
        assert result["type"] == "设备采购"
        assert result["status"] == "执行"
        assert result["business_id"] == base_data.business.id

    def test_serialize_datetime(self, session, base_data):
        """datetime 字段序列化为 ISO 格式字符串"""
        from logic.transactions import serialize_model

        vc = create_vc(session, base_data.business.id, flush=False)
        vc.status_timestamp = datetime(2026, 3, 15, 10, 30, 0)
        session.flush()
        result = serialize_model(vc)

        assert "status_timestamp" in result
        # 应该是 ISO 字符串，不是 datetime 对象
        assert isinstance(result["status_timestamp"], str)

    def test_serialize_decimal(self, session, base_data):
        """serialize_model 将 Decimal 转换为 float"""
        from decimal import Decimal
        from logic.transactions import serialize_model

        # 创建一个带 Decimal 字段的 mock 对象
        class MockModel:
            def __init__(self):
                self.amount = Decimal("1000.50")

        result = serialize_model(MockModel())
        assert isinstance(result["amount"], float)
        assert result["amount"] == 1000.50

    def test_ignores_private_and_sa_fields(self, session, base_data):
        """排除 _ 开头字段和 SQLAlchemy 内部字段"""
        from logic.transactions import serialize_model

        vc = create_vc(session, base_data.business.id)
        result = serialize_model(vc)

        # 不应该有 SQLAlchemy 内部字段
        assert "_sa_instance_state" not in result
        assert "metadata" not in result
        assert "registry" not in result
        # 不应该有 private 字段
        for key in result:
            assert not key.startswith("_"), f"Unexpected private key: {key}"


# ============ serialize_session_new_records ============

class TestSerializeSessionNewRecords:
    def test_empty_session(self, session):
        """空 session.new 返回空列表"""
        from logic.transactions import serialize_session_new_records

        result = serialize_session_new_records(session)
        assert result == []

    def test_single_new_record(self, session, base_data):
        """serialize_objs 序列化 flush 之前的新记录"""
        from logic.transactions import serialize_objs

        vc = create_vc(session, base_data.business.id, flush=False)
        result = serialize_objs([vc])

        assert len(result) == 1
        assert result[0]["class"] == "VirtualContract"
        assert result[0]["data"]["type"] == "设备采购"
        assert result[0]["id"] is None  # flush 前 id 尚未分配

        session.flush()  # flush 后 id 被分配
        assert vc.id is not None

    def test_multiple_new_records(self, session, base_data):
        """serialize_objs 序列化多条新记录"""
        from logic.transactions import serialize_objs

        vc1 = create_vc(session, base_data.business.id, type="设备采购", flush=False)
        vc2 = create_vc(session, base_data.business.id, type="物料采购", flush=False)
        result = serialize_objs([vc1, vc2])

        assert len(result) == 2
        classes = {r["class"] for r in result}
        assert classes == {"VirtualContract"}

        session.flush()


# ============ serialize_dirty_records ============

class TestSerializeDirtyRecords:
    def test_no_dirty_records(self, session, base_data):
        """未修改的记录不在 session.dirty"""
        from logic.transactions import serialize_dirty_records

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()
        # 仅查询，未修改
        result = serialize_dirty_records(session)
        assert result == []

    def test_dirty_record_has_before_and_after(self, session, base_data):
        """已修改记录包含修改前（committed_state）和修改后值"""
        from logic.transactions import serialize_dirty_records

        vc = create_vc(session, base_data.business.id, status="执行", flush=False)
        session.flush()

        # 修改记录，并在 flush 之前序列化
        vc.status = "完成"
        result = serialize_dirty_records(session)
        session.flush()

        assert len(result) == 1
        assert result[0]["class"] == "VirtualContract"
        assert result[0]["id"] == vc.id
        # committed_state 是修改前的值
        assert result[0]["before"]["status"] == "执行"
        # after 是修改后的值
        assert result[0]["after"]["status"] == "完成"

    def test_before_and_after_are_different(self, session, base_data):
        """修改前后值确实不同"""
        from logic.transactions import serialize_dirty_records

        vc = create_vc(session, base_data.business.id, type="设备采购", flush=False)
        session.flush()

        vc.type = "物料采购"
        result = serialize_dirty_records(session)
        session.flush()

        assert result[0]["before"]["type"] == "设备采购"
        assert result[0]["after"]["type"] == "物料采购"
