package com.shanyin.erp.domain.usecase.rule_engine

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.TimeRuleRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject

/**
 * 时间规则引擎主入口
 *
 * 职责（与 Desktop engine.py 的 TimeRuleEngine 完全对齐）：
 * 1. 扫描所有生效规则
 * 2. 逐条评估，更新状态
 * 3. 收集告警和违规
 * 4. 提交数据库更新
 */
class RuleEngine @Inject constructor(
    private val timeRuleRepository: TimeRuleRepository,
    private val evaluator: RuleEvaluator
) {

    /**
     * 运行规则引擎 - 评估所有生效规则
     *
     * @return 评估结果汇总
     */
    suspend fun run(): EngineRunResult = withContext(Dispatchers.IO) {
        val result = EngineRunResult()

        // 获取所有需要处理的规则（跳过 TEMPLATE 状态）
        val activeRules = timeRuleRepository.getAllNonTemplate()

        for (rule in activeRules) {
            val oldStatus = rule.status
            val evalResult = evaluator.evaluate(rule)
            result.processed++

            // 记录状态变更
            if (evalResult.newStatus != oldStatus) {
                val updatedRule = rule.copy(
                    triggerTime = evalResult.triggerTime,
                    flagTime = evalResult.flagTime,
                    targetTime = evalResult.targetTime,
                    warning = evalResult.warning,
                    result = evalResult.result,
                    status = evalResult.newStatus,
                    resultstamp = if (evalResult.newStatus == RuleStatus.HAS_RESULT) System.currentTimeMillis() else rule.resultstamp,
                    endstamp = if (evalResult.newStatus == RuleStatus.ENDED) System.currentTimeMillis() else rule.endstamp
                )
                timeRuleRepository.update(updatedRule)

                result.statusChanges.add(StatusChange(
                    ruleId = rule.id,
                    relatedType = rule.relatedType,
                    relatedId = rule.relatedId,
                    fromStatus = oldStatus,
                    toStatus = evalResult.newStatus
                ))
            } else {
                // 状态未变，但仍需更新计算结果（trigger_time, flag_time, target_time, warning）
                val updatedRule = rule.copy(
                    triggerTime = evalResult.triggerTime,
                    flagTime = evalResult.flagTime,
                    targetTime = evalResult.targetTime,
                    warning = evalResult.warning,
                    result = evalResult.result
                )
                timeRuleRepository.update(updatedRule)
            }

            // 收集告警（ORANGE + RED）
            if (evalResult.warning != null && evalResult.warning != WarningLevel.GREEN) {
                result.warnings.add(WarningInfo(
                    ruleId = rule.id,
                    relatedType = rule.relatedType,
                    relatedId = rule.relatedId,
                    targetEvent = rule.targetEvent,
                    flagTime = evalResult.flagTime,
                    warningLevel = evalResult.warning,
                    party = rule.party,
                    direction = rule.direction
                ))
            }

            // 收集所有告警（含 YELLOW）
            if (evalResult.warning != null && evalResult.warning != WarningLevel.GREEN) {
                result.allWarnings.add(WarningInfo(
                    ruleId = rule.id,
                    relatedType = rule.relatedType,
                    relatedId = rule.relatedId,
                    targetEvent = rule.targetEvent,
                    flagTime = evalResult.flagTime,
                    warningLevel = evalResult.warning,
                    party = rule.party,
                    direction = rule.direction
                ))
            }

            // 收集违规
            if (evalResult.isCompliant == false) {
                result.violations.add(ViolationInfo(
                    ruleId = rule.id,
                    relatedType = rule.relatedType,
                    relatedId = rule.relatedId,
                    targetEvent = rule.targetEvent,
                    targetTime = evalResult.targetTime,
                    flagTime = evalResult.flagTime,
                    party = rule.party,
                    direction = rule.direction
                ))
            }
        }

        result
    }

    /**
     * 评估指定实体的所有规则（含继承规则，Mobile 暂不支持继承规则）
     * 此方法保留接口对齐，Mobile 暂不实现继承规则收集
     */
    suspend fun evaluateEntity(relatedType: RelatedType, relatedId: Long): EngineRunResult {
        // Mobile 暂不支持继承规则收集，直接查询该实体的规则
        return withContext(Dispatchers.IO) {
            val result = EngineRunResult()
            val rules = timeRuleRepository.getAllNonTemplate().filter {
                it.relatedType == relatedType && it.relatedId == relatedId
            }

            for (rule in rules) {
                val oldStatus = rule.status
                val evalResult = evaluator.evaluate(rule)
                result.processed++

                if (evalResult.newStatus != oldStatus) {
                    val updatedRule = rule.copy(
                        triggerTime = evalResult.triggerTime,
                        flagTime = evalResult.flagTime,
                        targetTime = evalResult.targetTime,
                        warning = evalResult.warning,
                        result = evalResult.result,
                        status = evalResult.newStatus,
                        resultstamp = if (evalResult.newStatus == RuleStatus.HAS_RESULT) System.currentTimeMillis() else rule.resultstamp,
                        endstamp = if (evalResult.newStatus == RuleStatus.ENDED) System.currentTimeMillis() else rule.endstamp
                    )
                    timeRuleRepository.update(updatedRule)

                    result.statusChanges.add(StatusChange(
                        ruleId = rule.id,
                        relatedType = rule.relatedType,
                        relatedId = rule.relatedId,
                        fromStatus = oldStatus,
                        toStatus = evalResult.newStatus
                    ))
                }

                if (evalResult.warning != null && evalResult.warning != WarningLevel.GREEN) {
                    result.warnings.add(WarningInfo(
                        ruleId = rule.id,
                        relatedType = rule.relatedType,
                        relatedId = rule.relatedId,
                        targetEvent = rule.targetEvent,
                        flagTime = evalResult.flagTime,
                        warningLevel = evalResult.warning,
                        party = rule.party,
                        direction = rule.direction
                    ))
                }

                if (evalResult.isCompliant == false) {
                    result.violations.add(ViolationInfo(
                        ruleId = rule.id,
                        relatedType = rule.relatedType,
                        relatedId = rule.relatedId,
                        targetEvent = rule.targetEvent,
                        targetTime = evalResult.targetTime,
                        flagTime = evalResult.flagTime,
                        party = rule.party,
                        direction = rule.direction
                    ))
                }
            }
            result
        }
    }

    /**
     * 获取仪表盘汇总数据
     */
    suspend fun getDashboardSummary(): DashboardSummary {
        val result = run()
        return DashboardSummary(
            totalActive = result.processed,
            criticalCount = result.allWarnings.count { it.warningLevel == WarningLevel.RED },
            urgentCount = result.allWarnings.count { it.warningLevel == WarningLevel.ORANGE },
            attentionCount = result.allWarnings.count { it.warningLevel == WarningLevel.YELLOW },
            violationCount = result.violations.size,
            warningsByType = result.allWarnings.groupBy { it.relatedType.displayName },
            recentViolations = result.violations.take(10)
        )
    }
}

// =========================================================================
// 结果数据类
// =========================================================================

data class EngineRunResult(
    var processed: Int = 0,
    val warnings: MutableList<WarningInfo> = mutableListOf(),
    val violations: MutableList<ViolationInfo> = mutableListOf(),
    val statusChanges: MutableList<StatusChange> = mutableListOf(),
    val allWarnings: MutableList<WarningInfo> = mutableListOf()
)

data class WarningInfo(
    val ruleId: Long,
    val relatedType: RelatedType,
    val relatedId: Long,
    val targetEvent: RuleEvent,
    val flagTime: Long?,
    val warningLevel: WarningLevel,
    val party: Party?,
    val direction: Direction?
)

data class ViolationInfo(
    val ruleId: Long,
    val relatedType: RelatedType,
    val relatedId: Long,
    val targetEvent: RuleEvent,
    val targetTime: Long?,
    val flagTime: Long?,
    val party: Party?,
    val direction: Direction?
)

data class StatusChange(
    val ruleId: Long,
    val relatedType: RelatedType,
    val relatedId: Long,
    val fromStatus: RuleStatus,
    val toStatus: RuleStatus
)

data class DashboardSummary(
    val totalActive: Int,
    val criticalCount: Int,
    val urgentCount: Int,
    val attentionCount: Int,
    val violationCount: Int,
    val warningsByType: Map<String, List<WarningInfo>>,
    val recentViolations: List<ViolationInfo>
)
