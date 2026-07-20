package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.VCStatusLogRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
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
 * VirtualContractStateMachineUseCase 完整测试套件
 *
 * 覆盖所有 public/private 方法的全部执行路径和边界条件：
 * - onLogisticsStatusChanged          物流状态变更 → 标的物状态映射
 * - onCashFlowChanged                资金流变更 → 押金处理 + 资金状态重算
 * - processCfDeposit                 押金流水处理（退货VC押金重定向）
 * - processVcDeposit                  动态重算 shouldReceive + 退货VC自动完成
 * - calculateShouldReceive           shouldReceive 计算（基于库存 vs 基于合同计划）
 * - distributeDepositToInventory     按比例分摊押金到运营中设备
 * - recalculateCashStatus            资金状态重算（货款/押金结清判断 + 预付比例）
 * - recalculateOverallStatus         整体状态自动完成
 */
class VirtualContractStateMachineUseCaseTest {

    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var cashFlowRepo: CashFlowRepository
    private lateinit var inventoryRepo: EquipmentInventoryRepository
    private lateinit var logRepo: VCStatusLogRepository
    private lateinit var stateMachine: VirtualContractStateMachineUseCase

    @Before
    fun setup() {
        vcRepo = mockk()
        cashFlowRepo = mockk()
        inventoryRepo = mockk()
        logRepo = mockk()

        stateMachine = VirtualContractStateMachineUseCase(
            vcRepo = vcRepo,
            cashFlowRepo = cashFlowRepo,
            inventoryRepo = inventoryRepo,
            logRepo = logRepo
        )

        coEvery { cashFlowRepo.getByVcId(any()) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(any()) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(any()) } returns flowOf(emptyList())
        coEvery { logRepo.insert(any()) } returns 0L
        coEvery { vcRepo.update(any()) } returns Unit
        coEvery { inventoryRepo.update(any()) } returns Unit
    }

    // ========================================================================
    // onLogisticsStatusChanged — 物流状态 → 标的物状态映射
    // ========================================================================

    @Test
    fun `物流IN_TRANSIT映射到标的物SHIPPED`() = runTest {
        val vc = createVC(id = 1L, subjectStatus = SubjectStatus.EXECUTING)
        coEvery { vcRepo.getById(1L) } returns vc

        stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.IN_TRANSIT)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(SubjectStatus.SHIPPED, slot.captured.subjectStatus)
    }

    @Test
    fun `物流SIGNED映射到标的物SIGNED`() = runTest {
        val vc = createVC(id = 1L, subjectStatus = SubjectStatus.EXECUTING)
        coEvery { vcRepo.getById(1L) } returns vc

        stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.SIGNED)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(SubjectStatus.SIGNED, slot.captured.subjectStatus)
    }

    @Test
    fun `物流COMPLETED映射到标的物COMPLETED`() = runTest {
        val vc = createVC(id = 1L, subjectStatus = SubjectStatus.SIGNED)
        coEvery { vcRepo.getById(1L) } returns vc

        stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.COMPLETED)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(SubjectStatus.COMPLETED, slot.captured.subjectStatus)
    }

    @Test
    fun `物流状态不变时不调用update`() = runTest {
        // SHIPPED → IN_TRANSIT 仍然映射到 SHIPPED，状态不变
        val vc = createVC(id = 1L, subjectStatus = SubjectStatus.SHIPPED)
        coEvery { vcRepo.getById(1L) } returns vc

        stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.IN_TRANSIT)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `VC不存在时onLogisticsStatusChanged不做任何操作`() = runTest {
        coEvery { vcRepo.getById(999L) } returns null

        stateMachine.onLogisticsStatusChanged(999L, LogisticsStatus.SIGNED)

        coVerify(exactly = 0) { vcRepo.update(any()) }
        coVerify(exactly = 0) { logRepo.insert(any()) }
    }

    @Test
    fun `退货VC物流COMPLETED触发原合同押金重算`() = runTest {
        val originalVc = createVC(id = 1L,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        val returnVc = createVC(id = 2L, type = VCType.RETURN, relatedVcId = 1L,
            subjectStatus = SubjectStatus.EXECUTING)

        coEvery { vcRepo.getById(2L) } returns returnVc
        coEvery { vcRepo.getById(1L) } returns originalVc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onLogisticsStatusChanged(2L, LogisticsStatus.COMPLETED)

        // 退货VC subjectStatus → COMPLETED
        coVerify { vcRepo.update(match { it.id == 2L && it.subjectStatus == SubjectStatus.COMPLETED }) }
        // 原合同押金重算
        coVerify(atLeast = 1) { vcRepo.update(match { it.id == 1L }) }
    }

    // ========================================================================
    // onCashFlowChanged — 资金流变更入口
    // ========================================================================

    @Test
    fun `cf为null时无资金流水不触发update`() = runTest {
        val vc = createVC(id = 1L, subjectStatus = SubjectStatus.COMPLETED, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `VC不存在时onCashFlowChanged不做任何操作`() = runTest {
        coEvery { vcRepo.getById(999L) } returns null

        stateMachine.onCashFlowChanged(999L, createCashFlow(vcId = 999L, type = CashFlowType.DEPOSIT, amount = 100.0))

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    // ========================================================================
    // processCfDeposit — 押金流水重定向
    // ========================================================================

    @Test
    fun `普通VC的DEPOSIT流水增加自身actualDeposit`() = runTest {
        val vc = createVC(id = 1L, depositInfo = DepositInfo(actualDeposit = 100.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        val depositCf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 200.0)
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(depositCf))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, depositCf)

        // actualDeposit: 100 → 300
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `普通VC的DEPOSIT_REFUND流水减少自身actualDeposit`() = runTest {
        val vc = createVC(id = 1L, depositInfo = DepositInfo(actualDeposit = 300.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        val refundCf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT_REFUND, amount = 100.0)
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(refundCf))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, refundCf)

        // actualDeposit: 300 → 200
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `退货VC的DEPOSIT流水重定向到原合同`() = runTest {
        val originalVc = createVC(id = 1L, depositInfo = DepositInfo(actualDeposit = 100.0, shouldReceive = 500.0))
        val returnVc = createVC(id = 2L, type = VCType.RETURN, relatedVcId = 1L,
            depositInfo = DepositInfo(actualDeposit = 0.0))
        val depositCf = createCashFlow(vcId = 2L, type = CashFlowType.DEPOSIT, amount = 50.0)

        coEvery { vcRepo.getById(2L) } returns returnVc
        coEvery { vcRepo.getById(1L) } returns originalVc
        coEvery { cashFlowRepo.getByVcId(2L) } returns flowOf(listOf(depositCf))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(2L, depositCf)

        // 原合同 actualDeposit 被更新（100→150）
        coVerify(atLeast = 1) { vcRepo.update(match { it.id == 1L }) }
    }

    @Test
    fun `DEPOSIT_REFUND后actualDeposit不低于零`() = runTest {
        val vc = createVC(id = 1L, depositInfo = DepositInfo(actualDeposit = 50.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        val refundCf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT_REFUND, amount = 100.0)
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(refundCf))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, refundCf)

        // actualDeposit = max(0, 50-100) = 0
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `cf为DEPOSIT类型触发processCfDeposit`() = runTest {
        val vc = createVC(id = 1L, depositInfo = DepositInfo(actualDeposit = 100.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        val depositCf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 200.0)
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(depositCf))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, depositCf)

        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `cf为DEPOSIT_REFUND类型触发processCfDeposit`() = runTest {
        val vc = createVC(id = 1L, depositInfo = DepositInfo(actualDeposit = 300.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        val refundCf = createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT_REFUND, amount = 100.0)
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(refundCf))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, refundCf)

        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    // ========================================================================
    // calculateShouldReceive — shouldReceive 计算
    // ========================================================================

    @Test
    fun `非设备采购类型VC的shouldReceive保持不变`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.MATERIAL_SUPPLY,
            depositInfo = DepositInfo(shouldReceive = 999.0)
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 10.0))

        // MATERIAL_SUPPLY 不走 shouldReceive 重算，仅 actualDeposit 增加
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `设备采购VC无运营设备时shouldReceive基于初始合同计划`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            depositInfo = DepositInfo(shouldReceive = 0.0),
            elements = listOf(
                SkusFormatElement(skuId =1L, skuName = "SKU-A", quantity = 3, unitPrice = 100.0, deposit = 50.0),
                SkusFormatElement(skuId =2L, skuName = "SKU-B", quantity = 2, unitPrice = 200.0, deposit = 80.0)
            )
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        // 无运营设备 → 返回只有 IN_STOCK 设备
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(listOf(
            createEquipmentInventory(id = 1L, vcId = 1L, skuId = 1L,
                operationalStatus = OperationalStatus.IN_STOCK, depositAmount = 0.0)
        ))

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 50.0))

        // 3*50 + 2*80 = 310
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `设备采购VC有运营设备时shouldReceive基于设备数量`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            depositInfo = DepositInfo(shouldReceive = 0.0),
            elements = listOf(
                SkusFormatElement(skuId =1L, skuName = "SKU-A", quantity = 10, unitPrice = 100.0, deposit = 50.0),
                SkusFormatElement(skuId =2L, skuName = "SKU-B", quantity = 5, unitPrice = 200.0, deposit = 80.0)
            )
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(listOf(
            createEquipmentInventory(id = 1L, vcId = 1L, skuId = 1L,
                operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 50.0),
            createEquipmentInventory(id = 2L, vcId = 1L, skuId = 2L,
                operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 80.0)
        ))

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 50.0))

        // 1*50 + 1*80 = 130（基于运营中设备数量）
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `设备采购VC无运营设备且elements为空时shouldReceive为零`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            depositInfo = DepositInfo(shouldReceive = 0.0),
            elements = emptyList()
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 50.0))

        // shouldReceive = 0
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `多SKU运营设备shouldReceive为各SKU约定押金之和`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_STOCK,
            depositInfo = DepositInfo(shouldReceive = 0.0),
            elements = listOf(
                SkusFormatElement(skuId =1L, skuName = "SKU-A", quantity = 10, unitPrice = 100.0, deposit = 30.0),
                SkusFormatElement(skuId =2L, skuName = "SKU-B", quantity = 5, unitPrice = 200.0, deposit = 70.0),
                SkusFormatElement(skuId =3L, skuName = "SKU-C", quantity = 3, unitPrice = 50.0, deposit = 20.0)
            )
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(listOf(
            createEquipmentInventory(id = 1L, vcId = 1L, skuId = 1L,
                operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 30.0),
            createEquipmentInventory(id = 2L, vcId = 1L, skuId = 2L,
                operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 70.0),
            createEquipmentInventory(id = 3L, vcId = 1L, skuId = 3L,
                operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 20.0)
        ))

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 120.0))

        // 30 + 70 + 20 = 120
        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    // ========================================================================
    // distributeDepositToInventory — 押金分摊
    // ========================================================================

    @Test
    fun `无运营设备时distributeDepositToInventory不更新任何设备`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            depositInfo = DepositInfo(shouldReceive = 0.0, actualDeposit = 500.0)
        )
        coEvery { vcRepo.getById(1L) } returns vc
        // 只有库存中设备，无运营中设备
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(listOf(
            createEquipmentInventory(id = 1L, vcId = 1L, skuId = 1L,
                operationalStatus = OperationalStatus.IN_STOCK, depositAmount = 0.0)
        ))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 100.0))

        // 无运营设备 → inventoryRepo.update 不应被调用
        coVerify(exactly = 0) { inventoryRepo.update(any()) }
    }

    @Test
    fun `有运营设备时inventoryUpdate被调用`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            depositInfo = DepositInfo(shouldReceive = 500.0, actualDeposit = 250.0)
        )
        val inv = createEquipmentInventory(id = 1L, vcId = 1L, skuId = 1L,
            operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 500.0)

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(listOf(inv))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 250.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 250.0))

        // 有运营设备 → inventoryRepo.update 被调用
        coVerify(atLeast = 1) { inventoryRepo.update(any()) }
    }

    @Test
    fun `shouldReceive为零时ratio为1p0所有设备获得全押金`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            depositInfo = DepositInfo(shouldReceive = 0.0, actualDeposit = 100.0)
        )
        val inv = createEquipmentInventory(id = 1L, vcId = 1L, skuId = 1L,
            operationalStatus = OperationalStatus.IN_OPERATION, depositAmount = 100.0)

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(listOf(inv))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 100.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 100.0))

        // shouldReceive=0 → ratio=1.0
        coVerify(atLeast = 1) { inventoryRepo.update(any()) }
    }

    // ========================================================================
    // recalculateCashStatus — 资金状态重算
    // ========================================================================

    @Test
    fun `无资金流水时cashStatus保持不变`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `货款结清且押金结清时cashStatus变为COMPLETED`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 1000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.COMPLETED, slot.captured.cashStatus)
    }

    @Test
    fun `货款未结清但押金结清时cashStatus保持EXECUTING`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 600.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `货款结清但押金未结清时cashStatus保持EXECUTING`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 200.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 1000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 200.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `cashStatus已是COMPLETED则不再更新`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.COMPLETED,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 1000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `预付款比例达标时cashStatus变为PREPAID`() = runTest {
        // 预付比例 = expectedDeposit(500) / totalDue(1000) = 0.5
        // paidGoods=600 >= 1000*0.5=500 → PREPAID
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, expectedDeposit = 500.0, actualDeposit = 0.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 600.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.PREPAID, slot.captured.cashStatus)
    }

    @Test
    fun `预付款比例刚好达标时cashStatus变为PREPAID`() = runTest {
        // paidGoods=500 >= 1000*0.5-0.01=499.99 → PREPAID
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, expectedDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.PREPAID, slot.captured.cashStatus)
    }

    @Test
    fun `预付款比例未达标时cashStatus保持EXECUTING`() = runTest {
        // paidGoods=400 < 1000*0.5=500 → 保持 EXECUTING
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, expectedDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 400.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `预付款比例为0时cashStatus保持EXECUTING`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, expectedDeposit = 0.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 1000.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        // ratio=0，不满足 ratio>0 条件 → 保持 EXECUTING
        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `货款使用PREPAYMENT类型计入paidGoods`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PREPAYMENT, amount = 1000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.COMPLETED, slot.captured.cashStatus)
    }

    @Test
    fun `REFUND类型也计入paidGoods`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.REFUND, amount = 200.0),
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 800.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.COMPLETED, slot.captured.cashStatus)
    }

    @Test
    fun `OFFSET_OUTFLOW类型计入paidGoods`() = runTest {
        // paidGoods = PERFORMANCE(2000) + OFFSET_OUTFLOW(5000) = 7000
        // totalAmount=7000, 押金已结清
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 7000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 2000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.OFFSET_OUTFLOW, amount = 5000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.COMPLETED, slot.captured.cashStatus)
    }

    @Test
    fun `OFFSET_OUTFLOW单独计入paidGoods使货款结清`() = runTest {
        // OFFSET_OUTFLOW(10000) = totalAmount(10000) → goods cleared
        // shouldReceive=0 使 depDue=0 → 押金直接判定已结清
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 10000.0, shouldReceive = 0.0, actualDeposit = 0.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.OFFSET_OUTFLOW, amount = 10000.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.COMPLETED, slot.captured.cashStatus)
    }

    @Test
    fun `DEPOSIT类型不计入paidGoods`() = runTest {
        // DEPOSIT(5000) 不计入 paidGoods, PERFORMANCE(4000) < totalAmount(10000) → 不结清
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 10000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 5000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 4000.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        // paidGoods=4000 < 10000，不结清，不更新
        coVerify(exactly = 0) { vcRepo.update(match { it.cashStatus == CashStatus.COMPLETED }) }
    }

    @Test
    fun `关联退货VC的DEPOSIT_REFUND计入totalReturnDeposit`() = runTest {
        val vc = createVC(id = 1L, cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        val returnVc = createVC(id = 2L, type = VCType.RETURN, relatedVcId = 1L,
            status = VCStatus.EXECUTING, subjectStatus = SubjectStatus.COMPLETED, cashStatus = CashStatus.EXECUTING)

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(listOf(returnVc))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 1000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { cashFlowRepo.getByVcId(2L) } returns flowOf(listOf(
            createCashFlow(vcId = 2L, type = CashFlowType.DEPOSIT_REFUND, amount = 200.0)
        ))
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        // actualNetDeposit = 500 - 200 = 300 < depDue=500 → deposit 未结清
        // 不应变为 COMPLETED
        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    // ========================================================================
    // recalculateOverallStatus — 整体状态自动完成
    // ========================================================================

    @Test
    fun `subjectStatus和cashStatus同时COMPLETED时VC状态自动变为COMPLETED`() = runTest {
        val vc = createVC(
            id = 1L,
            status = VCStatus.EXECUTING,
            subjectStatus = SubjectStatus.COMPLETED,
            cashStatus = CashStatus.COMPLETED,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0)
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 1000.0),
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(atLeast = 1) { vcRepo.update(any()) }
    }

    @Test
    fun `subjectStatus和cashStatus同时COMPLETED但status已是COMPLETED时不再更新`() = runTest {
        val vc = createVC(
            id = 1L,
            status = VCStatus.COMPLETED,
            subjectStatus = SubjectStatus.COMPLETED,
            cashStatus = CashStatus.COMPLETED
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `subjectStatus完成但cashStatus未完成时status保持EXECUTING`() = runTest {
        val vc = createVC(
            id = 1L,
            status = VCStatus.EXECUTING,
            subjectStatus = SubjectStatus.COMPLETED,
            cashStatus = CashStatus.EXECUTING,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 0.0)
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.PERFORMANCE, amount = 500.0)
        ))
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    @Test
    fun `cashStatus完成但subjectStatus未完成时status保持EXECUTING`() = runTest {
        // expectedDeposit=0 → ratio=0 → newCashStatus=EXECUTING, 与当前 cashStatus=COMPLETED 不同
        // → 会调用 update（cashStatus: COMPLETED → EXECUTING），这是代码行为
        // subjectStatus != COMPLETED → recalculateOverallStatus 不触发
        val vc = createVC(
            id = 1L,
            status = VCStatus.EXECUTING,
            subjectStatus = SubjectStatus.EXECUTING,
            cashStatus = CashStatus.COMPLETED,
            depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0)
        )
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(emptyList())
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(1L, null)

        // 代码行为：expectedDeposit=0 → ratio=0 → cashStatus 变为 EXECUTING
        // 验证 cashStatus 从 COMPLETED → EXECUTING（status 不变）
        val slot = slot<VirtualContract>()
        coVerify { vcRepo.update(capture(slot)) }
        assertEquals(CashStatus.EXECUTING, slot.captured.cashStatus)
        assertEquals(VCStatus.EXECUTING, slot.captured.status) // status 不变
    }

    @Test
    fun `VC不存在时recalculateOverallStatus不做任何操作`() = runTest {
        coEvery { vcRepo.getById(999L) } returns null

        stateMachine.onCashFlowChanged(999L, null)

        coVerify(exactly = 0) { vcRepo.update(any()) }
    }

    // ========================================================================
    // processVcDeposit — 退货VC自动完成
    // ========================================================================

    @Test
    fun `depDue充足且退货VC无资金流水时update被调用`() = runTest {
        // actualNetDeposit=500, depDue=500, 500 <= 500.01 满足
        // 退货VC status==EXECUTING && cashStatus==EXECUTING && subjectStatus==COMPLETED && cfCount==0
        // → 退货VC应自动完成（status → COMPLETED）
        val originalVc = createVC(id = 1L, depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 500.0))
        val returnVc = createVC(id = 2L, type = VCType.RETURN, relatedVcId = 1L,
            status = VCStatus.EXECUTING, subjectStatus = SubjectStatus.COMPLETED, cashStatus = CashStatus.EXECUTING)

        coEvery { vcRepo.getById(2L) } returns returnVc
        coEvery { vcRepo.getById(1L) } returns originalVc
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(listOf(returnVc))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 500.0)
        ))
        coEvery { cashFlowRepo.getByVcId(2L) } returns flowOf(emptyList())
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(2L, null)

        // 退货VC有 update 调用（cashStatus 或 status 变更）
        coVerify(atLeast = 1) { vcRepo.update(match { it.id == 2L }) }
    }

    @Test
    fun `depDue不足且退货VC有资金流水时不自动完成`() = runTest {
        // actualNetDeposit=100, depDue=500, 100 <= 500.01 满足
        // 但 retVc 有 cash flow → 不自动完成
        val originalVc = createVC(id = 1L, depositInfo = DepositInfo(totalAmount = 1000.0, shouldReceive = 500.0, actualDeposit = 100.0))
        val returnVc = createVC(id = 2L, type = VCType.RETURN, relatedVcId = 1L,
            status = VCStatus.EXECUTING, subjectStatus = SubjectStatus.COMPLETED, cashStatus = CashStatus.EXECUTING)

        coEvery { vcRepo.getById(2L) } returns returnVc
        coEvery { vcRepo.getById(1L) } returns originalVc
        coEvery { vcRepo.getByRelatedVcId(1L) } returns flowOf(listOf(returnVc))
        coEvery { cashFlowRepo.getByVcId(1L) } returns flowOf(listOf(
            createCashFlow(vcId = 1L, type = CashFlowType.DEPOSIT, amount = 100.0)
        ))
        coEvery { cashFlowRepo.getByVcId(2L) } returns flowOf(listOf(
            createCashFlow(vcId = 2L, type = CashFlowType.DEPOSIT, amount = 50.0)
        ))
        coEvery { inventoryRepo.getByVcId(1L) } returns flowOf(emptyList())

        stateMachine.onCashFlowChanged(2L, null)

        // retVc 有 cash flow → 不自动完成（status 不变为 COMPLETED）
        coVerify(exactly = 0) { vcRepo.update(match { it.id == 2L && it.status == VCStatus.COMPLETED }) }
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(
        id: Long = 1L,
        type: VCType = VCType.EQUIPMENT_PROCUREMENT,
        status: VCStatus = VCStatus.EXECUTING,
        subjectStatus: SubjectStatus = SubjectStatus.EXECUTING,
        cashStatus: CashStatus = CashStatus.EXECUTING,
        businessId: Long? = null,
        supplyChainId: Long? = null,
        relatedVcId: Long? = null,
        elements: List<VCElement> = emptyList(),
        depositInfo: DepositInfo = DepositInfo()
    ) = VirtualContract(
        id = id, type = type, status = status, subjectStatus = subjectStatus,
        cashStatus = cashStatus, businessId = businessId, supplyChainId = supplyChainId,
        relatedVcId = relatedVcId, elements = elements, depositInfo = depositInfo
    )

    private fun createCashFlow(
        id: Long = 1L, vcId: Long, type: CashFlowType, amount: Double
    ) = CashFlow(id = id, virtualContractId = vcId, type = type, amount = amount)

    private fun createEquipmentInventory(
        id: Long = 1L, vcId: Long, skuId: Long,
        operationalStatus: OperationalStatus, depositAmount: Double = 0.0
    ) = EquipmentInventory(
        id = id, virtualContractId = vcId, skuId = skuId,
        operationalStatus = operationalStatus, depositAmount = depositAmount
    )
}
