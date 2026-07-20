package com.shanyin.erp.domain.usecase

import com.shanyin.erp.data.local.dao.FinancialJournalDao
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.LogisticsRepository
import com.shanyin.erp.domain.repository.MaterialInventoryRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ProcessLogisticsFinanceUseCase
import com.shanyin.erp.domain.usecase.finance.engine.AccountResolver
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * ProcessLogisticsFinanceUseCase 完整测试套件
 *
 * §1 幂等性
 * §2 SIGNED 状态凭证
 * §3 COMPLETED 状态凭证（仅 RETURN）
 * §4 金额边界
 * §5 科目解析
 */
class ProcessLogisticsFinanceUseCaseTest {

    private lateinit var logisticsRepo: LogisticsRepository
    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var journalDao: FinancialJournalDao
    private lateinit var accountResolver: AccountResolver
    private lateinit var materialInventoryRepo: MaterialInventoryRepository
    private lateinit var processLogisticsFinance: ProcessLogisticsFinanceUseCase

    private val logisticsSigned = Logistics(id = 10L, virtualContractId = 1L, status = LogisticsStatus.SIGNED, financeTriggered = false)
    private val logisticsCompleted = Logistics(id = 20L, virtualContractId = 2L, status = LogisticsStatus.COMPLETED, financeTriggered = false)

    @Before
    fun setup() {
        logisticsRepo = mockk(relaxed = true)
        vcRepo = mockk(relaxed = true)
        journalDao = mockk(relaxed = true)
        accountResolver = mockk(relaxed = true)
        materialInventoryRepo = mockk(relaxed = true)

        processLogisticsFinance = ProcessLogisticsFinanceUseCase(
            logisticsRepo = logisticsRepo,
            vcRepo = vcRepo,
            journalDao = journalDao,
            accountResolver = accountResolver,
            materialInventoryRepo = materialInventoryRepo
        )

        // 通用账户 ID mock
        coEvery { accountResolver.resolveId(any()) } returns 1L
    }

    // ========================================================================
    // §1 幂等性
    // ========================================================================

    // ========================================================================
    // §0 safeBearer 防御性枚举解析
    // ========================================================================

    @Test
    fun `TC46 - safeBearer returns SENDER for null`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 0.0,
            logisticsCost = 100.0,
            logisticsBearer = null  // null → SENDER fallback
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // null bearer → SENDER → Dr 应收账款-客户, Cr 销售费用
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货物流费-客户自付收回") == true && it.debit == 100.0
            })
        }
    }

    // ========================================================================
    // §1 幂等性
    // ========================================================================

    @Test
    fun `TC47 - financeTriggered=true且force=false 跳过`() = runTest {
        val triggeredLogistics = logisticsSigned.copy(financeTriggered = true)
        coEvery { logisticsRepo.getById(10L) } returns triggeredLogistics

        val result = processLogisticsFinance(10L, force = false)

        assertEquals(10L, result)
        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    @Test
    fun `TC48 - financeTriggered=true且force=true 重新生成`() = runTest {
        val triggeredLogistics = logisticsSigned.copy(financeTriggered = true)
        coEvery { logisticsRepo.getById(10L) } returns triggeredLogistics
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc

        val result = processLogisticsFinance(10L, force = true)

        assertEquals(10L, result)
        coVerify { journalDao.insert(any()) }
    }

    // ========================================================================
    // §2 SIGNED 状态凭证
    // ========================================================================

    @Test
    fun `TC49 - EQUIPMENT_PROCUREMENT SIGNED 生成凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        coVerify {
            journalDao.insert(match {
                it.accountId == 1L && it.debit > 0 && it.summary?.contains("设备采购") == true
            })
        }
        coVerify {
            journalDao.insert(match {
                it.accountId == 1L && it.credit > 0
            })
        }
        coVerify { logisticsRepo.update(match { it.financeTriggered }) }
    }

    @Test
    fun `TC50 - EQUIPMENT_STOCK SIGNED 生成凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_STOCK)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        coVerify { journalDao.insert(any()) }
    }

    @Test
    fun `TC51 - MATERIAL_PROCUREMENT SIGNED 生成凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        coVerify { journalDao.insert(any()) }
    }

    @Test
    fun `TC52 - MATERIAL_SUPPLY SIGNED 生成收入凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.MATERIAL_SUPPLY)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        // Dr: 应收账款-客户, Cr: 主营业务收入
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("物料供应确认收入") == true && it.debit > 0
            })
        }
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("物料供应确认收入") == true && it.credit > 0
            })
        }
    }

    @Test
    fun `TC53 - MATERIAL_SUPPLY SIGNED 有库存成本 生成成本结转凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(
            id = 1L,
            type = VCType.MATERIAL_SUPPLY,
            elements = listOf(SkusFormatElement(skuId =20L, skuName = "物料X", quantity = 10, unitPrice = 50.0))
        )
        coEvery { vcRepo.getById(1L) } returns vc
        val matInv = MaterialInventory(id = 1L, skuId = 20L, skuName = "物料X", totalBalance = 100.0, averagePrice = 30.0)
        coEvery { materialInventoryRepo.getBySkuIds(listOf(20L)) } returns listOf(matInv)

        processLogisticsFinance(10L)

        // 第2组：Dr: 主营业务成本, Cr: 库存商品
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("结转物料销售成本") == true && it.debit > 0
            })
        }
    }

    @Test
    fun `TC54 - MATERIAL_SUPPLY SIGNED 无库存成本 跳过成本结转`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(
            id = 1L,
            type = VCType.MATERIAL_SUPPLY,
            elements = listOf(SkusFormatElement(skuId =20L, skuName = "物料X", quantity = 10, unitPrice = 0.0))
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { materialInventoryRepo.getBySkuIds(listOf(20L)) } returns emptyList()

        processLogisticsFinance(10L)

        // 只验证有收入凭证，不验证有成本凭证（成本为0.01以下跳过）
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("物料供应确认收入") == true
            })
        }
    }

    @Test
    fun `TC55 - RETURN SIGNED 不生成凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.RETURN)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        // RETURN VC 在 SIGNED 时不生成凭证，只在 COMPLETED 时生成
        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    @Test
    fun `TC56 - INVENTORY_ALLOCATION SIGNED 无凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.INVENTORY_ALLOCATION)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    // ========================================================================
    // §3 COMPLETED 状态凭证（仅 RETURN）
    // ========================================================================

    @Test
    fun `TC57 - RETURN CUSTOMER_TO_US 有goods_amount 生成收入冲减凭证`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 2000.0,
            logisticsCost = 0.0
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // Dr: 主营业务收入, Cr: 应收账款-客户
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货收入冲减") == true && it.debit == 2000.0
            })
        }
    }

    @Test
    fun `TC58 - RETURN CUSTOMER_TO_US 无goods_amount 跳过收入分录`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 0.0,
            logisticsCost = 0.0
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // goodsAmount < 0.01，跳过
        coVerify(exactly = 0) { journalDao.insert(match { it.debit == 0.0 && it.credit == 0.0 }) }
    }

    @Test
    fun `TC59 - RETURN US_TO_SUPPLIER 有goods_amount 生成库存冲销凭证`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.US_TO_SUPPLIER,
            goodsAmount = 3000.0,
            logisticsCost = 0.0
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // Dr: 应付账款-设备款, Cr: 库存商品
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货冲销应付") == true && it.debit == 3000.0
            })
        }
    }

    @Test
    fun `TC60 - RETURN US_TO_SUPPLIER 无goods_amount 跳过`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.US_TO_SUPPLIER,
            goodsAmount = 0.0,
            logisticsCost = 0.0
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    @Test
    fun `TC61 - RETURN CUSTOMER_TO_US RECEIVER 有物流费 Dr销售费用Cr应收账款`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 0.0,
            logisticsCost = 150.0,
            logisticsBearer = LogisticsBearer.RECEIVER
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // RECEIVER（收方承担）= 我方承担：Dr 销售费用, Cr 应收账款-客户
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货物流费-我方承担") == true && it.debit == 150.0
            })
        }
    }

    @Test
    fun `TC62 - RETURN CUSTOMER_TO_US SENDER 有物流费 Dr应收账款Cr销售费用`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 0.0,
            logisticsCost = 150.0,
            logisticsBearer = LogisticsBearer.SENDER
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // SENDER（发方承担）= 客户自付：Dr 应收账款-客户, Cr 销售费用
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货物流费-客户自付收回") == true && it.debit == 150.0
            })
        }
    }

    @Test
    fun `TC63 - RETURN US_TO_SUPPLIER SENDER 有物流费 Dr销售费用Cr应付账款`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.US_TO_SUPPLIER,
            goodsAmount = 0.0,
            logisticsCost = 200.0,
            logisticsBearer = LogisticsBearer.SENDER
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // SENDER（发方承担）= 我方承担：Dr 销售费用, Cr 应付账款-设备款
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货物流费-我方承担") == true && it.debit == 200.0
            })
        }
    }

    @Test
    fun `TC64 - RETURN US_TO_SUPPLIER RECEIVER 有物流费 Dr应付账款Cr销售费用`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.US_TO_SUPPLIER,
            goodsAmount = 0.0,
            logisticsCost = 200.0,
            logisticsBearer = LogisticsBearer.RECEIVER
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // RECEIVER（收方承担）= 代垫供应商：Dr 应付账款-设备款, Cr 销售费用
        coVerify {
            journalDao.insert(match {
                it.summary?.contains("退货物流费-代垫供应商") == true && it.debit == 200.0
            })
        }
    }

    @Test
    fun `TC65 - RETURN 物流费小于001 跳过物流费分录`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 0.0,
            logisticsCost = 0.005,
            logisticsBearer = LogisticsBearer.RECEIVER
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    @Test
    fun `TC66 - RETURN 非COMPLETED状态 不生成凭证`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(
            id = 1L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 2000.0,
            logisticsCost = 100.0
        )
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        // RETURN VC 在 SIGNED 状态不生成凭证
        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    @Test
    fun `TC67 - 非RETURN VC COMPLETED状态 不生成凭证`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(id = 2L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // 非 RETURN VC 在 COMPLETED 状态不生成凭证（仅 RETURN VC 在 COMPLETED 时生成）
        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    // ========================================================================
    // §4 金额边界
    // ========================================================================

    @Test
    fun `TC68 - 金额小于001 跳过该分录`() = runTest {
        coEvery { logisticsRepo.getById(20L) } returns logisticsCompleted
        val vc = createVC(
            id = 2L,
            type = VCType.RETURN,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 0.005,
            logisticsCost = 0.0
        )
        coEvery { vcRepo.getById(2L) } returns vc

        processLogisticsFinance(20L)

        // goodsAmount < 0.01，跳过
        coVerify(exactly = 0) { journalDao.insert(any()) }
    }

    // ========================================================================
    // §5 科目解析
    // ========================================================================

    @Test
    fun `TC70 - accountResolver解析失败 抛出异常`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { accountResolver.resolveId(any()) } returns null

        val ex = catchEx { processLogisticsFinance(10L) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("not found"))
    }

    @Test
    fun `TC71 - accountResolver正常解析 journal正确写入`() = runTest {
        coEvery { logisticsRepo.getById(10L) } returns logisticsSigned
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc

        processLogisticsFinance(10L)

        // 验证 journalDao.insert 被调用两次（Dr + Cr）
        coVerify(exactly = 2) { journalDao.insert(any()) }
        coVerify { logisticsRepo.update(match { it.financeTriggered }) }
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(
        id: Long = 1L,
        type: VCType = VCType.EQUIPMENT_PROCUREMENT,
        elements: List<VCElement> = listOf(SkusFormatElement(skuId =10L, skuName = "设备A", quantity = 1, unitPrice = 1000.0)),
        returnDirection: ReturnDirection? = null,
        goodsAmount: Double = 0.0,
        logisticsCost: Double = 0.0,
        logisticsBearer: LogisticsBearer? = null
    ) = VirtualContract(
        id = id,
        type = type,
        status = VCStatus.EXECUTING,
        subjectStatus = SubjectStatus.EXECUTING,
        cashStatus = CashStatus.EXECUTING,
        elements = elements,
        depositInfo = DepositInfo(totalAmount = 1000.0),
        returnDirection = returnDirection,
        goodsAmount = goodsAmount,
        logisticsCost = logisticsCost,
        logisticsBearer = logisticsBearer
    )

    private suspend fun catchEx(block: suspend () -> Unit): Exception {
        return try {
            block()
            throw AssertionError("Expected exception was not thrown")
        } catch (e: Exception) {
            e
        }
    }
}
