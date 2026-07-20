"""
边界条件和拦截测试
测试 rollback_operation / redo_operation 的拦截逻辑
"""
import pytest
from tests.rollback.conftest import create_vc


# ============ rollback_operation 拦截 ============

class TestRollbackInterception:
    def test_rollback_twice_fails(self, session, base_data):
        """重复回滚 → 第二次被拦截"""
        from logic.transactions import create_operation_record, complete_operation_record, rollback_operation

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
        )
        complete_operation_record(tx_id, {"records": []}, session=session)
        session.commit()

        # 第一次回滚成功
        result1 = rollback_operation(session, tx_id, "录错了")
        assert result1.success is True

        # 第二次回滚被拦截
        result2 = rollback_operation(session, tx_id, "再回滚一次")
        assert result2.success is False
        assert "已被回滚" in result2.error or "不允许" in result2.error

    def test_finish_vc_rollback_fails(self, session, base_data):
        """FINISH 状态 VC 的操作 → 回滚被拦截"""
        from logic.transactions import create_operation_record, complete_operation_record, rollback_operation
        from logic.constants import VCStatus

        vc = create_vc(session, base_data.business.id, status=VCStatus.FINISH, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={"records": [{"class": "VirtualContract", "id": vc.id, "data": {"status": "执行"}}]},
        )
        complete_operation_record(tx_id, {"records": []}, session=session)
        session.commit()

        result = rollback_operation(session, tx_id, "录错了")
        assert result.success is False
        assert "已完成" in result.error or "完成" in result.error

    def test_failed_operation_cannot_rollback(self, session, base_data):
        """标记为 failed 的操作不允许回滚"""
        from logic.transactions import create_operation_record, rollback_operation, OperationTransaction

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
        )
        # 模拟 failed 状态：标记后回滚
        tx = session.query(OperationTransaction).get(tx_id)
        tx.status = "failed"
        session.flush()
        # rollback 前不做额外处理，测试 rollback_operation 的检查

        result = rollback_operation(session, tx_id, "尝试回滚")
        assert result.success is False

    def test_non_existent_tx_id_fails(self, session):
        """不存在的 tx_id 被拦截"""
        from logic.transactions import rollback_operation

        result = rollback_operation(session, 99999, "录错了")
        assert result.success is False


# ============ redo_operation 拦截 ============

class TestRedoInterception:
    def test_redo_non_rolled_back_fails(self, session, base_data):
        """未回滚的操作不能 redo"""
        from logic.transactions import create_operation_record, complete_operation_record, redo_operation

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
        )
        complete_operation_record(tx_id, {"records": []}, session=session)
        session.commit()

        # 未回滚，尝试 redo → 被拦截
        result = redo_operation(session, tx_id)
        assert result.success is False
        assert "未被回滚" in result.error or "rolled_back" in result.error

    def test_redo_restores_status(self, session, base_data):
        """redo 后 transaction status 恢复为 committed"""
        from logic.transactions import create_operation_record, complete_operation_record
        from logic.transactions import rollback_operation, redo_operation
        from models import OperationTransaction

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
        )
        complete_operation_record(tx_id, {"records": []}, session=session)
        session.commit()

        rollback_operation(session, tx_id, "录错了")
        result = redo_operation(session, tx_id)

        assert result.success is True
        tx = session.query(OperationTransaction).get(tx_id)
        assert tx.status == "committed"


# ============ create_operation_record / complete_operation_record ============

class TestOperationRecordLifecycle:
    def test_creates_with_pending_status(self, session, base_data):
        """create_operation_record 创建后 status=committed"""
        from logic.transactions import create_operation_record
        from models import OperationTransaction

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
        )
        session.commit()

        tx = session.query(OperationTransaction).get(tx_id)
        assert tx.status == "committed"

    def test_complete_updates_snapshot_after(self, session, base_data):
        """complete_operation_record 写入 snapshot_after"""
        from logic.transactions import create_operation_record, complete_operation_record
        from models import OperationTransaction

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
        )

        snapshot = {
            "records": [{"class": "VirtualContract", "id": vc.id, "data": {"status": "完成"}}]
        }
        complete_operation_record(tx_id, snapshot, session=session)
        session.commit()

        tx = session.query(OperationTransaction).get(tx_id)
        assert len(tx.snapshot_after["records"]) == 1
        assert tx.snapshot_after["records"][0]["data"]["status"] == "完成"

    def test_involved_ids_helper(self, session, base_data):
        """involved_ids 字段正确记录关联 ID"""
        from logic.transactions import create_operation_record
        from models import OperationTransaction

        vc = create_vc(session, base_data.business.id, flush=False)
        session.flush()

        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before={},
            involved_ids=[vc.id],
        )
        session.commit()

        tx = session.query(OperationTransaction).get(tx_id)
        assert vc.id in tx.involved_ids
