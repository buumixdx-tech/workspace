package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.CashFlowType
import com.shanyin.erp.domain.usecase.finance.engine.AccountConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AccountConfig.getJournalEntries 完整测试套件
 *
 * 覆盖所有 CashFlowType 的所有 isIncome 分支：
 * §5.1  PREPAYMENT  流出/流入
 * §5.3  PERFORMANCE 流出/流入
 * §5.4  DEPOSIT     流入/流出
 * §5.5  DEPOSIT_REFUND 流入/流出
 * §5.6  REFUND      流入/流出
 * §5.7  PENALTY     流入/流出
 * §5.8  OFFSET_OUTFLOW 流入/流出
 * §5.9  OFFSET_INFLOW  流入/流出
 * §5.10 DEPOSIT_OFFSET_IN（应返回空）
 *
 * §10.3 借贷平衡校验（所有生成的 JournalEntryGroup）
 */
class AccountConfigTest {

    // ========================================================================
    // §5.1 PREPAYMENT
    // ========================================================================

    @Test
    fun `PREPAYMENT流出有ar_ap和pre_amt生成3条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PREPAYMENT,
            amount = 10000.0,
            isIncome = false,
            arApAmount = 6000.0,
            preAmount = 4000.0,
            cpType = "SUPPLIER",
            cpId = 1L,
            bankAccountId = 100L
        )

        assertEquals(3, group.entries.size)
        assertEquals(false, group.isIncome)

        // 借贷平衡
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(10000.0, totalDebit, 0.001)
        assertEquals(10000.0, totalCredit, 0.001)

        // AP借方
        assertEquals(AccountConfig.AP_EQUIPMENT, group.entries[0].account)
        assertEquals(6000.0, group.entries[0].debit, 0.001)
        assertEquals(0.0, group.entries[0].credit, 0.001)

        // PREPAYMENT借方
        assertEquals(AccountConfig.PREPAYMENT, group.entries[1].account)
        assertEquals(4000.0, group.entries[1].debit, 0.001)

        // CASH贷方
        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[2].account)
        assertEquals(0.0, group.entries[2].debit, 0.001)
        assertEquals(10000.0, group.entries[2].credit, 0.001)
    }

    @Test
    fun `PREPAYMENT流出只有ar_ap_amt生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PREPAYMENT,
            amount = 5000.0,
            isIncome = false,
            arApAmount = 5000.0,
            preAmount = 0.0,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(5000.0, totalDebit, 0.001)
        assertEquals(5000.0, totalCredit, 0.001)
    }

    @Test
    fun `PREPAYMENT流出只有pre_amt生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PREPAYMENT,
            amount = 3000.0,
            isIncome = false,
            arApAmount = 0.0,
            preAmount = 3000.0,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        assertEquals(AccountConfig.PREPAYMENT, group.entries[0].account)
        assertEquals(3000.0, group.entries[0].debit, 0.001)
        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[1].account)
        assertEquals(3000.0, group.entries[1].credit, 0.001)
    }

    @Test
    fun `PREPAYMENT流入有ar_ap和pre_amt生成3条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PREPAYMENT,
            amount = 10000.0,
            isIncome = true,
            arApAmount = 6000.0,
            preAmount = 4000.0,
            cpType = "CUSTOMER",
            cpId = 2L,
            bankAccountId = 100L
        )

        assertEquals(3, group.entries.size)
        assertEquals(true, group.isIncome)

        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(10000.0, totalDebit, 0.001)
        assertEquals(10000.0, totalCredit, 0.001)

        // CASH借方
        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[0].account)
        assertEquals(10000.0, group.entries[0].debit, 0.001)

        // AR贷方
        assertEquals(AccountConfig.AR_CUSTOMER, group.entries[1].account)
        assertEquals(6000.0, group.entries[1].credit, 0.001)

        // PRE_COLLECTION贷方
        assertEquals(AccountConfig.PRE_COLLECTION, group.entries[2].account)
        assertEquals(4000.0, group.entries[2].credit, 0.001)
    }

    // ========================================================================
    // §5.3 PERFORMANCE
    // ========================================================================

    @Test
    fun `PERFORMANCE流出生成正确分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PERFORMANCE,
            amount = 8000.0,
            isIncome = false,
            arApAmount = 8000.0,
            preAmount = 0.0,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(8000.0, totalDebit, 0.001)
        assertEquals(8000.0, totalCredit, 0.001)
    }

    @Test
    fun `PERFORMANCE流入生成正确分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PERFORMANCE,
            amount = 8000.0,
            isIncome = true,
            arApAmount = 8000.0,
            preAmount = 0.0,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(8000.0, totalDebit, 0.001)
        assertEquals(8000.0, totalCredit, 0.001)
    }

    // ========================================================================
    // §5.4 DEPOSIT
    // ========================================================================

    @Test
    fun `DEPOSIT流入生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.DEPOSIT,
            amount = 5000.0,
            isIncome = true,
            cpType = "CUSTOMER",
            cpId = 1L,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(5000.0, totalDebit, 0.001)
        assertEquals(5000.0, totalCredit, 0.001)

        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[0].account)
        assertEquals(5000.0, group.entries[0].debit, 0.001)

        assertEquals(AccountConfig.DEPOSIT_PAYABLE, group.entries[1].account)
        assertEquals(5000.0, group.entries[1].credit, 0.001)
    }

    @Test
    fun `DEPOSIT流出生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.DEPOSIT,
            amount = 5000.0,
            isIncome = false,
            cpType = "SUPPLIER",
            cpId = 1L,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(5000.0, totalDebit, 0.001)
        assertEquals(5000.0, totalCredit, 0.001)

        assertEquals("其他应收款-押金", group.entries[0].account)
        assertEquals(5000.0, group.entries[0].debit, 0.001)
    }

    // ========================================================================
    // §5.5 DEPOSIT_REFUND
    // ========================================================================

    @Test
    fun `DEPOSIT_REFUND流入生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.DEPOSIT_REFUND,
            amount = 3000.0,
            isIncome = true,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(3000.0, totalDebit, 0.001)
        assertEquals(3000.0, totalCredit, 0.001)
    }

    @Test
    fun `DEPOSIT_REFUND流出生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.DEPOSIT_REFUND,
            amount = 3000.0,
            isIncome = false,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(3000.0, totalDebit, 0.001)
        assertEquals(3000.0, totalCredit, 0.001)

        assertEquals(AccountConfig.DEPOSIT_PAYABLE, group.entries[0].account)
        assertEquals(3000.0, group.entries[0].debit, 0.001)
    }

    // ========================================================================
    // §5.6 REFUND
    // ========================================================================

    @Test
    fun `REFUND流入生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.REFUND,
            amount = 2000.0,
            isIncome = true,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(2000.0, totalDebit, 0.001)
        assertEquals(2000.0, totalCredit, 0.001)

        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[0].account)
        assertEquals(2000.0, group.entries[0].debit, 0.001)
        assertEquals(AccountConfig.AP_EQUIPMENT, group.entries[1].account)
        assertEquals(2000.0, group.entries[1].credit, 0.001)
    }

    @Test
    fun `REFUND流出生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.REFUND,
            amount = 1500.0,
            isIncome = false,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(1500.0, totalDebit, 0.001)
        assertEquals(1500.0, totalCredit, 0.001)

        assertEquals(AccountConfig.AR_CUSTOMER, group.entries[0].account)
        assertEquals(1500.0, group.entries[0].debit, 0.001)
    }

    // ========================================================================
    // §5.7 PENALTY
    // ========================================================================

    @Test
    fun `PENALTY流入生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PENALTY,
            amount = 1000.0,
            isIncome = true,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(1000.0, totalDebit, 0.001)
        assertEquals(1000.0, totalCredit, 0.001)

        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[0].account)
        assertEquals(1000.0, group.entries[0].debit, 0.001)
        assertEquals(AccountConfig.NON_OP_REVENUE_PENALTY, group.entries[1].account)
        assertEquals(1000.0, group.entries[1].credit, 0.001)
    }

    @Test
    fun `PENALTY流出生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PENALTY,
            amount = 800.0,
            isIncome = false,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(800.0, totalDebit, 0.001)
        assertEquals(800.0, totalCredit, 0.001)

        assertEquals(AccountConfig.NON_OP_COST_PENALTY, group.entries[0].account)
        assertEquals(800.0, group.entries[0].debit, 0.001)
    }

    // ========================================================================
    // §5.8 OFFSET_OUTFLOW
    // ========================================================================

    @Test
    fun `OFFSET_OUTFLOW流出isIncome_false生成2条分录无CASH`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.OFFSET_OUTFLOW,
            amount = 5000.0,
            isIncome = false,
            cpType = "SUPPLIER",
            cpId = 1L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(5000.0, totalDebit, 0.001)
        assertEquals(5000.0, totalCredit, 0.001)

        // 无 BANK_DEFAULT 分录（纯内部核销）
        assertTrue(group.entries.none { it.account == AccountConfig.BANK_DEFAULT })

        assertEquals(AccountConfig.AP_EQUIPMENT, group.entries[0].account)
        assertEquals(5000.0, group.entries[0].debit, 0.001)
        assertEquals(AccountConfig.PREPAYMENT, group.entries[1].account)
        assertEquals(5000.0, group.entries[1].credit, 0.001)
    }

    @Test
    fun `OFFSET_OUTFLOW流入isIncome_true生成2条分录无CASH`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.OFFSET_OUTFLOW,
            amount = 3000.0,
            isIncome = true,
            cpType = "CUSTOMER",
            cpId = 2L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(3000.0, totalDebit, 0.001)
        assertEquals(3000.0, totalCredit, 0.001)

        assertTrue(group.entries.none { it.account == AccountConfig.BANK_DEFAULT })

        assertEquals(AccountConfig.PRE_COLLECTION, group.entries[0].account)
        assertEquals(3000.0, group.entries[0].debit, 0.001)
        assertEquals(AccountConfig.AR_CUSTOMER, group.entries[1].account)
        assertEquals(3000.0, group.entries[1].credit, 0.001)
    }

    // ========================================================================
    // §5.9 OFFSET_INFLOW
    // ========================================================================

    @Test
    fun `OFFSET_INFLOW流入生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.OFFSET_INFLOW,
            amount = 4000.0,
            isIncome = true,
            cpType = "CUSTOMER",
            cpId = 2L,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(4000.0, totalDebit, 0.001)
        assertEquals(4000.0, totalCredit, 0.001)

        assertEquals(AccountConfig.BANK_DEFAULT, group.entries[0].account)
        assertEquals(4000.0, group.entries[0].debit, 0.001)
        assertEquals(AccountConfig.PRE_COLLECTION, group.entries[1].account)
        assertEquals(4000.0, group.entries[1].credit, 0.001)
    }

    @Test
    fun `OFFSET_INFLOW流出生成2条分录`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.OFFSET_INFLOW,
            amount = 4000.0,
            isIncome = false,
            cpType = "SUPPLIER",
            cpId = 1L,
            bankAccountId = 100L
        )

        assertEquals(2, group.entries.size)
        val totalDebit = group.entries.sumOf { it.debit }
        val totalCredit = group.entries.sumOf { it.credit }
        assertEquals(4000.0, totalDebit, 0.001)
        assertEquals(4000.0, totalCredit, 0.001)

        assertEquals(AccountConfig.PREPAYMENT, group.entries[0].account)
        assertEquals(4000.0, group.entries[0].debit, 0.001)
    }

    // ========================================================================
    // §5.10 DEPOSIT_OFFSET_IN（遗留行为：空分录）
    // ========================================================================

    @Test
    fun `DEPOSIT_OFFSET_IN生成空分录列表`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.DEPOSIT_OFFSET_IN,
            amount = 5000.0,
            isIncome = true
        )

        assertTrue(group.entries.isEmpty())
    }

    // ========================================================================
    // §10.3 借贷平衡全局校验
    // ========================================================================

    @Test
    fun `所有分支生成的分录均借贷平衡`() {
        val testCases = listOf(
            // type, amount, isIncome, arApAmount, preAmount, bankAccountId
            Triple(CashFlowType.PREPAYMENT, 10000.0, false),
            Triple(CashFlowType.PERFORMANCE, 8000.0, false),
            Triple(CashFlowType.DEPOSIT, 5000.0, true),
            Triple(CashFlowType.DEPOSIT_REFUND, 3000.0, true),
            Triple(CashFlowType.REFUND, 2000.0, true),
            Triple(CashFlowType.PENALTY, 1000.0, true),
            Triple(CashFlowType.OFFSET_INFLOW, 4000.0, true),
            Triple(CashFlowType.OFFSET_OUTFLOW, 5000.0, false),
        )

        for ((type, amount, isIncome) in testCases) {
            val arAp = if (isIncome) amount * 0.6 else amount * 0.6
            val pre = amount - arAp
            val group = AccountConfig.getJournalEntries(
                type = type,
                amount = amount,
                isIncome = isIncome,
                arApAmount = arAp,
                preAmount = pre,
                bankAccountId = 100L
            )

            val totalDebit = group.entries.sumOf { it.debit }
            val totalCredit = group.entries.sumOf { it.credit }
            assertEquals(
                "借贷不平衡: type=$type isIncome=$isIncome debit=$totalDebit credit=$totalCredit",
                totalDebit, totalCredit, 0.001
            )
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun `JournalEntry throws when both debit and credit are positive`() {
        AccountConfig.JournalEntry(
            account = "测试科目",
            debit = 100.0,
            credit = 50.0,
            summary = "这条分录应该抛出异常"
        )
    }

    @Test
    fun `amount为0时分录金额均为0`() {
        val group = AccountConfig.getJournalEntries(
            type = CashFlowType.PREPAYMENT,
            amount = 0.0,
            isIncome = true,
            arApAmount = 0.0,
            preAmount = 0.0,
            bankAccountId = 100L
        )

        assertTrue(group.entries.isNotEmpty())
        assertEquals(0.0, group.entries.sumOf { it.debit }, 0.001)
        assertEquals(0.0, group.entries.sumOf { it.credit }, 0.001)
    }
}
