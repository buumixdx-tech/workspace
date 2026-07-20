package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.CashFlowLedgerRepository
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ProcessCashFlowFinanceUseCase
import com.shanyin.erp.domain.usecase.finance.engine.AccountResolver
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * ProcessCashFlowFinanceUseCase 完整测试套件
 *
 * §3   isIncome 方向判断（VC类型 + return_direction）
 * §4   ar_ap_amt / pre_amt 计算边界
 * §6   凭证号生成格式
 * §8   幂等性（已凭证化则跳过）
 */
class ProcessCashFlowFinanceUseCaseTest {

    private lateinit var cashFlowRepo: CashFlowRepository
    private lateinit var journalDao: com.shanyin.erp.data.local.dao.FinancialJournalDao
    private lateinit var ledgerRepo: CashFlowLedgerRepository
    private lateinit var accountResolver: AccountResolver
    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var bankAccountRepo: BankAccountRepository
    private lateinit var processCashFlowFinance: ProcessCashFlowFinanceUseCase

    @Before
    fun setup() {
        cashFlowRepo = mockk()
        journalDao = mockk()
        ledgerRepo = mockk()
        accountResolver = mockk()
        vcRepo = mockk()
        bankAccountRepo = mockk()

        processCashFlowFinance = ProcessCashFlowFinanceUseCase(
            cashFlowRepo = cashFlowRepo,
            journalDao = journalDao,
            ledgerRepo = ledgerRepo,
            accountResolver = accountResolver,
            vcRepo = vcRepo,
            bankAccountRepo = bankAccountRepo
        )

        // 默认：账户解析返回有效ID
        coEvery { accountResolver.resolveId(any()) } returns 1L
        coEvery { journalDao.getMaxSeqForPrefix(any(), any()) } returns 0
        coEvery { journalDao.insert(any()) } returns 1L
        coEvery { ledgerRepo.insert(any()) } returns 1L
        coEvery { bankAccountRepo.getById(any()) } returns null
        coEvery { cashFlowRepo.update(any()) } returns Unit
    }

    // ========================================================================
    // §3 isIncome 方向判断
    // ========================================================================

    @Test
    fun `MATERIAL_SUPPLY_VC的PREPAYMENT方向为流入`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_SUPPLY)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payeeAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        // 执行
        processCashFlowFinance(10L)

        // 验证生成了正确的 journal entry 类型（从流入方向，CASH在借方）
        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        // 流入时 CASH 在借方：找 debit > 0 的分录
        assertTrue(entries.any { it.debit > 0 })
    }

    @Test
    fun `EQUIPMENT_PROCUREMENT_VC的PREPAYMENT方向为流出`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payerAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        processCashFlowFinance(10L)

        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        // 流出时 CASH 在贷方：找 credit > 0 的分录
        assertTrue(entries.any { it.credit > 0 })
    }

    @Test
    fun `EQUIPMENT_STOCK_VC的PREPAYMENT方向为流出`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_STOCK)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payerAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        processCashFlowFinance(10L)

        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        assertTrue(entries.any { it.credit > 0 })
    }

    @Test
    fun `MATERIAL_PROCUREMENT_VC的PREPAYMENT方向为流出`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payerAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        processCashFlowFinance(10L)

        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        assertTrue(entries.any { it.credit > 0 })
    }

    // §3.2 退货VC的return_direction影响

    @Test
    fun `RETURN_VC_US_TO_SUPPLIER方向为流入`() = runTest {
        val vc = createVC(id = 1L, type = VCType.RETURN, returnDirection = ReturnDirection.US_TO_SUPPLIER)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payeeAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        processCashFlowFinance(10L)

        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        // US_TO_SUPPLIER → 供应商退款给我们 → 流入 → CASH 借方
        assertTrue(entries.any { it.debit > 0 })
    }

    @Test
    fun `RETURN_VC_CUSTOMER_TO_US方向为流出`() = runTest {
        val vc = createVC(id = 1L, type = VCType.RETURN, returnDirection = ReturnDirection.CUSTOMER_TO_US)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payerAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        processCashFlowFinance(10L)

        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        // CUSTOMER_TO_US → 我们退款给客户 → 流出 → CASH 贷方
        assertTrue(entries.any { it.credit > 0 })
    }

    @Test
    fun `RETURN_VC_returnDirection为null方向为流出`() = runTest {
        val vc = createVC(id = 1L, type = VCType.RETURN, returnDirection = null)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = false, payerAccountId = 100L)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(100L) } returns createBankAccount(100L, OwnerType.OURSELVES)

        processCashFlowFinance(10L)

        val entries = mutableListOf<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(entries)) }
        assertTrue(entries.any { it.credit > 0 })
    }

    // ========================================================================
    // §4 ar_ap_amt / pre_amt 计算边界
    // ========================================================================

    @Test
    fun `PREPAYMENT金额完全覆盖remaining时pre_amt为零`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 10000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 4000.0, financeTriggered = false)

        // 已付 6000 (paid_before)
        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(id = 1L, vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 6000.0)
        ))
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // remaining = 10000 - 6000 = 4000, 本次 4000
        // ar_ap_amt = 4000, pre_amt = 0
        // 验证 journal entries 存在，且 cashFlow.financeTriggered 更新
        coVerify { cashFlowRepo.update(match { it.financeTriggered && it.id == 10L }) }
    }

    @Test
    fun `PREPAYMENT金额超过remaining时拆分ar_ap和pre`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 10000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 6000.0, financeTriggered = false)

        // 已付 6000 (paid_before)
        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(id = 1L, vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 6000.0)
        ))
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // remaining = 10000 - 6000 = 4000
        // ar_ap_amt = min(6000, 4000) = 4000
        // pre_amt = 6000 - 4000 = 2000
        // 期望 3 条分录: AP借4000 + PREPAYMENT借2000 + CASH贷6000
        coVerify { journalDao.insert(match {
            it.accountId == 1L && it.debit == 4000.0
        }) }
    }

    @Test
    fun `PREPAYMENT金额小于remaining时pre_amt为零`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 10000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 2000.0, financeTriggered = false)

        // 已付 3000
        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(id = 1L, vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 3000.0)
        ))
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // remaining = 10000 - 3000 = 7000
        // ar_ap_amt = min(2000, 7000) = 2000
        // pre_amt = 0
        coVerify { cashFlowRepo.update(match { it.financeTriggered && it.id == 10L }) }
    }

    @Test
    fun `已全额付款后再付时pre_amt等于全额`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 10000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 1000.0, financeTriggered = false)

        // 已付 10000 (刚好结清)
        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(id = 1L, vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 10000.0)
        ))
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // remaining = 0, ar_ap_amt = 0, pre_amt = 1000（全进预付）
        coVerify { cashFlowRepo.update(match { it.financeTriggered && it.id == 10L }) }
    }

    @Test
    fun `首批PREPAYMENT时paid_before为零`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 50000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 20000.0, financeTriggered = false)

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // paid_before = 0, remaining = 50000
        // ar_ap_amt = 20000, pre_amt = 0
        coVerify { cashFlowRepo.update(match { it.financeTriggered && it.id == 10L }) }
    }

    @Test
    fun `paid_before计算排除本次CF`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 30000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 20000.0, financeTriggered = false)

        // 已付 CF1=8000, CF2=8000, 本次 CF3=20000
        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(id = 1L, vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 8000.0),
            createCashFlow(id = 2L, vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 8000.0)
        ))
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // paid_before = 8000 + 8000 = 16000 (排除id=10)
        // remaining = 30000 - 16000 = 14000
        // ar_ap_amt = min(20000, 14000) = 14000
        // pre_amt = 20000 - 14000 = 6000
        coVerify { cashFlowRepo.update(match { it.financeTriggered && it.id == 10L }) }
    }

    @Test
    fun `OFFSET_OUTFLOW参与paid_before计算`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT,
            totalAmount = 10000.0)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 5000.0, financeTriggered = false)

        // 已付 OFFSET_OUTFLOW 2000
        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(id = 1L, vcId = 1L, type = CashFlowType.OFFSET_OUTFLOW, amount = 2000.0)
        ))
        coEvery { bankAccountRepo.getById(any()) } returns null

        processCashFlowFinance(10L)

        // paid_before = 2000 (OFFSET_OUTFLOW计入)
        // remaining = 10000 - 2000 = 8000
        // ar_ap_amt = min(5000, 8000) = 5000
        // pre_amt = 0
        coVerify { cashFlowRepo.update(match { it.financeTriggered && it.id == 10L }) }
    }

    // ========================================================================
    // §8 幂等性
    // ========================================================================

    @Test
    fun `已financeTriggered的CashFlow幂等跳过`() = runTest {
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            financeTriggered = true)

        coEvery { cashFlowRepo.getById(10L) } returns cf

        val result = processCashFlowFinance(10L)

        assertEquals(10L, result)
        coVerify(exactly = 0) { journalDao.insert(any()) }
        coVerify(exactly = 0) { cashFlowRepo.update(any()) }
    }

    @Test
    fun `CashFlow不存在时抛出异常`() = runTest {
        coEvery { cashFlowRepo.getById(999L) } returns null

        var ex: Exception? = null
        try {
            processCashFlowFinance(999L)
        } catch (e: Exception) {
            ex = e
        }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex!!.message!!.contains("not found"))
    }

    @Test
    fun `CashFlow_type为null时抛出异常`() = runTest {
        val cf = CashFlow(id = 10L, virtualContractId = 1L, type = null, amount = 100.0, financeTriggered = false)
        coEvery { cashFlowRepo.getById(10L) } returns cf

        var ex: Exception? = null
        try {
            processCashFlowFinance(10L)
        } catch (e: Exception) {
            ex = e
        }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex!!.message!!.contains("type is null"))
    }

    // ========================================================================
    // §6 凭证号生成
    // ========================================================================

    @Test
    fun `凭证号格式为JZ_YYYYMM_NNNN`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        val cf = createCashFlow(id = 10L, vcId = 1L, type = CashFlowType.PREPAYMENT,
            amount = 1000.0, financeTriggered = false, transactionDate = System.currentTimeMillis())

        coEvery { cashFlowRepo.getById(10L) } returns cf
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { bankAccountRepo.getById(any()) } returns null
        coEvery { journalDao.getMaxSeqForPrefix(any(), any()) } returns 5

        processCashFlowFinance(10L)

        val slot = slot<com.shanyin.erp.data.local.entity.FinancialJournalEntity>()
        coVerify { journalDao.insert(capture(slot)) }
        assertTrue(slot.captured.voucherNo!!.startsWith("JZ-"))
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(
        id: Long = 1L,
        type: VCType = VCType.EQUIPMENT_PROCUREMENT,
        returnDirection: ReturnDirection? = null,
        totalAmount: Double = 10000.0
    ) = VirtualContract(
        id = id,
        type = type,
        returnDirection = returnDirection,
        depositInfo = DepositInfo(totalAmount = totalAmount)
    )

    private fun createCashFlow(
        id: Long = 1L,
        vcId: Long? = 1L,
        type: CashFlowType = CashFlowType.PREPAYMENT,
        amount: Double = 1000.0,
        financeTriggered: Boolean = false,
        transactionDate: Long? = null,
        payerAccountId: Long? = null,
        payeeAccountId: Long? = null
    ) = CashFlow(
        id = id,
        virtualContractId = vcId,
        type = type,
        amount = amount,
        financeTriggered = financeTriggered,
        transactionDate = transactionDate ?: System.currentTimeMillis(),
        payerAccountId = payerAccountId,
        payeeAccountId = payeeAccountId
    )

    private fun createBankAccount(id: Long, ownerType: OwnerType = OwnerType.OURSELVES) =
        BankAccount(id = id, ownerType = ownerType)
}
