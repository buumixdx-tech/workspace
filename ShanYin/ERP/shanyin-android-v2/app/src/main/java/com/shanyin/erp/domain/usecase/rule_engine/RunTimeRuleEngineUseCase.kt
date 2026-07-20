package com.shanyin.erp.domain.usecase.rule_engine

import com.shanyin.erp.domain.model.RelatedType
import javax.inject.Inject

/**
 * 运行时间规则引擎的 Use Case
 *
 * 便捷入口，对应 Desktop 的 run_time_rule_engine() 便捷函数。
 * 实际逻辑委托给 RuleEngine。
 */
class RunTimeRuleEngineUseCase @Inject constructor(
    private val engine: RuleEngine
) {
    /**
     * 运行所有规则
     */
    suspend operator fun invoke(): EngineRunResult = engine.run()

    /**
     * 评估指定实体的规则
     */
    suspend fun evaluateEntity(relatedType: RelatedType, relatedId: Long): EngineRunResult =
        engine.evaluateEntity(relatedType, relatedId)

    /**
     * 获取仪表盘汇总
     */
    suspend fun getDashboardSummary(): DashboardSummary = engine.getDashboardSummary()
}
