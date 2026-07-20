package com.shanyin.erp.domain.usecase.rule_engine

import com.shanyin.erp.domain.model.*
import javax.inject.Inject
import kotlin.math.abs

/**
 * 规则评估器
 *
 * 核心计算引擎，负责：
 * - 根据触发事件 + 偏移量计算 flag_time
 * - 检查目标事件是否发生
 * - 判断是否合规
 * - 计算告警等级
 * - 更新规则状态
 *
 * 与 Desktop evaluator.py 的 RuleEvaluator.evaluate_rule 完全对齐。
 */
class RuleEvaluator @Inject constructor(
    private val eventHandler: EventHandler
) {

    /**
     * 评估单条规则
     *
     * @param rule 待评估的时间规则
     * @param currentTime 当前时间（默认 System.currentTimeMillis()）
     * @return 评估结果
     */
    suspend fun evaluate(
        rule: TimeRule,
        currentTime: Long = System.currentTimeMillis()
    ): EvaluationResult {
        var triggerTime: Long? = rule.triggerTime
        var flagTime: Long? = rule.flagTime
        var targetTime: Long? = rule.targetTime
        var warning: WarningLevel? = rule.warning
        var result: RuleResult? = rule.result

        // Step 1: 处理触发事件，计算 flag_time
        if (rule.triggerEvent == RuleEvent.ABSOLUTE_DATE) {
            // 绝对日期模式：flag_time 已在创建时赋值，无需计算
            triggerTime = null
        } else if (rule.triggerEvent != null && rule.flagTime == null) {
            // 标准模式：查询触发事件时间，计算 flag_time
            val foundTriggerTime = eventHandler.getEventTime(
                rule.triggerEvent,
                rule.relatedType,
                rule.relatedId,
                rule.tgeParam1,
                rule.tgeParam2
            )
            if (foundTriggerTime != null) {
                triggerTime = foundTriggerTime
                flagTime = calculateFlagTime(foundTriggerTime, rule.offset ?: 0, rule.unit)
            }
        }

        // Step 2: 检查目标事件
        val foundTargetTime = eventHandler.getEventTime(
            rule.targetEvent,
            rule.relatedType,
            rule.relatedId,
            rule.taeParam1,
            rule.taeParam2
        )
        if (foundTargetTime != null) {
            targetTime = foundTargetTime
        }

        // Step 3: 评估合规性（仅当 flag_time 和 target_time 都存在时）
        var isCompliant: Boolean? = null
        if (flagTime != null && targetTime != null) {
            isCompliant = checkCompliance(targetTime, flagTime, rule.direction)
            result = if (isCompliant) RuleResult.COMPLIANT else RuleResult.VIOLATION
        }

        // Step 4: 确定新状态
        val newStatus = determineStatus(rule, triggerTime, targetTime, flagTime)

        // Step 5: 计算告警等级（仅当目标事件未发生时）
        if (targetTime == null && flagTime != null) {
            warning = calculateWarningLevel(flagTime, rule.direction, currentTime)
        } else if (targetTime != null) {
            // 目标事件已发生，无需告警
            warning = WarningLevel.GREEN
        }

        return EvaluationResult(
            triggerTime = triggerTime,
            flagTime = flagTime,
            targetTime = targetTime,
            isCompliant = isCompliant,
            warning = warning,
            newStatus = newStatus,
            result = result
        )
    }

    /**
     * 基于触发时间 + 偏移量计算标杆时间
     */
    private fun calculateFlagTime(triggerTime: Long, offset: Int, unit: TimeUnit?): Long {
        return when (unit) {
            TimeUnit.WORKING_DAY -> addWorkDays(triggerTime, offset)
            TimeUnit.HOUR -> triggerTime + offset * 3600 * 1000L
            else -> triggerTime + offset * 24 * 3600 * 1000L  // 默认自然日
        }
    }

    /**
     * 添加工作日（排除周末）
     *
     * TODO: 扩展支持节假日排除
     */
    private fun addWorkDays(startDate: Long, days: Int): Long {
        if (days == 0) return startDate

        var current = startDate
        var added = 0
        val direction = if (days >= 0) 1 else -1
        val targetDays = abs(days)

        while (added < targetDays) {
            current += direction * 24 * 3600 * 1000L
            // 周一到周五为工作日 (weekday: 0=周一, 4=周五)
            val weekday = java.util.Calendar.getInstance().apply { timeInMillis = current }.get(java.util.Calendar.DAY_OF_WEEK)
            if (weekday in 2..6) {  // Mon-Fri
                added++
            }
        }
        return current
    }

    /**
     * 检查目标事件是否合规
     *
     * direction=BEFORE：目标事件需在 flag_time 之前（或当天）完成
     * direction=AFTER：目标事件需在 flag_time 之后（或当天）发生
     */
    private fun checkCompliance(targetTime: Long, flagTime: Long, direction: Direction?): Boolean {
        return when (direction) {
            Direction.BEFORE -> targetTime <= flagTime
            Direction.AFTER -> targetTime >= flagTime
            else -> true
        }
    }

    /**
     * 计算告警等级
     *
     * 仅当 direction=BEFORE 时产生紧迫性告警
     *
     * 阈值（与 Desktop WarningLevel.THRESHOLDS 对齐）：
     * - ≤0 天：RED（已逾期）
     * - 1~3 天：ORANGE
     * - 4~7 天：YELLOW
     * - >7 天：GREEN
     */
    private fun calculateWarningLevel(
        flagTime: Long,
        direction: Direction?,
        currentTime: Long
    ): WarningLevel {
        if (direction != Direction.BEFORE) {
            return WarningLevel.GREEN
        }

        val deltaDays = ((flagTime - currentTime) / (24 * 3600 * 1000L)).toInt()

        return when {
            deltaDays < 0 -> WarningLevel.RED
            deltaDays <= 3 -> WarningLevel.ORANGE
            deltaDays <= 7 -> WarningLevel.YELLOW
            else -> WarningLevel.GREEN
        }
    }

    /**
     * 确定规则状态
     *
     * 状态流转逻辑（与 Desktop _determine_status 完全对齐）：
     * - 绝对日期模式：目标发生即结束
     * - 标准模式：
     *   - 目标 + 触发都发生 → 结束
     *   - 目标发生，触发未发生 → 有结果
     *   - 其他 → 生效
     */
    private fun determineStatus(
        rule: TimeRule,
        triggerTime: Long?,
        targetTime: Long?,
        flagTime: Long?
    ): RuleStatus {
        // 如果已手动失效，保持失效状态
        if (rule.status == RuleStatus.INACTIVE) {
            return RuleStatus.INACTIVE
        }

        val targetOccurred = targetTime != null

        // 绝对日期模式：无触发事件，目标发生即结束
        if (rule.triggerEvent == RuleEvent.ABSOLUTE_DATE) {
            return if (targetOccurred) RuleStatus.ENDED else RuleStatus.ACTIVE
        }

        // 标准模式
        val triggerOccurred = triggerTime != null || rule.triggerEvent == null

        return when {
            targetOccurred && triggerOccurred -> RuleStatus.ENDED
            targetOccurred && !triggerOccurred -> RuleStatus.HAS_RESULT
            else -> RuleStatus.ACTIVE
        }
    }
}

/**
 * 规则评估结果
 */
data class EvaluationResult(
    val triggerTime: Long?,      // 触发事件实际发生时间
    val flagTime: Long?,          // 计算出的旗标时间
    val targetTime: Long?,        // 目标事件实际发生时间
    val isCompliant: Boolean?,    // 是否合规
    val warning: WarningLevel?,   // 预警等级
    val newStatus: RuleStatus,    // 评估后状态
    val result: RuleResult?       // 判定结果
)
