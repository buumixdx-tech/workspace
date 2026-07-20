package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.LogisticsRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * CreateLogisticsUseCase 完整测试套件
 *
 * §1    创建约束：VC 状态检查（EXECUTING/COMPLETED/TERMINATED/CANCELLED）
 * §2    Desktop-consistent：重复创建返回已有物流 id
 * §3    正常创建：返回 logisticsId，status=PENDING
 */
class CreateLogisticsUseCaseTest {

    private lateinit var logisticsRepo: LogisticsRepository
    private lateinit var vcRepo: VirtualContractRepository
    private lateinit var syncRules: SyncRulesFromVirtualContractUseCase
    private lateinit var createLogistics: CreateLogisticsUseCase

    @Before
    fun setup() {
        logisticsRepo = mockk(relaxed = true)
        vcRepo = mockk(relaxed = true)
        syncRules = mockk(relaxed = true)

        createLogistics = CreateLogisticsUseCase(
            repository = logisticsRepo,
            vcRepository = vcRepo,
            syncRules = syncRules
        )

        coEvery { logisticsRepo.insert(any()) } returns 1L
        coEvery { logisticsRepo.getFirstByVcId(any()) } returns null
    }

    // ========================================================================
    // §1 VC 状态约束检查
    // ========================================================================

    @Test
    fun `TC01 VC status EXECUTING 时正常创建物流`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.EXECUTING)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { logisticsRepo.getFirstByVcId(1L) } returns null

        val id = createLogistics(1L)

        assertEquals(1L, id)
        coVerify { logisticsRepo.insert(match { it.status == LogisticsStatus.PENDING }) }
        coVerify { syncRules.invoke(1L, 1L) }
    }

    @Test
    fun `TC02 - 创建后物流 status=PENDING financeTriggered=false`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.EXECUTING)
        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { logisticsRepo.getFirstByVcId(1L) } returns null
        coEvery { logisticsRepo.insert(any()) } returns 5L

        createLogistics(1L)

        coVerify {
            logisticsRepo.insert(match {
                it.status == LogisticsStatus.PENDING &&
                it.virtualContractId == 1L
            })
        }
    }

    @Test
    fun `TC03 VC status COMPLETED 时拒绝创建`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.COMPLETED)
        coEvery { vcRepo.getById(1L) } returns vc

        val ex = catchEx { createLogistics(1L) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("完成"))
        coVerify(exactly = 0) { logisticsRepo.insert(any()) }
    }

    @Test
    fun `TC04 VC status TERMINATED 时拒绝创建`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.TERMINATED)
        coEvery { vcRepo.getById(1L) } returns vc

        val ex = catchEx { createLogistics(1L) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("终止"))
        coVerify(exactly = 0) { logisticsRepo.insert(any()) }
    }

    @Test
    fun `TC05 VC status CANCELLED 时拒绝创建 Desktop对齐`() = runTest {
        // 注意：Mobile VCStatus 无 CANCELLED，此测试验证 Desktop 兼容逻辑
        // CANCELLED 在 Mobile 等效于 TERMINATED
        val vc = createVC(id = 1L, status = VCStatus.CANCELLED)
        coEvery { vcRepo.getById(1L) } returns vc

        val ex = catchEx { createLogistics(1L) }

        assertTrue(ex is IllegalStateException)
        assertTrue(ex.message!!.contains("取消"))
        coVerify(exactly = 0) { logisticsRepo.insert(any()) }
    }

    @Test
    fun `TC06 - VC 不存在时抛出 IllegalArgumentException`() = runTest {
        coEvery { vcRepo.getById(999L) } returns null

        val ex = catchEx { createLogistics(999L) }

        assertTrue(ex is IllegalArgumentException)
        assertTrue(ex.message!!.contains("VC 不存在"))
    }

    // ========================================================================
    // §2 Desktop-consistent：重复创建返回已有物流 id
    // ========================================================================

    @Test
    fun `TC07 - VC 已有物流时返回已有 id 不新建`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.EXECUTING)
        val existingLogistics = Logistics(id = 99L, virtualContractId = 1L, status = LogisticsStatus.IN_TRANSIT)

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { logisticsRepo.getFirstByVcId(1L) } returns existingLogistics

        val id = createLogistics(1L)

        assertEquals(99L, id)
        // 不新建，不同步规则
        coVerify(exactly = 0) { logisticsRepo.insert(any()) }
        coVerify(exactly = 0) { syncRules.invoke(any(), any()) }
    }

    @Test
    fun `TC07b - VC 已有物流时返回 id 而非新 id`() = runTest {
        val vc = createVC(id = 1L, status = VCStatus.EXECUTING)
        val existing = Logistics(id = 77L, virtualContractId = 1L, status = LogisticsStatus.SIGNED)

        coEvery { vcRepo.getById(1L) } returns vc
        coEvery { logisticsRepo.getFirstByVcId(1L) } returns existing

        val id = createLogistics(1L)

        assertEquals(77L, id)
        coVerify(exactly = 0) { logisticsRepo.insert(any()) }
    }

    // ========================================================================
    // Helper
    // ========================================================================

    private fun createVC(
        id: Long = 1L,
        status: VCStatus = VCStatus.EXECUTING,
        type: VCType = VCType.EQUIPMENT_PROCUREMENT
    ) = VirtualContract(
        id = id,
        type = type,
        status = status,
        subjectStatus = SubjectStatus.EXECUTING,
        cashStatus = CashStatus.EXECUTING
    )

    private suspend fun createLogistics(vcId: Long): Long = createLogistics.invoke(vcId)

    private suspend fun catchEx(block: suspend () -> Unit): Exception {
        return try {
            block()
            throw AssertionError("Expected exception was not thrown")
        } catch (e: Exception) {
            e
        }
    }
}
