package com.shanyin.erp.domain.usecase

import com.google.gson.Gson
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.VCStatusLogRepository
import com.shanyin.erp.domain.repository.VCHistoryRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ApplyOffsetToVcUseCase
import com.shanyin.erp.domain.usecase.finance.GetOffsetPoolUseCase
import com.shanyin.erp.domain.usecase.finance.OffsetPoolType
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject

// ==================== VirtualContract Use Cases ====================

class GetAllVirtualContractsUseCase @Inject constructor(
    private val repository: VirtualContractRepository
) {
    operator fun invoke(): Flow<List<VirtualContract>> = repository.getAll()
}

class GetVirtualContractByIdUseCase @Inject constructor(
    private val repository: VirtualContractRepository
) {
    suspend operator fun invoke(id: Long): VirtualContract? = repository.getById(id)
}

class GetVirtualContractsByBusinessUseCase @Inject constructor(
    private val repository: VirtualContractRepository
) {
    operator fun invoke(businessId: Long): Flow<List<VirtualContract>> = repository.getByBusinessId(businessId)
}

class GetVirtualContractsByStatusUseCase @Inject constructor(
    private val repository: VirtualContractRepository
) {
    operator fun invoke(status: VCStatus): Flow<List<VirtualContract>> = repository.getByStatus(status)
}

class GetVirtualContractsByTypeUseCase @Inject constructor(
    private val repository: VirtualContractRepository
) {
    operator fun invoke(type: VCType): Flow<List<VirtualContract>> = repository.getByType(type)
}

class SaveVirtualContractUseCase @Inject constructor(
    private val repository: VirtualContractRepository,
    private val historyRepository: VCHistoryRepository,
    private val gson: Gson
) {
    suspend operator fun invoke(vc: VirtualContract, changeReason: String? = null): Long {
        return if (vc.id == 0L) {
            repository.insert(vc)
        } else {
            // Save history before update
            val existing = repository.getById(vc.id)
            if (existing != null) {
                historyRepository.insert(
                    VCHistory(
                        vcId = vc.id,
                        originalData = gson.toJson(existing),
                        changeReason = changeReason
                    )
                )
            }
            repository.update(vc)
            vc.id
        }
    }
}

class DeleteVirtualContractUseCase @Inject constructor(
    private val repository: VirtualContractRepository
) {
    suspend operator fun invoke(vc: VirtualContract) = repository.delete(vc)
}

/**
 * 更新主状态
 */
class UpdateVCStatusUseCase @Inject constructor(
    private val repository: VirtualContractRepository,
    private val logRepository: VCStatusLogRepository
) {
    suspend operator fun invoke(vcId: Long, newStatus: VCStatus): Result<VirtualContract> {
        val vc = repository.getById(vcId)
            ?: return Result.failure(IllegalArgumentException("虚拟合同不存在"))

        val updatedVc = vc.copy(
            status = newStatus,
            statusTimestamp = System.currentTimeMillis()
        )
        repository.update(updatedVc)

        logRepository.insert(
            VCStatusLog(
                vcId = vcId,
                category = StatusLogCategory.STATUS,
                statusName = newStatus.displayName
            )
        )

        return Result.success(updatedVc)
    }
}

/**
 * 更新标的物状态
 */
class UpdateVCSubjectStatusUseCase @Inject constructor(
    private val repository: VirtualContractRepository,
    private val logRepository: VCStatusLogRepository
) {
    suspend operator fun invoke(vcId: Long, newStatus: SubjectStatus): Result<VirtualContract> {
        val vc = repository.getById(vcId)
            ?: return Result.failure(IllegalArgumentException("虚拟合同不存在"))

        val updatedVc = vc.copy(
            subjectStatus = newStatus,
            subjectStatusTimestamp = System.currentTimeMillis()
        )
        repository.update(updatedVc)

        logRepository.insert(
            VCStatusLog(
                vcId = vcId,
                category = StatusLogCategory.SUBJECT,
                statusName = newStatus.displayName
            )
        )

        return Result.success(updatedVc)
    }
}

/**
 * 更新资金状态
 */
class UpdateVCCashStatusUseCase @Inject constructor(
    private val repository: VirtualContractRepository,
    private val logRepository: VCStatusLogRepository
) {
    suspend operator fun invoke(vcId: Long, newStatus: CashStatus): Result<VirtualContract> {
        val vc = repository.getById(vcId)
            ?: return Result.failure(IllegalArgumentException("虚拟合同不存在"))

        val updatedVc = vc.copy(
            cashStatus = newStatus,
            cashStatusTimestamp = System.currentTimeMillis()
        )
        repository.update(updatedVc)

        logRepository.insert(
            VCStatusLog(
                vcId = vcId,
                category = StatusLogCategory.CASH,
                statusName = newStatus.displayName
            )
        )

        return Result.success(updatedVc)
    }
}

/**
 * 获取VC状态日志
 */
class GetVCStatusLogsUseCase @Inject constructor(
    private val repository: VCStatusLogRepository
) {
    operator fun invoke(vcId: Long): Flow<List<VCStatusLog>> = repository.getByVcId(vcId)
}

/**
 * 获取VC历史版本
 */
class GetVCHistoryUseCase @Inject constructor(
    private val repository: VCHistoryRepository
) {
    operator fun invoke(vcId: Long): Flow<List<VCHistory>> = repository.getByVcId(vcId)
}

/**
 * 完成虚拟合同 - 自动设置所有状态为完成
 */
class CompleteVirtualContractUseCase @Inject constructor(
    private val repository: VirtualContractRepository,
    private val logRepository: VCStatusLogRepository
) {
    suspend operator fun invoke(vcId: Long): Result<VirtualContract> {
        val vc = repository.getById(vcId)
            ?: return Result.failure(IllegalArgumentException("虚拟合同不存在"))

        if (vc.status == VCStatus.COMPLETED) {
            return Result.failure(IllegalStateException("合同已完成"))
        }

        val now = System.currentTimeMillis()
        val updatedVc = vc.copy(
            status = VCStatus.COMPLETED,
            subjectStatus = SubjectStatus.COMPLETED,
            cashStatus = CashStatus.COMPLETED,
            statusTimestamp = now,
            subjectStatusTimestamp = now,
            cashStatusTimestamp = now
        )
        repository.update(updatedVc)

        // Log all status changes
        logRepository.insert(VCStatusLog(vcId = vcId, category = StatusLogCategory.STATUS, statusName = VCStatus.COMPLETED.displayName))
        logRepository.insert(VCStatusLog(vcId = vcId, category = StatusLogCategory.SUBJECT, statusName = SubjectStatus.COMPLETED.displayName))
        logRepository.insert(VCStatusLog(vcId = vcId, category = StatusLogCategory.CASH, statusName = CashStatus.COMPLETED.displayName))

        return Result.success(updatedVc)
    }
}

/**
 * 终止虚拟合同
 */
class TerminateVirtualContractUseCase @Inject constructor(
    private val repository: VirtualContractRepository,
    private val logRepository: VCStatusLogRepository
) {
    suspend operator fun invoke(vcId: Long): Result<VirtualContract> {
        val vc = repository.getById(vcId)
            ?: return Result.failure(IllegalArgumentException("虚拟合同不存在"))

        if (vc.status == VCStatus.TERMINATED) {
            return Result.failure(IllegalStateException("合同已终止"))
        }

        val updatedVc = vc.copy(
            status = VCStatus.TERMINATED,
            statusTimestamp = System.currentTimeMillis()
        )
        repository.update(updatedVc)

        logRepository.insert(
            VCStatusLog(vcId = vcId, category = StatusLogCategory.STATUS, statusName = VCStatus.TERMINATED.displayName)
        )

        return Result.success(updatedVc)
    }
}

/**
 * 创建设备采购合同
 */
class CreateEquipmentProcurementVCUseCase @Inject constructor(
    private val saveVC: SaveVirtualContractUseCase,
    private val syncFromBusiness: SyncRulesFromBusinessUseCase,
    private val applyOffset: ApplyOffsetToVcUseCase,
    private val getOffsetPool: GetOffsetPoolUseCase
) {
    suspend operator fun invoke(
        businessId: Long?,
        description: String,
        elements: List<VCElement>,
        depositInfo: DepositInfo = DepositInfo()
    ): Long {
        val vc = VirtualContract(
            businessId = businessId,
            type = VCType.EQUIPMENT_PROCUREMENT,
            description = description,
            elements = elements,
            depositInfo = depositInfo
        )
        val vcId = saveVC(vc, "创建设备采购合同")

        // 从业务继承模板规则
        businessId?.let { syncFromBusiness(it, vcId) }

        // 自动应用核销池（预付账款-供应商 → 核销应付设备款）
        applyOffsetPoolIfAvailable(vcId, depositInfo.totalAmount)

        return vcId
    }

    private suspend fun applyOffsetPoolIfAvailable(vcId: Long, totalAmount: Double) {
        try {
            val pool = getOffsetPool(OffsetPoolType.PREPAYMENT)
            if (pool.availableBalance > 0.01) {
                val applyAmount = minOf(pool.availableBalance, totalAmount)
                applyOffset(vcId, applyAmount, OffsetPoolType.PREPAYMENT)
            }
        } catch (e: Exception) {
            // 核销失败不影响 VC 创建
        }
    }
}

/**
 * 创建物料供应合同
 */
class CreateMaterialSupplyVCUseCase @Inject constructor(
    private val saveVC: SaveVirtualContractUseCase,
    private val syncFromBusiness: SyncRulesFromBusinessUseCase,
    private val syncFromSupplyChain: SyncRulesFromSupplyChainUseCase,
    private val applyOffset: ApplyOffsetToVcUseCase,
    private val getOffsetPool: GetOffsetPoolUseCase
) {
    suspend operator fun invoke(
        businessId: Long?,
        supplyChainId: Long,
        description: String,
        elements: List<VCElement>,
        depositInfo: DepositInfo = DepositInfo()
    ): Long {
        val vc = VirtualContract(
            businessId = businessId,
            supplyChainId = supplyChainId,
            type = VCType.MATERIAL_SUPPLY,
            description = description,
            elements = elements,
            depositInfo = depositInfo
        )
        val vcId = saveVC(vc, "创建物料供应合同")

        // 从业务继承模板规则
        businessId?.let { syncFromBusiness(it, vcId) }
        // 从供应链继承模板规则
        syncFromSupplyChain(supplyChainId, vcId)

        // 自动应用核销池（预收账款-客户 → 冲抵应收货款）
        applyOffsetPoolIfAvailable(vcId, depositInfo.totalAmount)

        return vcId
    }

    private suspend fun applyOffsetPoolIfAvailable(vcId: Long, totalAmount: Double) {
        try {
            val pool = getOffsetPool(OffsetPoolType.PRE_COLLECTION)
            if (pool.availableBalance > 0.01) {
                val applyAmount = minOf(pool.availableBalance, totalAmount)
                applyOffset(vcId, applyAmount, OffsetPoolType.PRE_COLLECTION)
            }
        } catch (e: Exception) {
            // 核销失败不影响 VC 创建
        }
    }
}

/**
 * 创建退货合同
 */
class CreateReturnVCUseCase @Inject constructor(
    private val saveVC: SaveVirtualContractUseCase,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val applyOffset: ApplyOffsetToVcUseCase,
    private val getOffsetPool: GetOffsetPoolUseCase
) {
    suspend operator fun invoke(
        relatedVcId: Long,
        description: String,
        elements: List<VCElement>,
        returnDirection: ReturnDirection = ReturnDirection.CUSTOMER_TO_US
    ): Long {
        val vc = VirtualContract(
            relatedVcId = relatedVcId,
            type = VCType.RETURN,
            description = description,
            elements = elements,
            returnDirection = returnDirection
        )
        val vcId = saveVC(vc, "创建退货合同")

        // 自动应用核销池
        // CUSTOMER_TO_US: 我们退款给客户 → 核销预付账款(供应商)冲抵应付
        // US_TO_SUPPLIER: 供应商退款给我们 → 核销预收账款(客户)冲抵应收
        val offsetType = when (returnDirection) {
            ReturnDirection.US_TO_SUPPLIER -> OffsetPoolType.PRE_COLLECTION
            ReturnDirection.CUSTOMER_TO_US -> OffsetPoolType.PREPAYMENT
        }
        applyOffsetPoolIfAvailable(vcId, 0.0, offsetType)

        return vcId
    }

    private suspend fun applyOffsetPoolIfAvailable(vcId: Long, totalAmount: Double, offsetType: OffsetPoolType) {
        try {
            val pool = getOffsetPool(offsetType)
            if (pool.availableBalance > 0.01) {
                val applyAmount = minOf(pool.availableBalance, totalAmount.coerceAtLeast(pool.availableBalance))
                if (applyAmount > 0.01) {
                    applyOffset(vcId, applyAmount, offsetType)
                }
            }
        } catch (e: Exception) {
            // 核销失败不影响 VC 创建
        }
    }
}
