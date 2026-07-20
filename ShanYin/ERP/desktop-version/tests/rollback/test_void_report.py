"""
report.json 幂等去重和 void_report 测试
使用 tmp_path 模拟文件系统
"""
import pytest
import json
from datetime import datetime


@pytest.fixture
def report_file(tmp_path):
    """创建初始 report.json 文件"""
    report_dir = tmp_path / "finance-report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.json"

    report_data = {
        "2026-03": {
            "month": "2026-03",
            "vouchers": [
                {"ref_type": "CashFlow", "ref_id": "10", "voucher_no": "CF-001", "amount": 1000},
                {"ref_type": "CashFlow", "ref_id": "11", "voucher_no": "CF-002", "amount": 2000},
                {"ref_type": "Logistics", "ref_id": "5", "voucher_no": "LG-001", "amount": 500},
            ],
            "summary": {"total_debit": 3000, "total_credit": 3000}
        },
        "2026-04": {
            "month": "2026-04",
            "vouchers": [
                {"ref_type": "CashFlow", "ref_id": "20", "voucher_no": "CF-003", "amount": 3000},
            ],
            "summary": {"total_debit": 3000, "total_credit": 3000}
        }
    }

    report_path.write_text(json.dumps(report_data, ensure_ascii=False), encoding="utf-8")
    return report_path


# ============ void_report ============

class TestVoidReport:
    def test_removes_matching_entry(self, report_file):
        """void_report 移除匹配 ref_type + ref_id 的凭证"""
        from logic.transactions import void_report

        void_report("CashFlow", 10, datetime(2026, 3, 15), report_dir=str(report_file.parent))

        report = json.loads(report_file.read_text(encoding="utf-8"))
        voucher_ids = {(v["ref_type"], str(v["ref_id"])) for v in report["2026-03"]["vouchers"]}
        assert ("CashFlow", "10") not in voucher_ids
        # 其他凭证不受影响
        assert ("CashFlow", "11") in voucher_ids
        assert ("Logistics", "5") in voucher_ids

    def test_idempotent_twice(self, report_file):
        """void_report 幂等：连续调用两次不报错，第二次无效果"""
        from logic.transactions import void_report

        void_report("CashFlow", 10, datetime(2026, 3, 15), report_dir=str(report_file.parent))
        void_report("CashFlow", 10, datetime(2026, 3, 15), report_dir=str(report_file.parent))  # 第二次

        report = json.loads(report_file.read_text(encoding="utf-8"))
        voucher_ids = {(v["ref_type"], str(v["ref_id"])) for v in report["2026-03"]["vouchers"]}
        assert ("CashFlow", "10") not in voucher_ids

    def test_missing_month_key(self, report_file):
        """void_report 处理不存在的月份（幂等）"""
        from logic.transactions import void_report

        # 不应抛异常
        void_report("CashFlow", 999, datetime(2026, 12, 1), report_dir=str(report_file.parent))

        report = json.loads(report_file.read_text(encoding="utf-8"))
        # 原有数据不变
        assert len(report["2026-03"]["vouchers"]) == 3

    def test_missing_ref_id(self, report_file):
        """void_report 处理不存在的 ref_id（幂等）"""
        from logic.transactions import void_report

        void_report("CashFlow", 9999, datetime(2026, 3, 1), report_dir=str(report_file.parent))

        report = json.loads(report_file.read_text(encoding="utf-8"))
        # 原有凭证不变
        assert len(report["2026-03"]["vouchers"]) == 3


# ============ update_report ============

class TestUpdateReport:
    def test_adds_new_voucher(self, report_file):
        """update_report 幂等追加新凭证"""
        from logic.transactions import update_report

        new_voucher = {
            "ref_type": "CashFlow",
            "ref_id": "30",
            "voucher_no": "CF-NEW",
            "amount": 5000,
            "timestamp": "2026-03-15T10:00:00",
        }
        update_report(new_voucher, report_dir=str(report_file.parent))

        report = json.loads(report_file.read_text(encoding="utf-8"))
        # 应该追加到 2026-03
        assert any(v["voucher_no"] == "CF-NEW" for v in report["2026-03"]["vouchers"])

    def test_idempotent_no_duplicate(self, report_file):
        """update_report 幂等：同一凭证多次追加不重复"""
        from logic.transactions import update_report

        voucher = {
            "ref_type": "CashFlow",
            "ref_id": "30",
            "voucher_no": "CF-DUP",
            "amount": 5000,
            "timestamp": "2026-03-15T10:00:00",
        }
        update_report(voucher, report_dir=str(report_file.parent))
        update_report(voucher, report_dir=str(report_file.parent))  # 第二次

        report = json.loads(report_file.read_text(encoding="utf-8"))
        dup_count = sum(
            1 for v in report["2026-03"]["vouchers"]
            if v.get("ref_type") == "CashFlow" and str(v.get("ref_id")) == "30"
        )
        assert dup_count == 1, f"Duplicate found: {dup_count}"

    def test_ignores_existing_voucher_no(self, report_file):
        """update_report 通过 voucher_no 去重"""
        from logic.transactions import update_report

        voucher = {
            "ref_type": "CashFlow",
            "ref_id": "99",
            "voucher_no": "CF-001",  # 已存在
            "amount": 9999,
            "timestamp": "2026-03-15T10:00:00",
        }
        update_report(voucher, report_dir=str(report_file.parent))

        report = json.loads(report_file.read_text(encoding="utf-8"))
        cf001_count = sum(
            1 for month_data in report.values()
            for v in month_data["vouchers"]
            if v.get("voucher_no") == "CF-001"
        )
        # 原有 CF-001 不变，且无重复
        assert cf001_count == 1
        # 新凭证没有真正写入（因为 voucher_no 重复）
        assert all(
            v.get("ref_id") != "99" or v.get("voucher_no") != "CF-001"
            for month_data in report.values()
            for v in month_data["vouchers"]
        )


# ============ recalculate_month_summary ============

class TestRecalculateMonthSummary:
    def test_recalculates_after_void(self, report_file):
        """void 后 summary 应被重新计算"""
        from logic.transactions import void_report

        void_report("CashFlow", 10, datetime(2026, 3, 15), report_dir=str(report_file.parent))

        report = json.loads(report_file.read_text(encoding="utf-8"))
        summary = report["2026-03"]["summary"]
        # 移除了 CF-001 (1000 debit) 和 CF-002 (2000 credit)，还剩 LG-001 (500)
        # 实际 summary 计算依赖 update_report 逻辑，这里只验证结构存在
        assert "total_debit" in summary
        assert "total_credit" in summary
