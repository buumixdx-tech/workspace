package com.shanyin.erp.domain.usecase.rule_engine

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.*
import javax.inject.Inject

/**
 * 事件处理模块
 *
 * 职责：查询任意事件的发生时间
 * 入参：事件类型、关联对象类型、关联对象ID、可选参数
 * 返回：事件发生时间 (Long/epoch millis) 或 null（未发生）
 *
 * 与 Desktop event_handler.py 完全对齐。
 */
class EventHandler @Inject constructor(
    private val vcRepository: VirtualContractRepository,
    private val vcStatusLogRepository: VCStatusLogRepository,
    private val logisticsRepository: LogisticsRepository,
    private val expressOrderRepository: ExpressOrderRepository,
    private val cashFlowRepository: CashFlowRepository
) {

    /**
     * 获取事件发生时间
     *
     * @param eventType    事件类型（如 SUBJECT_SHIPPED）
     * @param relatedType  关联对象类型
     * @param relatedId   关联对象 ID
     * @param param1      可选参数1（如付款比例字符串 "0.4"）
     * @param param2      可选参数2
     * @return 事件发生时间（epoch millis），未发生返回 null
     */
    suspend fun getEventTime(
        eventType: RuleEvent,
        relatedType: RelatedType,
        relatedId: Long,
        param1: String? = null,
        param2: String? = null
    ): Long? {
        // 特殊事件：绝对日期模式不需要查询
        if (eventType == RuleEvent.ABSOLUTE_DATE) return null

        val result: Long? = when (eventType) {
            RuleEvent.CONTRACT_SIGNED -> checkContractSigned(relatedType, relatedId)
            RuleEvent.CONTRACT_EFFECTIVE -> checkContractEffective(relatedType, relatedId)
            RuleEvent.CONTRACT_EXPIRY -> checkContractExpiry(relatedType, relatedId)
            RuleEvent.CONTRACT_RENEWED -> null
            RuleEvent.CONTRACT_TERMINATED -> null
            RuleEvent.VC_CREATED -> checkVcCreated(relatedType, relatedId)
            RuleEvent.VC_STATUS_EXE -> checkVcStatusExe(relatedType, relatedId)
            RuleEvent.VC_STATUS_FINISH -> checkVcStatusFinish(relatedType, relatedId)
            RuleEvent.SUBJECT_SHIPPED -> checkSubjectShipped(relatedType, relatedId)
            RuleEvent.SUBJECT_SIGNED -> checkSubjectSigned(relatedType, relatedId)
            RuleEvent.SUBJECT_FINISH -> checkSubjectFinish(relatedType, relatedId)
            RuleEvent.CASH_PREPAID -> checkCashPrepaid(relatedType, relatedId)
            RuleEvent.CASH_FINISH -> checkCashFinish(relatedType, relatedId)
            RuleEvent.SUBJECT_CASH_FINISH -> checkSubjectCashFinish(relatedType, relatedId)
            RuleEvent.DEPOSIT_RECEIVED -> checkDepositReceived(relatedType, relatedId)
            RuleEvent.DEPOSIT_RETURNED -> checkDepositReturned(relatedType, relatedId)
            RuleEvent.PAYMENT_RATIO_REACHED -> checkPaymentRatioReached(relatedType, relatedId, param1)
            RuleEvent.LOGISTICS_CREATED -> checkLogisticsCreated(relatedType, relatedId)
            RuleEvent.LOGISTICS_PENDING -> checkLogisticsPending(relatedType, relatedId)
            RuleEvent.LOGISTICS_SHIPPED -> checkLogisticsShipped(relatedType, relatedId)
            RuleEvent.LOGISTICS_SIGNED -> checkLogisticsSigned(relatedType, relatedId)
            RuleEvent.LOGISTICS_FINISH -> checkLogisticsFinish(relatedType, relatedId)
            RuleEvent.EXPRESS_CREATED -> null
            RuleEvent.EXPRESS_SHIPPED -> null
            RuleEvent.EXPRESS_SIGNED -> null
            RuleEvent.ABSOLUTE_DATE -> null
        }
        return result
    }

    // =========================================================================
    // 辅助方法：关联ID解析
    // =========================================================================

    /** 将不同关联类型解析到虚拟合同 ID */
    private suspend fun resolveToVcId(relatedType: RelatedType, relatedId: Long): Long? {
        return when (relatedType) {
            RelatedType.VIRTUAL_CONTRACT -> relatedId
            RelatedType.LOGISTICS -> {
                val logistics = logisticsRepository.getById(relatedId)
                logistics?.virtualContractId
            }
            else -> null  // BUSINESS / SUPPLY_CHAIN 级别不支持
        }
    }

    /** 将不同关联类型解析到物流 ID */
    private fun resolveToLogisticsId(relatedType: RelatedType, relatedId: Long): Long? {
        return when (relatedType) {
            RelatedType.LOGISTICS -> relatedId
            else -> null
        }
    }

    // =========================================================================
    // 合同级事件处理器
    // =========================================================================

    /** 检查合同签订时间（返回 VC 创建时间作为代理） */
    private suspend fun checkContractSigned(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcRepository.getById(vcId)?.statusTimestamp
    }

    /** 检查合同生效时间（同签订时间） */
    private suspend fun checkContractEffective(relatedType: RelatedType, relatedId: Long): Long? {
        return checkContractSigned(relatedType, relatedId)
    }

    /** 检查合同到期时间（暂不支持） */
    private suspend fun checkContractExpiry(relatedType: RelatedType, relatedId: Long): Long? {
        return null  // TODO: Contract 表需有 expiry_date 字段
    }

    // =========================================================================
    // 虚拟合同级事件处理器
    // =========================================================================

    /** 检查虚拟合同创建时间 */
    private suspend fun checkVcCreated(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcRepository.getById(vcId)?.statusTimestamp
    }

    /** 检查虚拟合同进入执行状态时间 */
    private suspend fun checkVcStatusExe(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.STATUS, VCStatus.EXECUTING.displayName
        )?.timestamp
    }

    /** 检查虚拟合同完成时间 */
    private suspend fun checkVcStatusFinish(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.STATUS, VCStatus.COMPLETED.displayName
        )?.timestamp
    }

    /** 检查发货时间（标的物状态变为 SHIPPED） */
    private suspend fun checkSubjectShipped(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.SUBJECT, SubjectStatus.SHIPPED.displayName
        )?.timestamp
    }

    /** 检查签收时间 */
    private suspend fun checkSubjectSigned(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.SUBJECT, SubjectStatus.SIGNED.displayName
        )?.timestamp
    }

    /** 检查标的完成时间 */
    private suspend fun checkSubjectFinish(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.SUBJECT, SubjectStatus.COMPLETED.displayName
        )?.timestamp
    }

    /** 检查预付完成时间（cash_status 变为 PREPAID） */
    private suspend fun checkCashPrepaid(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.CASH, CashStatus.PREPAID.displayName
        )?.timestamp
    }

    /** 检查款项结清时间（cash_status 变为 COMPLETED） */
    private suspend fun checkCashFinish(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        return vcStatusLogRepository.getEarliestByCategoryAndStatus(
            vcId, StatusLogCategory.CASH, CashStatus.COMPLETED.displayName
        )?.timestamp
    }

    /** 检查货款结清时间（预付+履约达到100%） */
    private suspend fun checkSubjectCashFinish(relatedType: RelatedType, relatedId: Long): Long? {
        return checkPaymentRatioReached(relatedType, relatedId, "1.0")
    }

    /** 检查押金收齐时间 */
    private suspend fun checkDepositReceived(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        val vc = vcRepository.getById(vcId) ?: return null
        val depositInfo = vc.depositInfo
        val shouldReceive = depositInfo.expectedDeposit  // 应收押金

        if (shouldReceive <= 0) return null

        // 查询所有押金类资金流，累加到达标的时间点
        val cashFlows = cashFlowRepository.getByVcIdAndTypes(
            vcId, listOf(CashFlowType.DEPOSIT)
        )

        var cumulative = 0.0
        for (cf in cashFlows) {
            cumulative += cf.amount
            if (cumulative >= shouldReceive - 0.01) {
                return cf.transactionDate
            }
        }
        return null
    }

    /** 检查押金退还时间（最后一笔退还押金的时间） */
    private suspend fun checkDepositReturned(relatedType: RelatedType, relatedId: Long): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        val cashFlows = cashFlowRepository.getByVcIdAndTypes(
            vcId, listOf(CashFlowType.DEPOSIT_REFUND)
        )
        return cashFlows.maxByOrNull { it.transactionDate ?: 0 }?.transactionDate
    }

    /** 检查付款比例是否达到指定值 */
    private suspend fun checkPaymentRatioReached(
        relatedType: RelatedType,
        relatedId: Long,
        ratioParam: String?
    ): Long? {
        val vcId = resolveToVcId(relatedType, relatedId) ?: return null
        val vc = vcRepository.getById(vcId) ?: return null

        val targetRatio = ratioParam?.toDoubleOrNull() ?: 0.5
        val totalAmount = vc.elements.sumOf { (it as? SkusFormatElement)?.subtotal ?: 0.0 }

        if (totalAmount <= 0) return null

        // 查询所有资金流（预付/履约/退款/冲抵）
        val types = listOf(
            CashFlowType.PREPAYMENT,
            CashFlowType.PERFORMANCE,
            CashFlowType.REFUND,
            CashFlowType.OFFSET_INFLOW,
            CashFlowType.OFFSET_OUTFLOW
        )
        val cashFlows = cashFlowRepository.getByVcIdAndTypes(vcId, types)
            .filter { it.transactionDate != null }
            .sortedBy { it.transactionDate }

        var cumulative = 0.0
        for (cf in cashFlows) {
            val amount = if (cf.type == CashFlowType.REFUND) -cf.amount else cf.amount
            cumulative += amount
            if (totalAmount > 0 && cumulative / totalAmount >= targetRatio) {
                return cf.transactionDate
            }
        }
        return null
    }

    // =========================================================================
    // 物流级事件处理器
    // =========================================================================

    /** 检查物流创建时间 */
    private suspend fun checkLogisticsCreated(relatedType: RelatedType, relatedId: Long): Long? {
        val logisticsId = resolveToLogisticsId(relatedType, relatedId) ?: return null
        return logisticsRepository.getById(logisticsId)?.timestamp
    }

    /** 检查物流待发货时间（即创建时间） */
    private suspend fun checkLogisticsPending(relatedType: RelatedType, relatedId: Long): Long? {
        return checkLogisticsCreated(relatedType, relatedId)
    }

    /** 检查物流已发货时间（所有快递都不在待发货状态） */
    private suspend fun checkLogisticsShipped(relatedType: RelatedType, relatedId: Long): Long? {
        val logisticsId = resolveToLogisticsId(relatedType, relatedId) ?: return null
        val expressOrders = expressOrderRepository.getByLogisticsIdSuspend(logisticsId)

        if (expressOrders.isEmpty()) return null

        // 严格逻辑：所有快递必须都在"在途"或"签收"状态
        val allShipped = expressOrders.all {
            it.status == ExpressStatus.IN_TRANSIT || it.status == ExpressStatus.SIGNED
        }
        if (allShipped) {
            return expressOrders.maxOfOrNull { it.timestamp }
        }
        return null
    }

    /** 检查物流已签收时间（所有快递都签收） */
    private suspend fun checkLogisticsSigned(relatedType: RelatedType, relatedId: Long): Long? {
        val logisticsId = resolveToLogisticsId(relatedType, relatedId) ?: return null
        val expressOrders = expressOrderRepository.getByLogisticsIdSuspend(logisticsId)

        if (expressOrders.isEmpty()) return null

        if (expressOrders.all { it.status == ExpressStatus.SIGNED }) {
            return expressOrders.maxOfOrNull { it.timestamp }
        }
        return null
    }

    /** 检查物流完成时间 */
    private suspend fun checkLogisticsFinish(relatedType: RelatedType, relatedId: Long): Long? {
        val logisticsId = resolveToLogisticsId(relatedType, relatedId) ?: return null
        val logistics = logisticsRepository.getById(logisticsId) ?: return null
        return if (logistics.status == LogisticsStatus.COMPLETED) logistics.timestamp else null
    }
}
