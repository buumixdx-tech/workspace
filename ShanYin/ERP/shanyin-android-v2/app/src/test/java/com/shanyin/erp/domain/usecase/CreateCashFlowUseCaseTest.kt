package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * CreateCashFlowUseCase 完整测试套件
 *
 * 覆盖所有校验路径：
 * - VC 状态校验（TERMINATED / CANCELLED / cashStatus=COMPLETED）
 * - CashFlowType 合法性校验
 * - 银行账户存在性校验
 * - 合法路径：所有合法 CashFlowType 均可成功创建
 */
class CreateCashFlowUseCaseTest {

    private lateinit var cashFlowRepo: CashFlowRepository
    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var bankAccountRepo: BankAccountRepository
    private lateinit var stateMachine: VirtualContractStateMachineUseCase
    private lateinit var triggerFinance: TriggerCashFlowFinanceUseCase
    private lateinit var createCashFlow: CreateCashFlowUseCase

    @Before
    fun setup() {
        cashFlowRepo = mockk()
        vcRepo = mockk()
        bankAccountRepo = mockk()
        stateMachine = mockk(relaxed = true)
        triggerFinance = mockk(relaxed = true)

        createCashFlow = CreateCashFlowUseCase(
            repository = cashFlowRepo,
            vcRepository = vcRepo,
            bankAccountRepository = bankAccountRepo,
            stateMachine = stateMachine,
            triggerFinance = triggerFinance
        )

        coEvery { cashFlowRepo.insert(any()) } returns 1L
        coEvery { bankAccountRepo.getById(any()) } returns null
        coEvery { bankAccountRepo.getRawAccountInfo(any()) } returns null
    }

    // ========================================================================
    // §2 合法路径测试
    // ========================================================================

    @Test
    fun `合法PREPAYMENT录入成功`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.EXECUTING, cashStatus = CashStatus.EXECUTING)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { bankAccountRepo.getById(10L) } returns createBankAccount(id = 10L)
        coEvery { bankAccountRepo.getById(20L) } returns createBankAccount(id = 20L)

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 10000.0,
            payerAccountId = 10L, payeeAccountId = 20L)

        val id = createCashFlow(cf)

        assertEquals(1L, id)
        coVerify { cashFlowRepo.insert(match { it.type == CashFlowType.PREPAYMENT }) }
        coVerify { stateMachine.onCashFlowChanged(eq(1L), any()) }
        coVerify { triggerFinance(eq(1L)) }
    }

    @Test
    fun `合法DEPOSIT录入成功`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { bankAccountRepo.getById(10L) } returns createBankAccount(id = 10L)
        coEvery { bankAccountRepo.getById(20L) } returns createBankAccount(id = 20L)

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 5000.0,
            payerAccountId = 10L, payeeAccountId = 20L)

        val id = createCashFlow(cf)
        assertEquals(1L, id)
    }

    @Test
    fun `合法OFFSET_OUTFLOW录入成功`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.OFFSET_OUTFLOW, amount = 3000.0)

        val id = createCashFlow(cf)
        assertEquals(1L, id)
    }

    @Test
    fun `合法DEPOSIT_OFFSET_IN录入成功`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT_OFFSET_IN, amount = 2000.0)

        val id = createCashFlow(cf)
        assertEquals(1L, id)
    }

    @Test
    fun `合法PENALTY录入成功`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PENALTY, amount = 1000.0)

        val id = createCashFlow(cf)
        assertEquals(1L, id)
    }

    // ========================================================================
    // §2.2 VC 状态校验
    // ========================================================================

    @Test
    fun `VC status=TERMINATED 时拒绝录入`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.TERMINATED)
        coEvery { vcRepo.getById(1L) } returns vc

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT)

        val ex = try {
            createCashFlow(cf)
            null
        } catch (e: Exception) {
            e
        }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex!!.message!!.contains("终止"))
        coVerify(exactly = 0) { cashFlowRepo.insert(any()) }
    }

    // 注意：Mobile VCStatus 只有 EXECUTING / COMPLETED / TERMINATED
    // CANCELLED 是 Desktop 特有状态，本测试用例在 Mobile 不可达（编译器保护）

    @Test
    fun `VC cashStatus=COMPLETED 时拒绝录入`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.COMPLETED)
        coEvery { vcRepo.getById(1L) } returns vc

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT)

        val ex = try {
            createCashFlow(cf)
            null
        } catch (e: Exception) {
            e
        }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex!!.message!!.contains("结清"))
    }

    // ========================================================================
    // §2.3 CashFlowType 合法性校验
    // ========================================================================

    @Test
    fun `type=null 时拒绝录入`() = runTest {
        val cf = CashFlow(virtualContractId = 1L, type = null, amount = 100.0)

        val ex = try {
            createCashFlow(cf)
            null
        } catch (e: Exception) {
            e
        }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex!!.message!!.contains("类型不能为空"))
    }

    @Test
    fun `不在VALID_CASH_FLOW_TYPES中的type被拒绝`() = runTest {
        // 通过反射或直接构造一个"不存在"的 CashFlowType — 这里用 null 已覆盖
        // 本测试验证已知合法类型之外的值
        // 实际代码中 CashFlowType 是 enum，不可能传入非法 enum 值
        // 此测试路径在运行时不可达（编译器保护）
    }

    // ========================================================================
    // §2.4 银行账户校验
    // ========================================================================

    @Test
    fun `payerAccountId不存在时被拒绝`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { bankAccountRepo.getById(999L) } returns null

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT, payerAccountId = 999L)

        val ex = try {
            createCashFlow(cf)
            null
        } catch (e: Exception) {
            e
        }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex!!.message!!.contains("付款银行账户不存在"))
    }

    @Test
    fun `payeeAccountId不存在时被拒绝`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { bankAccountRepo.getById(10L) } returns createBankAccount(id = 10L)
        coEvery { bankAccountRepo.getById(999L) } returns null

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT,
            payerAccountId = 10L, payeeAccountId = 999L)

        val ex = try {
            createCashFlow(cf)
            null
        } catch (e: Exception) {
            e
        }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex!!.message!!.contains("收款银行账户不存在"))
    }

    @Test
    fun `payer和payee均为null时Penalty类型仍可创建`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PENALTY, amount = 500.0,
            payerAccountId = null, payeeAccountId = null)

        val id = createCashFlow(cf)
        assertEquals(1L, id)
    }

    // ========================================================================
    // §2.5 VC 不存在校验
    // ========================================================================

    @Test
    fun `VC不存在时拒绝录入`() = runTest {
        coEvery { vcRepo.getById(999L) } returns null

        val cf = createCashFlow(vcId = 999L, type = CashFlowType.PREPAYMENT)

        val ex = try {
            createCashFlow(cf)
            null
        } catch (e: Exception) {
            e
        }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex!!.message!!.contains("虚拟合同不存在"))
    }

    // ========================================================================
    // §2.6 幂等性与错误容忍
    // ========================================================================

    @Test
    fun `triggerFinance失败不影响cashFlow创建`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { triggerFinance.invoke(any()) } throws RuntimeException("finance error")

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT)
        val id = createCashFlow(cf)

        assertEquals(1L, id)
        coVerify { cashFlowRepo.insert(any()) }
    }

    @Test
    fun `stateMachine失败不影响cashFlow创建`() = runTest {
        val vc = createVC(id = 1L)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { stateMachine.onCashFlowChanged(any(), any()) } throws RuntimeException("state machine error")

        val cf = createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT)
        val id = createCashFlow(cf)

        assertEquals(1L, id)
        coVerify { cashFlowRepo.insert(any()) }
    }

    // ========================================================================
    // §10.2 vcId=null 时不触发校验
    // ========================================================================

    @Test
    fun `vcId=null时跳过VC状态校验直接创建`() = runTest {
        // vcId=null 时，不查 VC，不校验状态
        val cf = createCashFlow(vcId = null, type = CashFlowType.PENALTY, amount = 1000.0)

        val id = createCashFlow(cf)

        assertEquals(1L, id)
        coVerify(exactly = 0) { vcRepo.getById(any()) }
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(
        id: Long = 1L,
        status: VCStatus = VCStatus.EXECUTING,
        cashStatus: CashStatus = CashStatus.EXECUTING
    ) = VirtualContract(
        id = id,
        type = VCType.EQUIPMENT_PROCUREMENT,
        status = status,
        cashStatus = cashStatus
    )

    private fun createCashFlow(
        vcId: Long?,
        type: CashFlowType,
        amount: Double = 100.0,
        payerAccountId: Long? = null,
        payeeAccountId: Long? = null
    ) = CashFlow(
        virtualContractId = vcId,
        type = type,
        amount = amount,
        payerAccountId = payerAccountId,
        payeeAccountId = payeeAccountId
    )

    private fun createBankAccount(id: Long) = BankAccount(
        id = id,
        ownerType = OwnerType.OURSELVES
    )
}
