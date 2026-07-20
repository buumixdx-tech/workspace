package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.SystemEventRepository
import com.shanyin.erp.domain.repository.TimeRuleRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

// ==================== Time Rule Use Cases ====================

class GetAllTimeRulesUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    operator fun invoke(): Flow<List<TimeRule>> = repository.getAll()
}

class GetTimeRuleByIdUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(id: Long): TimeRule? = repository.getById(id)
}

class GetTimeRulesByRelatedUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    operator fun invoke(relatedId: Long, relatedType: RelatedType): Flow<List<TimeRule>> =
        repository.getByRelatedIdAndType(relatedId, relatedType)
}

class GetTimeRulesByTypeUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    operator fun invoke(relatedType: RelatedType): Flow<List<TimeRule>> =
        repository.getByRelatedType(relatedType)
}

class GetTimeRulesByStatusUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    operator fun invoke(status: RuleStatus): Flow<List<TimeRule>> =
        repository.getByStatus(status)
}

class GetTimeRulesByWarningUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    operator fun invoke(warning: WarningLevel): Flow<List<TimeRule>> =
        repository.getByWarning(warning)
}

class SaveTimeRuleUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(rule: TimeRule): Long {
        return if (rule.id == 0L) {
            repository.insert(rule)
        } else {
            repository.update(rule)
            rule.id
        }
    }
}

class DeleteTimeRuleUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(rule: TimeRule) = repository.delete(rule)
}

class UpdateTimeRuleStatusUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(ruleId: Long, status: RuleStatus, result: RuleResult? = null): Long {
        val rule = repository.getById(ruleId)
            ?: throw IllegalArgumentException("Time rule not found")
        val updated = rule.copy(
            status = status,
            result = result,
            resultstamp = if (result != null) System.currentTimeMillis() else rule.resultstamp,
            endstamp = if (status == RuleStatus.ENDED) System.currentTimeMillis() else rule.endstamp
        )
        repository.update(updated)
        return ruleId
    }
}

/**
 * Calculate and update warning levels for all active rules
 */
class UpdateRuleWarningsUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(currentTime: Long = System.currentTimeMillis()): Int {
        var updatedCount = 0
        // This would typically be called by a background worker
        // For now, just return 0 as actual implementation would need flow collection
        return updatedCount
    }
}

/**
 * Create a time rule for a virtual contract
 */
class CreateVcTimeRuleUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(
        vcId: Long,
        triggerEvent: RuleEvent,
        targetEvent: RuleEvent,
        offsetDays: Int,
        unit: TimeUnit = TimeUnit.CALENDAR_DAY,
        direction: Direction = Direction.AFTER
    ): Long {
        val rule = TimeRule(
            relatedId = vcId,
            relatedType = RelatedType.VIRTUAL_CONTRACT,
            triggerEvent = triggerEvent,
            targetEvent = targetEvent,
            offset = offsetDays,
            unit = unit,
            direction = direction,
            status = RuleStatus.ACTIVE
        )
        return repository.insert(rule)
    }
}

// ==================== System Event Use Cases ====================

class GetAllSystemEventsUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    operator fun invoke(): Flow<List<SystemEvent>> = repository.getAll()
}

class GetSystemEventByIdUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    suspend operator fun invoke(id: Long): SystemEvent? = repository.getById(id)
}

class GetSystemEventsByTypeUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    operator fun invoke(eventType: SystemEventType): Flow<List<SystemEvent>> =
        repository.getByEventType(eventType)
}

class GetSystemEventsByAggregateUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    operator fun invoke(aggregateType: String, aggregateId: Long): Flow<List<SystemEvent>> =
        repository.getByAggregate(aggregateType, aggregateId)
}

class RecordSystemEventUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    suspend operator fun invoke(
        eventType: SystemEventType,
        relatedId: Long? = null,
        relatedType: String? = null,
        description: String? = null,
        metadata: String? = null
    ): Long {
        val event = SystemEvent(
            eventType = eventType,
            relatedId = relatedId,
            relatedType = relatedType,
            description = description,
            metadata = metadata
        )
        return repository.insert(event)
    }
}

class GetUnpushedSystemEventsUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    operator fun invoke(limit: Int = 100): Flow<List<SystemEvent>> =
        repository.getUnpushedEvents(limit)
}

class MarkEventAsPushedUseCase @Inject constructor(
    private val repository: SystemEventRepository
) {
    suspend operator fun invoke(eventId: Long) = repository.markAsPushed(eventId)
}

// ==================== Rule Generation Use Cases ====================

/**
 * 根据付款条款自动生成时间规则
 *
 * 规则生成逻辑（与 Desktop generate_rules_from_payment_terms 一致）：
 *   - 预付比例 > 0 → 生成预付约束规则：CASH_PREPAID → SUBJECT_SHIPPED (direction=AFTER, offset=0)
 *   - 所有情况 → 生成结算规则：SUBJECT_FINISH → SUBJECT_CASH_FINISH (direction=BEFORE, offset=账期天数)
 *
 * 字段赋值规范：
 *   - tae_param1：统一赋值为 "付款条款生成"，tae_param2 为 null
 *   - 规则1（预付约束）：tge_param1 = 纯百分数字符串（如 "40%"）
 *   - 规则2（结算规则）：tge_param1 = null，账期天数承载于 offset
 */
class GenerateRulesFromPaymentTermsUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(
        relatedId: Long,
        relatedType: RelatedType,
        prepaymentPercent: Double,   // 0.0 ~ 1.0
        balanceDays: Int,
        dayRule: TimeUnit = TimeUnit.CALENDAR_DAY
    ): Int {
        var count = 0

        // 规则1：预付约束 (prepayment > 0)
        if (prepaymentPercent > 0) {
            val rule = TimeRule(
                relatedId = relatedId,
                relatedType = relatedType,
                inherit = InheritLevel.NEAR,
                party = Party.SELF,
                triggerEvent = RuleEvent.CASH_PREPAID,
                tgeParam1 = "${(prepaymentPercent * 100).toInt()}%",  // 纯百分数
                tgeParam2 = null,
                targetEvent = RuleEvent.SUBJECT_SHIPPED,
                taeParam1 = "付款条款生成",
                taeParam2 = null,
                offset = 0,
                unit = dayRule,
                direction = Direction.AFTER,
                status = RuleStatus.TEMPLATE
            )
            repository.insert(rule)
            count++
        }

        // 规则2：结算规则（始终生成）
        val rule2 = TimeRule(
            relatedId = relatedId,
            relatedType = relatedType,
            inherit = InheritLevel.NEAR,
            party = if (relatedType == RelatedType.BUSINESS) Party.CUSTOMER else Party.SELF,
            triggerEvent = RuleEvent.SUBJECT_FINISH,
            tgeParam1 = null,
            tgeParam2 = null,
            targetEvent = RuleEvent.SUBJECT_CASH_FINISH,
            taeParam1 = "付款条款生成",
            taeParam2 = null,
            offset = balanceDays,
            unit = dayRule,
            direction = Direction.BEFORE,
            status = RuleStatus.TEMPLATE
        )
        repository.insert(rule2)
        count++

        return count
    }
}

/**
 * 从供应链继承模板规则到虚拟合同（近继承）
 *
 * 查询供应链的 TEMPLATE 规则（inherit=NEAR），复制到 VC 上，
 * status 改为 ACTIVE，inherit 保持 NEAR。
 */
class SyncRulesFromSupplyChainUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(supplyChainId: Long, vcId: Long): Int {
        val templates = repository.getTemplateRules(supplyChainId, RelatedType.SUPPLY_CHAIN, InheritLevel.NEAR)
        templates.forEach { tmpl ->
            repository.insert(tmpl.copy(
                id = 0,
                relatedId = vcId,
                relatedType = RelatedType.VIRTUAL_CONTRACT,
                status = RuleStatus.ACTIVE
            ))
        }
        return templates.size
    }
}

/**
 * 从业务继承模板规则到虚拟合同（近继承）
 *
 * 查询业务的 TEMPLATE 规则（inherit=NEAR），复制到 VC 上，
 * status 改为 ACTIVE，inherit 保持 NEAR。
 */
class SyncRulesFromBusinessUseCase @Inject constructor(
    private val repository: TimeRuleRepository
) {
    suspend operator fun invoke(businessId: Long, vcId: Long): Int {
        val templates = repository.getTemplateRules(businessId, RelatedType.BUSINESS, InheritLevel.NEAR)
        templates.forEach { tmpl ->
            repository.insert(tmpl.copy(
                id = 0,
                relatedId = vcId,
                relatedType = RelatedType.VIRTUAL_CONTRACT,
                status = RuleStatus.ACTIVE
            ))
        }
        return templates.size
    }
}

/**
 * 从虚拟合同继承模板规则到物流单（近继承 + 远继承穿透）
 *
 * 逻辑与 Desktop _sync_logistics_from_parent 完全一致：
 *   ① 从 VC 的 TEMPLATE 规则复制（inherit=NEAR）
 *   ② 穿透查询 VC 的父级（Business/SC）的 TEMPLATE 规则（inherit=FAR），
 *      复制到 Logistics，status 改为 ACTIVE，inherit 保持不变。
 */
class SyncRulesFromVirtualContractUseCase @Inject constructor(
    private val timeRuleRepository: TimeRuleRepository,
    private val vcRepository: VirtualContractRepository
) {
    suspend operator fun invoke(vcId: Long, logisticsId: Long): Int {
        val vc = vcRepository.getById(vcId) ?: return 0

        var count = 0

        // ① 从 VC 的 TEMPLATE 规则复制（inherit=NEAR）
        val vcTemplates = timeRuleRepository.getTemplateRules(
            vcId, RelatedType.VIRTUAL_CONTRACT, InheritLevel.NEAR
        )
        for (tmpl in vcTemplates) {
            timeRuleRepository.insert(tmpl.copy(
                id = 0,
                relatedId = logisticsId,
                relatedType = RelatedType.LOGISTICS,
                status = RuleStatus.ACTIVE
            ))
            count++
        }

        // ② 穿透从 Business/SC 的 FAR 规则复制
        val grandparents = mutableListOf<Pair<RelatedType, Long>>()
        vc.businessId?.let { grandparents.add(RelatedType.BUSINESS to it) }
        vc.supplyChainId?.let { grandparents.add(RelatedType.SUPPLY_CHAIN to it) }

        for ((gpType, gpId) in grandparents) {
            val gpTemplates = timeRuleRepository.getTemplateRules(
                gpId, gpType, InheritLevel.FAR
            )
            for (tmpl in gpTemplates) {
                timeRuleRepository.insert(tmpl.copy(
                    id = 0,
                    relatedId = logisticsId,
                    relatedType = RelatedType.LOGISTICS,
                    status = RuleStatus.ACTIVE
                ))
                count++
            }
        }

        return count
    }
}
