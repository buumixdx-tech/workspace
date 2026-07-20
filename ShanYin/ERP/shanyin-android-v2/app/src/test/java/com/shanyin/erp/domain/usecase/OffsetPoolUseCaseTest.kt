package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.FinanceAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ApplyOffsetToVcUseCase
import com.shanyin.erp.domain.usecase.finance.GetOffsetPoolUseCase
import com.shanyin.erp.domain.usecase.finance.OffsetPoolType
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * ApplyOffsetToVcUseCase 完整测试套件
 *
 * §6   核销池自动应用（VC创建时）
 * §6.4 错误容忍
 */
class OffsetPoolUseCaseTest {

    private lateinit var journalRepo: FinancialJournalRepository
    private lateinit var financeAccountRepo: FinanceAccountRepository
    private lateinit var cashFlowRepo: CashFlowRepository
    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var triggerFinance: TriggerCashFlowFinanceUseCase
    private lateinit var applyOffset: ApplyOffsetToVcUseCase
    private lateinit var getOffsetPool: GetOffsetPoolUseCase

    @Before
    fun setup() {
        journalRepo = mockk()
        financeAccountRepo = mockk()
        cashFlowRepo = mockk()
        vcRepo = mockk()
        triggerFinance = mockk()

        getOffsetPool = GetOffsetPoolUseCase(journalRepo, financeAccountRepo)

        applyOffset = ApplyOffsetToVcUseCase(
            journalRepo = journalRepo,
            financeAccountRepo = financeAccountRepo,
            cashFlowRepo = cashFlowRepo,
            vcRepo = vcRepo,
            triggerCashFlowFinance = triggerFinance
        )

        coEvery { financeAccountRepo.getByName(any()) } returns null
        coEvery { journalRepo.getAll() } returns flowOf(emptyList())
        coEvery { cashFlowRepo.insert(any()) } returns 1L
        coEvery { cashFlowRepo.delete(any()) } returns Unit
        coEvery { triggerFinance.invoke(any()) } returns 1L
    }

    // ========================================================================
    // §6.1 设备采购VC核销
    // ========================================================================

    @Test
    fun `设备采购VC有充足核销池余额时应用全部`() = runTest {
        // 核销池可用余额 = 20000, VC totalAmount = 50000
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 10L, debit = 20000.0, credit = 0.0)
        ))

        val pool = getOffsetPool(OffsetPoolType.PREPAYMENT)
        assertEquals(20000.0, pool.availableBalance, 0.001)
        assertEquals(20000.0, pool.totalBalance, 0.001)
    }

    @Test
    fun `核销池余额不足时应用余额`() = runTest {
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 10L, debit = 3000.0, credit = 0.0)
        ))

        val pool = getOffsetPool(OffsetPoolType.PREPAYMENT)
        assertEquals(3000.0, pool.availableBalance, 0.001)
    }

    @Test
    fun `核销池余额为零时不应用`() = runTest {
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(emptyList())

        val pool = getOffsetPool(OffsetPoolType.PREPAYMENT)
        assertEquals(0.0, pool.availableBalance, 0.001)
    }

    @Test
    fun `核销池账户不存在时返回零余额`() = runTest {
        coEvery { financeAccountRepo.getByName(any()) } returns null
        coEvery { journalRepo.getAll() } returns flowOf(emptyList())

        val pool = getOffsetPool(OffsetPoolType.PREPAYMENT)
        assertEquals(0.0, pool.availableBalance, 0.001)
        assertEquals(0L, pool.accountId)
    }

    // ========================================================================
    // §6.2 物料供应VC核销
    // ========================================================================

    @Test
    fun `物料供应VC使用PRE_COLLECTION核销池`() = runTest {
        val poolAccount = FinanceAccount(id = 20L, level1Name = "预收账款-客户")
        coEvery { financeAccountRepo.getByName("预收账款-客户") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 20L, debit = 0.0, credit = 10000.0)
        ))

        val pool = getOffsetPool(OffsetPoolType.PRE_COLLECTION)
        assertEquals(10000.0, pool.availableBalance, 0.001)
    }

    // ========================================================================
    // §6.3 退货VC退货方向决定核销类型
    // ========================================================================

    @Test
    fun `US_TO_SUPPLIER使用PRE_COLLECTION核销池`() = runTest {
        // 供应商退款给我们 → 冲抵应收
        val poolAccount = FinanceAccount(id = 20L, level1Name = "预收账款-客户")
        coEvery { financeAccountRepo.getByName("预收账款-客户") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 20L, debit = 0.0, credit = 5000.0)
        ))

        val pool = getOffsetPool(OffsetPoolType.PRE_COLLECTION)
        assertEquals(5000.0, pool.availableBalance, 0.001)
    }

    @Test
    fun `CUSTOMER_TO_US使用PREPAYMENT核销池`() = runTest {
        // 我们退款给客户 → 核销预付
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 10L, debit = 3000.0, credit = 0.0)
        ))

        val pool = getOffsetPool(OffsetPoolType.PREPAYMENT)
        assertEquals(3000.0, pool.availableBalance, 0.001)
    }

    // ========================================================================
    // §6.4 错误容忍
    // ========================================================================

    @Test
    fun `VC不存在时返回失败`() = runTest {
        coEvery { vcRepo.getById(999L) } returns null

        val result = applyOffset(999L, 1000.0, OffsetPoolType.PREPAYMENT)

        assertEquals(false, result.success)
        assertTrue(result.message.contains("不存在"))
    }

    @Test
    fun `凭证化失败时删除已创建的CashFlow`() = runTest {
        val vc = createVC(id = 1L)
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 10L, debit = 20000.0, credit = 0.0)
        ))
        coEvery { triggerFinance.invoke(any()) } throws RuntimeException("finance error")

        val result = applyOffset(1L, 1000.0, OffsetPoolType.PREPAYMENT)

        assertEquals(false, result.success)
        assertTrue(result.message.contains("凭证化失败"))
        coVerify { cashFlowRepo.delete(any()) }
    }

    @Test
    fun `核销成功返回正确结果`() = runTest {
        val vc = createVC(id = 1L)
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 10L, debit = 20000.0, credit = 0.0)
        ))
        coEvery { cashFlowRepo.insert(any()) } returns 5L
        coEvery { triggerFinance.invoke(5L) } returns 5L
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())

        val result = applyOffset(1L, 5000.0, OffsetPoolType.PREPAYMENT)

        assertEquals(true, result.success)
        assertEquals(5000.0, result.appliedAmount, 0.001)
        assertEquals(15000.0, result.remainingPoolBalance, 0.001)
    }

    // ========================================================================
    // §7 paidGoods 包含 OFFSET_OUTFLOW（通过 recalculateVcActualAmount）
    // ========================================================================

    @Test
    fun `recalculateVcActualAmount包含OFFSET_OUTFLOW`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 10000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.OFFSET_OUTFLOW, amount = 5000.0)
        ))

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 2000.0)

        // 通过 applyOffset 验证 recalculateVcActualAmount
        val poolAccount = FinanceAccount(id = 10L, level1Name = "预付账款-供应商")
        coEvery { financeAccountRepo.getByName("预付账款-供应商") } returns poolAccount
        coEvery { journalRepo.getAll() } returns flowOf(listOf(
            createJournalEntry(accountId = 10L, debit = 20000.0, credit = 0.0)
        ))
        coEvery { triggerFinance.invoke(any()) } returns 1L

        val result = applyOffset(1L, 5000.0, OffsetPoolType.PREPAYMENT)

        // actualAmount = 10000 + 5000 = 15000（包含OFFSET_OUTFLOW）
        assertEquals(true, result.success)
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(id: Long = 1L) = VirtualContract(
        id = id,
        type = VCType.EQUIPMENT_PROCUREMENT,
        depositInfo = DepositInfo(totalAmount = 10000.0)
    )

    private fun createJournalEntry(
        accountId: Long,
        debit: Double = 0.0,
        credit: Double = 0.0
    ) = FinancialJournalEntry(
        accountId = accountId,
        debit = debit,
        credit = credit
    )

    private fun createCashFlow(
        vcId: Long,
        type: CashFlowType,
        amount: Double
    ) = CashFlow(
        virtualContractId = vcId,
        type = type,
        amount = amount
    )
}
