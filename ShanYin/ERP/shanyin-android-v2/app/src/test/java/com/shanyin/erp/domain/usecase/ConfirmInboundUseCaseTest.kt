package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.ExpressOrderRepository
import com.shanyin.erp.domain.repository.LogisticsRepository
import com.shanyin.erp.domain.repository.MaterialInventoryRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ProcessLogisticsFinanceUseCase
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * ConfirmInboundUseCase 完整测试套件
 *
 * §1 设备采购入库（EQUIPMENT_PROCUREMENT / EQUIPMENT_STOCK）
 * §2 物料采购入库（MATERIAL_PROCUREMENT）
 * §3 物料供应出库（MATERIAL_SUPPLY）
 * §4 退货（RETURN）
 * §5 库存调拨（INVENTORY_ALLOCATION）
 * §6 防重复确认入库
 * §7 联动触发（锁定 COMPLETED + VC 状态机 + 财务凭证）
 */
class ConfirmInboundUseCaseTest {

    private lateinit var logisticsRepo: LogisticsRepository
    private lateinit var expressOrderRepo: ExpressOrderRepository
    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var equipmentInventoryRepo: EquipmentInventoryRepository
    private lateinit var materialInventoryRepo: MaterialInventoryRepository
    private lateinit var stateMachine: VirtualContractStateMachineUseCase
    private lateinit var processLogisticsFinance: ProcessLogisticsFinanceUseCase
    private lateinit var confirmInbound: ConfirmInboundUseCase

    private val logistics1 = Logistics(id = 10L, virtualContractId = 1L, status = LogisticsStatus.SIGNED)

    @Before
    fun setup() {
        logisticsRepo = mockk(relaxed = true)
        expressOrderRepo = mockk(relaxed = true)
        vcRepo = mockk(relaxed = true)
        equipmentInventoryRepo = mockk(relaxed = true)
        materialInventoryRepo = mockk(relaxed = true)
        stateMachine = mockk(relaxed = true)
        processLogisticsFinance = mockk(relaxed = true)

        confirmInbound = ConfirmInboundUseCase(
            logisticsRepo = logisticsRepo,
            expressOrderRepo = expressOrderRepo,
            vcRepo = vcRepo,
            equipmentInventoryRepo = equipmentInventoryRepo,
            materialInventoryRepo = materialInventoryRepo,
            stateMachine = stateMachine,
            processLogisticsFinance = processLogisticsFinance
        )

        coEvery { logisticsRepo.getById(10L) } returns logistics1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns emptyList()
    }

    // ========================================================================
    // §1 设备采购入库（EQUIPMENT_PROCUREMENT / EQUIPMENT_STOCK）
    // ========================================================================

    @Test
    fun `TC24 - 设备采购 SN数量=SKU总量 正常入库`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 10L, skuName = "设备A", quantity = 3)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { equipmentInventoryRepo.getBySn(any()) } returns null
        coEvery { equipmentInventoryRepo.insert(any()) } returns 1L

        confirmInbound(10L, listOf("SN001", "SN002", "SN003"))

        coVerify(exactly = 3) { equipmentInventoryRepo.insert(any()) }
        coVerify { logisticsRepo.update(match { it.status == LogisticsStatus.COMPLETED }) }
        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.COMPLETED) }
        coVerify { processLogisticsFinance.invoke(10L) }
    }

    @Test
    fun `TC25 - 设备采购 SN数量小于SKU总量 部分入库`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 10L, skuName = "设备A", quantity = 5)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { equipmentInventoryRepo.getBySn(any()) } returns null
        coEvery { equipmentInventoryRepo.insert(any()) } returns 1L

        confirmInbound(10L, listOf("SN001", "SN002"))

        coVerify(exactly = 2) { equipmentInventoryRepo.insert(any()) }
    }

    @Test
    fun `TC26 - 设备采购 SN数量大于SKU总量 循环分配`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 10L, skuName = "设备A", quantity = 3)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { equipmentInventoryRepo.getBySn(any()) } returns null
        coEvery { equipmentInventoryRepo.insert(any()) } returns 1L

        confirmInbound(10L, listOf("SN001", "SN002", "SN003", "SN004", "SN005", "SN006"))

        coVerify(exactly = 6) { equipmentInventoryRepo.insert(any()) }
    }

    @Test
    fun `TC27 - 设备采购 SN已存在 抛出异常`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 10L, skuName = "设备A", quantity = 3)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { equipmentInventoryRepo.getBySn("SN001") } returns EquipmentInventory(sn = "SN001", skuId = 10L)
        coEvery { equipmentInventoryRepo.getBySn("SN002") } returns null
        coEvery { equipmentInventoryRepo.getBySn("SN003") } returns null

        val ex = catchEx { confirmInbound(10L, listOf("SN001", "SN002", "SN003")) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("SN001"))
        assertTrue(ex.message!!.contains("已存在"))
    }

    @Test
    fun `TC28 - 设备采购 SN列表为空 抛出异常`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 10L, skuName = "设备A", quantity = 3)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)

        val ex = catchEx { confirmInbound(10L, emptyList()) }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex.message!!.contains("SN"))
    }

    @Test
    fun `TC29 - 设备采购 多SKU SN互不重复`() = runTest {
        val vc = createVC(id = 1L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(
            ExpressItem(skuId = 10L, skuName = "设备A", quantity = 3),
            ExpressItem(skuId = 11L, skuName = "设备B", quantity = 2)
        ))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { equipmentInventoryRepo.getBySn(any()) } returns null
        coEvery { equipmentInventoryRepo.insert(any()) } returns 1L

        confirmInbound(10L, listOf("SN001", "SN002", "SN003", "SN004", "SN005"))

        coVerify(exactly = 5) { equipmentInventoryRepo.insert(any()) }
    }

    @Test
    fun `TC30 - 设备采购 押金depositAmount正确从VCElement读取`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.EQUIPMENT_PROCUREMENT,
            elements = listOf(SkusFormatElement(skuId =10L, skuName = "设备A", quantity = 2, unitPrice = 1000.0, deposit = 500.0))
        )
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 10L, skuName = "设备A", quantity = 2)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { equipmentInventoryRepo.getBySn(any()) } returns null

        confirmInbound(10L, listOf("SN001", "SN002"))

        coVerify {
            equipmentInventoryRepo.insert(match {
                it.depositAmount == 500.0
            })
        }
    }

    // ========================================================================
    // §2 物料采购入库（MATERIAL_PROCUREMENT）
    // ========================================================================

    @Test
    fun `TC31 - 物料采购 SKU已存在 累加totalBalance`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        val existingMat = MaterialInventory(id = 1L, skuId = 20L, skuName = "物料X", totalBalance = 100.0)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns existingMat

        confirmInbound(10L)

        coVerify { materialInventoryRepo.update(match { it.totalBalance == 150.0 }) }
    }

    @Test
    fun `TC32 - 物料采购 SKU不存在 新建MaterialInventory`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null

        confirmInbound(10L)

        coVerify {
            materialInventoryRepo.insert(match {
                it.skuId == 20L && it.totalBalance == 50.0
            })
        }
    }

    @Test
    fun `TC33 - 物料采购 多SKU批量入库`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(
            ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50),
            ExpressItem(skuId = 21L, skuName = "物料Y", quantity = 30)
        ))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null
        coEvery { materialInventoryRepo.getBySkuId(21L) } returns null

        confirmInbound(10L)

        coVerify { materialInventoryRepo.insert(match { it.skuId == 20L }) }
        coVerify { materialInventoryRepo.insert(match { it.skuId == 21L }) }
    }

    @Test
    fun `TC34 - 物料采购 SN列表为空 允许`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null

        confirmInbound(10L, emptyList())

        coVerify { materialInventoryRepo.insert(any()) }
    }

    // ========================================================================
    // §3 物料供应出库（MATERIAL_SUPPLY）
    // ========================================================================

    @Test
    fun `TC35 - 物料供应 SKU存在 扣减totalBalance`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_SUPPLY)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 30)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        val existingMat = MaterialInventory(id = 1L, skuId = 20L, skuName = "物料X", totalBalance = 100.0)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns existingMat

        confirmInbound(10L)

        coVerify { materialInventoryRepo.update(match { it.totalBalance == 70.0 }) }
    }

    @Test
    fun `TC36 - 物料供应 SKU不存在 抛出异常`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_SUPPLY)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 30)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null

        val ex = catchEx { confirmInbound(10L) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("库存"))
    }

    @Test
    fun `TC37 - 物料供应 出库超量 扣减至零`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_SUPPLY)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 30)))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        val existingMat = MaterialInventory(id = 1L, skuId = 20L, skuName = "物料X", totalBalance = 20.0)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns existingMat

        confirmInbound(10L)

        coVerify { materialInventoryRepo.update(match { it.totalBalance == 0.0 }) }
    }

    @Test
    fun `TC38 - 物料供应 多SKU批量出库`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_SUPPLY)
        coEvery { vcRepo.getById(1L) } returns vc
        val eo = createExpressOrder(1L, listOf(
            ExpressItem(skuId = 20L, skuName = "物料X", quantity = 5),
            ExpressItem(skuId = 21L, skuName = "物料Y", quantity = 3)
        ))
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns MaterialInventory(id = 1L, skuId = 20L, skuName = "物料X", totalBalance = 100.0)
        coEvery { materialInventoryRepo.getBySkuId(21L) } returns MaterialInventory(id = 2L, skuId = 21L, skuName = "物料Y", totalBalance = 50.0)

        confirmInbound(10L)

        coVerify { materialInventoryRepo.update(match { it.skuId == 20L && it.totalBalance == 95.0 }) }
        coVerify { materialInventoryRepo.update(match { it.skuId == 21L && it.totalBalance == 47.0 }) }
    }

    // ========================================================================
    // §4 退货（RETURN）
    // ========================================================================

    @Test
    fun `TC39 - 退货VC 有relatedVcId 触发押金重算`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.RETURN,
            relatedVcId = 2L,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 2000.0,
            logisticsCost = 100.0,
            logisticsBearer = LogisticsBearer.RECEIVER
        )
        coEvery { vcRepo.getById(1L) } returns vc
        val originalVC = createVC(id = 2L, type = VCType.EQUIPMENT_PROCUREMENT)
        coEvery { vcRepo.getById(2L) } returns originalVC

        confirmInbound(10L)

        // 押金重算由 stateMachine.onLogisticsStatusChanged 触发
        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.COMPLETED) }
    }

    @Test
    fun `TC40 - 退货VC 无relatedVcId 跳过押金重算`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.RETURN,
            relatedVcId = null,
            returnDirection = ReturnDirection.CUSTOMER_TO_US,
            goodsAmount = 2000.0,
            logisticsCost = 100.0
        )
        coEvery { vcRepo.getById(1L) } returns vc

        confirmInbound(10L)

        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.COMPLETED) }
    }

    @Test
    fun `TC41 - 退货VC 原合同为物料采购 跳过押金重算`() = runTest {
        val vc = createVC(
            id = 1L,
            type = VCType.RETURN,
            relatedVcId = 2L,
            returnDirection = ReturnDirection.CUSTOMER_TO_US
        )
        coEvery { vcRepo.getById(1L) } returns vc
        val originalVC = createVC(id = 2L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(2L) } returns originalVC

        confirmInbound(10L)

        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.COMPLETED) }
    }

    // ========================================================================
    // §5 库存调拨（INVENTORY_ALLOCATION）
    // ========================================================================

    @Test
    fun `TC42 - 库存调拨 确认入库 无库存操作`() = runTest {
        val vc = createVC(id = 1L, type = VCType.INVENTORY_ALLOCATION)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns emptyList()

        confirmInbound(10L)

        coVerify(exactly = 0) { materialInventoryRepo.insert(any()) }
        coVerify(exactly = 0) { materialInventoryRepo.update(any()) }
        coVerify(exactly = 0) { equipmentInventoryRepo.insert(any()) }
        coVerify { logisticsRepo.update(match { it.status == LogisticsStatus.COMPLETED }) }
    }

    // ========================================================================
    // §6 防重复确认入库
    // ========================================================================

    @Test
    fun `TC43 - status=COMPLETED的物流重复确认 抛出异常`() = runTest {
        val completedLogistics = Logistics(id = 10L, virtualContractId = 1L, status = LogisticsStatus.COMPLETED)
        coEvery { logisticsRepo.getById(10L) } returns completedLogistics

        val ex = catchEx { confirmInbound(10L) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("已完成"))
    }

    // ========================================================================
    // §7 联动触发（锁定 + VC状态机 + 财务凭证）
    // ========================================================================

    @Test
    fun `TC44 - 确认入库 锁定status=COMPLETED`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50))))
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null

        confirmInbound(10L)

        coVerify { logisticsRepo.update(match { it.status == LogisticsStatus.COMPLETED }) }
    }

    @Test
    fun `TC45 - 确认入库 触发VC subjectStatus→COMPLETED`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50))))
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null

        confirmInbound(10L)

        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.COMPLETED) }
    }

    @Test
    fun `TC46 - 确认入库 触发财务凭证`() = runTest {
        val vc = createVC(id = 1L, type = VCType.MATERIAL_PROCUREMENT)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(createExpressOrder(1L, listOf(ExpressItem(skuId = 20L, skuName = "物料X", quantity = 50))))
        coEvery { materialInventoryRepo.getBySkuId(20L) } returns null

        confirmInbound(10L)

        coVerify { processLogisticsFinance.invoke(10L) }
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(
        id: Long = 1L,
        type: VCType = VCType.EQUIPMENT_PROCUREMENT,
        status: VCStatus = VCStatus.EXECUTING,
        relatedVcId: Long? = null,
        elements: List<VCElement> = listOf(SkusFormatElement(skuId =10L, skuName = "设备A", quantity = 2, unitPrice = 1000.0, deposit = 500.0)),
        returnDirection: ReturnDirection? = null,
        goodsAmount: Double = 0.0,
        logisticsCost: Double = 0.0,
        logisticsBearer: LogisticsBearer? = null
    ) = VirtualContract(
        id = id,
        type = type,
        status = status,
        subjectStatus = SubjectStatus.EXECUTING,
        cashStatus = CashStatus.EXECUTING,
        elements = elements,
        relatedVcId = relatedVcId,
        returnDirection = returnDirection,
        goodsAmount = goodsAmount,
        logisticsCost = logisticsCost,
        logisticsBearer = logisticsBearer
    )

    private fun createExpressOrder(
        logisticsId: Long = 10L,
        items: List<ExpressItem> = listOf(ExpressItem(skuId = 10L, skuName = "SKU", quantity = 1))
    ) = ExpressOrder(
        id = 1L,
        logisticsId = logisticsId,
        trackingNumber = "TRACK1",
        items = items,
        addressInfo = AddressInfo(contactName = "Test", phone = "123"),
        status = ExpressStatus.SIGNED
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
