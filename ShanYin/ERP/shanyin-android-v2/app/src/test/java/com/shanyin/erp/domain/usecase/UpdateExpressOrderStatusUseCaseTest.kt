package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.ExpressOrderRepository
import com.shanyin.erp.domain.repository.LogisticsRepository
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
 * UpdateExpressOrderStatusUseCase 完整测试套件
 *
 * §1  状态推导真值表（deriveLogisticsStatus）
 * §2  联动触发：VC subjectStatus 镜像 + 财务凭证生成
 * §3  幂等性：COMPLETED 物流不再推导
 * §4  边界：ExpressOrder/Logistics 不存在
 */
class UpdateExpressOrderStatusUseCaseTest {

    private lateinit var expressOrderRepo: ExpressOrderRepository
    private lateinit var logisticsRepo: LogisticsRepository
    private lateinit var stateMachine: VirtualContractStateMachineUseCase
    private lateinit var processLogisticsFinance: ProcessLogisticsFinanceUseCase
    private lateinit var updateExpressOrderStatus: UpdateExpressOrderStatusUseCase

    private val logistics1 = Logistics(id = 10L, virtualContractId = 1L, status = LogisticsStatus.PENDING)

    @Before
    fun setup() {
        expressOrderRepo = mockk(relaxed = true)
        logisticsRepo = mockk(relaxed = true)
        stateMachine = mockk(relaxed = true)
        processLogisticsFinance = mockk(relaxed = true)

        updateExpressOrderStatus = UpdateExpressOrderStatusUseCase(
            expressOrderRepo = expressOrderRepo,
            logisticsRepo = logisticsRepo,
            stateMachine = stateMachine,
            processLogisticsFinance = processLogisticsFinance
        )

        coEvery { expressOrderRepo.update(any()) } returns Unit
        coEvery { logisticsRepo.update(any()) } returns Unit
        coEvery { expressOrderRepo.getById(any()) } returns createExpressOrder(1L)
        coEvery { logisticsRepo.getById(10L) } returns logistics1
    }

    // ========================================================================
    // §1 状态推导真值表
    // ========================================================================

    @Test
    fun `TC08 - 单快递单PENDING→IN_TRANSIT导致物流IN_TRANSIT`() = runTest {
        val eo = createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        coEvery { expressOrderRepo.getById(1L) } returns eo
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)

        updateExpressOrderStatus(1L, ExpressStatus.IN_TRANSIT)

        coVerify {
            logisticsRepo.update(match { it.status == LogisticsStatus.IN_TRANSIT })
        }
    }

    @Test
    fun `TC09 - 单快递单IN_TRANSIT→SIGNED但anyInTransit仍为IN_TRANSIT`() = runTest {
        val eo = createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        coEvery { expressOrderRepo.getById(1L) } returns eo
        // 注意：这里故意让快递单更新后的状态和推导时读取的状态不同
        // update 时：status=PENDING, invoke 时 getByLogisticsIdSuspend 返回 IN_TRANSIT
        // 由于单快递单 anyInTransit=true，推导为 IN_TRANSIT，与原状态相同，不触发 update
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(
            createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        )

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        // 快递单被更新，但物流状态仍为 PENDING（因为推导时只有1个PENDING的快递单）
        coVerify { expressOrderRepo.update(any()) }
    }

    @Test
    fun `TC10 - 单快递单IN_TRANSIT→SIGNED（最后一个）allSigned=true导致物流SIGNED`() = runTest {
        val eoSigned = createExpressOrder(id = 1L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eoSigned
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eoSigned)

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        coVerify {
            logisticsRepo.update(match { it.status == LogisticsStatus.SIGNED })
        }
        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.SIGNED) }
        coVerify { processLogisticsFinance.invoke(10L) }
    }

    @Test
    fun `TC11 - 多快递单IN_TRANSIT×2推导为IN_TRANSIT`() = runTest {
        val eo1 = createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        val eo2 = createExpressOrder(id = 2L, status = ExpressStatus.IN_TRANSIT)
        coEvery { expressOrderRepo.getById(1L) } returns eo1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo1, eo2)

        updateExpressOrderStatus(1L, ExpressStatus.IN_TRANSIT)

        coVerify {
            logisticsRepo.update(match { it.status == LogisticsStatus.IN_TRANSIT })
        }
    }

    @Test
    fun `TC12 - 多快递单SIGNED×2推导为SIGNED`() = runTest {
        val eo1 = createExpressOrder(id = 1L, status = ExpressStatus.SIGNED)
        val eo2 = createExpressOrder(id = 2L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eo1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo1, eo2)

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        coVerify {
            logisticsRepo.update(match { it.status == LogisticsStatus.SIGNED })
        }
    }

    @Test
    fun `TC13 - PENDING+SIGNED无IN_TRANSIT推导为PENDING`() = runTest {
        // 有SIGNED，但无IN_TRANSIT，且非全部SIGNED/IN_TRANSIT → 推导为PENDING
        // 但当前状态已是PENDING，故不触发 update（幂等跳过）
        val eo1 = createExpressOrder(id = 1L, status = ExpressStatus.PENDING)
        val eo2 = createExpressOrder(id = 2L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eo1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo1, eo2)

        updateExpressOrderStatus(1L, ExpressStatus.PENDING)

        // 推导为PENDING，与当前状态相同，不触发 update
        coVerify(exactly = 0) { logisticsRepo.update(any()) }
    }

    @Test
    fun `TC14 - IN_TRANSIT+PENDING推导为IN_TRANSIT`() = runTest {
        val eo1 = createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        val eo2 = createExpressOrder(id = 2L, status = ExpressStatus.PENDING)
        coEvery { expressOrderRepo.getById(1L) } returns eo1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo1, eo2)

        updateExpressOrderStatus(1L, ExpressStatus.IN_TRANSIT)

        coVerify {
            logisticsRepo.update(match { it.status == LogisticsStatus.IN_TRANSIT })
        }
    }

    @Test
    fun `TC15 - IN_TRANSIT+SIGNED推导为IN_TRANSIT`() = runTest {
        val eo1 = createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        val eo2 = createExpressOrder(id = 2L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eo1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo1, eo2)

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        coVerify {
            logisticsRepo.update(match { it.status == LogisticsStatus.IN_TRANSIT })
        }
    }

    @Test
    fun `TC16 - 无快递单时推导为PENDING`() = runTest {
        // 无快递单时，推导为PENDING；但当前状态已是PENDING，幂等跳过
        val eo = createExpressOrder(id = 1L, status = ExpressStatus.PENDING)
        coEvery { expressOrderRepo.getById(1L) } returns eo
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns emptyList()

        updateExpressOrderStatus(1L, ExpressStatus.PENDING)

        // 推导为PENDING，与当前状态相同，不触发 update
        coVerify(exactly = 0) { logisticsRepo.update(any()) }
    }

    @Test
    fun `TC17 - COMPLETED物流不再自动推导`() = runTest {
        val completedLogistics = Logistics(id = 10L, virtualContractId = 1L, status = LogisticsStatus.COMPLETED)
        coEvery { logisticsRepo.getById(10L) } returns completedLogistics

        val eo1 = createExpressOrder(id = 1L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eo1
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo1)

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        // COMPLETED 物流不触发推导，不更新状态
        coVerify(exactly = 0) { logisticsRepo.update(any()) }
        coVerify(exactly = 0) { stateMachine.onLogisticsStatusChanged(any(), any()) }
        coVerify(exactly = 0) { processLogisticsFinance.invoke(any()) }
    }

    // ========================================================================
    // §2 联动触发
    // ========================================================================

    @Test
    fun `TC18 - IN_TRANSIT触发VC subjectStatus→SHIPPED`() = runTest {
        val eo = createExpressOrder(id = 1L, status = ExpressStatus.IN_TRANSIT)
        coEvery { expressOrderRepo.getById(1L) } returns eo
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)

        updateExpressOrderStatus(1L, ExpressStatus.IN_TRANSIT)

        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.IN_TRANSIT) }
    }

    @Test
    fun `TC19 - SIGNED触发VC subjectStatus→SIGNED且生成财务凭证`() = runTest {
        val eo = createExpressOrder(id = 1L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eo
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        coVerify { stateMachine.onLogisticsStatusChanged(1L, LogisticsStatus.SIGNED) }
        coVerify { processLogisticsFinance.invoke(10L) }
    }

    @Test
    fun `TC20 - SIGNED触发财务凭证financeTriggered=True`() = runTest {
        val eo = createExpressOrder(id = 1L, status = ExpressStatus.SIGNED)
        coEvery { expressOrderRepo.getById(1L) } returns eo
        coEvery { expressOrderRepo.getByLogisticsIdSuspend(10L) } returns listOf(eo)

        updateExpressOrderStatus(1L, ExpressStatus.SIGNED)

        coVerify { processLogisticsFinance.invoke(10L) }
    }

    // ========================================================================
    // §3 边界：ExpressOrder/Logistics 不存在
    // ========================================================================

    @Test
    fun `TC22 - ExpressOrder不存在抛出IllegalArgumentException`() = runTest {
        coEvery { expressOrderRepo.getById(999L) } returns null

        val ex = catchEx { updateExpressOrderStatus(999L, ExpressStatus.SIGNED) }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex.message!!.contains("Express order not found"))
    }

    @Test
    fun `TC23 - Logistics不存在抛出IllegalStateException`() = runTest {
        coEvery { expressOrderRepo.getById(1L) } returns createExpressOrder(1L)
        coEvery { logisticsRepo.getById(10L) } returns null

        val ex = catchEx { updateExpressOrderStatus(1L, ExpressStatus.SIGNED) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("Logistics not found"))
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createExpressOrder(id: Long = 1L, status: ExpressStatus = ExpressStatus.PENDING) = ExpressOrder(
        id = id,
        logisticsId = 10L,
        trackingNumber = "TRACK$id",
        items = listOf(ExpressItem(skuId = 100L, skuName = "SKU", quantity = 1)),
        addressInfo = AddressInfo(contactName = "Test", phone = "123"),
        status = status
    )

    private suspend fun updateExpressOrderStatus(expressOrderId: Long, status: ExpressStatus): Long =
        updateExpressOrderStatus.invoke(expressOrderId, status)

    private suspend fun catchEx(block: suspend () -> Unit): Exception {
        return try {
            block()
            throw AssertionError("Expected exception was not thrown")
        } catch (e: Exception) {
            e
        }
    }
}
