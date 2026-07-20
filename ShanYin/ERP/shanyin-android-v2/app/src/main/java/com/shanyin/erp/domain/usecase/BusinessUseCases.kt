package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.BusinessRepository
import com.shanyin.erp.domain.repository.ContractRepository
import kotlinx.coroutines.flow.Flow
import android.util.Log
import javax.inject.Inject

// ==================== Business Use Cases ====================

class GetAllBusinessesUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    operator fun invoke(): Flow<List<Business>> = repository.getAll()
}

class GetBusinessByIdUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(id: Long): Business? = repository.getById(id)
}

class GetBusinessesByCustomerUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    operator fun invoke(customerId: Long): Flow<List<Business>> = repository.getByCustomerId(customerId)
}

class GetBusinessesByStatusUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    operator fun invoke(status: BusinessStatus): Flow<List<Business>> = repository.getByStatus(status)
}

class SaveBusinessUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(business: Business): Long {
        return if (business.id == 0L) {
            repository.insert(business)
        } else {
            repository.update(business)
            business.id
        }
    }
}

/**
 * 创建业务（含付款条款规则生成）
 */
class CreateBusinessUseCase @Inject constructor(
    private val saveBusiness: SaveBusinessUseCase,
    private val generateRules: GenerateRulesFromPaymentTermsUseCase
) {
    suspend operator fun invoke(business: Business): Long {
        val businessId = saveBusiness(business)

        // 生成付款条款时间规则
        business.details.paymentTerms?.let { pt ->
            if (pt.prepaymentRatio > 0 || pt.balancePeriod > 0) {
                generateRules(
                    relatedId = businessId,
                    relatedType = RelatedType.BUSINESS,
                    prepaymentPercent = pt.prepaymentRatio,
                    balanceDays = pt.balancePeriod
                )
            }
        }

        return businessId
    }
}

class DeleteBusinessUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(business: Business) = repository.delete(business)
}

/**
 * 推进业务阶段
 */
class AdvanceBusinessStageUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(businessId: Long, reason: String? = null): Result<Business> {
        val business = repository.getById(businessId)
            ?: return Result.failure(IllegalArgumentException("业务不存在"))

        val currentStatus = business.status
            ?: return Result.failure(IllegalStateException("业务状态异常"))

        val nextStatus = BusinessStatus.getNext(currentStatus)
            ?: return Result.failure(IllegalStateException("当前阶段不能推进"))

        val transition = StageTransition(
            from = currentStatus,
            to = nextStatus,
            comment = reason
        )

        val updatedBusiness = business.copy(
            status = nextStatus,
            details = business.details.copy(
                history = business.details.history + transition
            )
        )

        repository.update(updatedBusiness)
        return Result.success(updatedBusiness)
    }
}

/**
 * 暂停业务
 */
class SuspendBusinessUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(businessId: Long, reason: String? = null): Result<Business> {
        val business = repository.getById(businessId)
            ?: return Result.failure(IllegalArgumentException("业务不存在"))

        val currentStatus = business.status
            ?: return Result.failure(IllegalStateException("业务状态异常"))

        if (!BusinessStatus.canSuspend(currentStatus)) {
            return Result.failure(IllegalStateException("当前阶段不能暂停"))
        }

        val transition = StageTransition(
            from = currentStatus,
            to = BusinessStatus.SUSPENDED,
            comment = reason
        )

        val updatedBusiness = business.copy(
            status = BusinessStatus.SUSPENDED,
            details = business.details.copy(
                history = business.details.history + transition
            )
        )

        repository.update(updatedBusiness)
        return Result.success(updatedBusiness)
    }
}

/**
 * 终止业务
 */
class TerminateBusinessUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(businessId: Long, reason: String? = null): Result<Business> {
        val business = repository.getById(businessId)
            ?: return Result.failure(IllegalArgumentException("业务不存在"))

        val currentStatus = business.status
            ?: return Result.failure(IllegalStateException("业务状态异常"))

        if (!BusinessStatus.canTerminate(currentStatus)) {
            return Result.failure(IllegalStateException("当前状态不能终止"))
        }

        val transition = StageTransition(
            from = currentStatus,
            to = BusinessStatus.TERMINATED,
            comment = reason
        )

        val updatedBusiness = business.copy(
            status = BusinessStatus.TERMINATED,
            details = business.details.copy(
                history = business.details.history + transition
            )
        )

        repository.update(updatedBusiness)
        return Result.success(updatedBusiness)
    }
}

/**
 * 重新激活业务
 */
class ReactivateBusinessUseCase @Inject constructor(
    private val repository: BusinessRepository
) {
    suspend operator fun invoke(businessId: Long, reason: String? = null): Result<Business> {
        val business = repository.getById(businessId)
            ?: return Result.failure(IllegalArgumentException("业务不存在"))

        val currentStatus = business.status
            ?: return Result.failure(IllegalStateException("业务状态异常"))

        if (currentStatus != BusinessStatus.SUSPENDED) {
            return Result.failure(IllegalStateException("只有暂停状态可以重新激活"))
        }

        // 找到暂停前的状态（history 中最近一条转到 SUSPENDED 的 from）
        val previousStatus = business.details.history
            .filter { it.to == BusinessStatus.SUSPENDED }
            .lastOrNull()
            ?.from
            ?: BusinessStatus.INITIAL_CONTACT

        val transition = StageTransition(
            from = currentStatus,
            to = previousStatus,
            comment = reason
        )

        val updatedBusiness = business.copy(
            status = previousStatus,
            details = business.details.copy(
                history = business.details.history + transition
            )
        )

        repository.update(updatedBusiness)
        return Result.success(updatedBusiness)
    }
}

// ==================== Contract Use Cases ====================

class GetAllContractsUseCase @Inject constructor(
    private val repository: ContractRepository
) {
    operator fun invoke(): Flow<List<Contract>> = repository.getAll()
}

class GetContractByIdUseCase @Inject constructor(
    private val repository: ContractRepository
) {
    suspend operator fun invoke(id: Long): Contract? = repository.getById(id)
}

class GetContractByNumberUseCase @Inject constructor(
    private val repository: ContractRepository
) {
    suspend operator fun invoke(contractNumber: String): Contract? = repository.getByContractNumber(contractNumber)
}

class SaveContractUseCase @Inject constructor(
    private val repository: ContractRepository
) {
    suspend operator fun invoke(contract: Contract): Long {
        return if (contract.id == 0L) {
            repository.insert(contract)
        } else {
            repository.update(contract)
            contract.id
        }
    }
}

class DeleteContractUseCase @Inject constructor(
    private val repository: ContractRepository
) {
    suspend operator fun invoke(contract: Contract) = repository.delete(contract)
}
