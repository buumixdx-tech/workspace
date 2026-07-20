package com.shanyin.erp.domain.model

// ==================== Time Rule Enums ====================

enum class RelatedType(val displayName: String) {
    BUSINESS("业务"),
    SUPPLY_CHAIN("供应链"),
    VIRTUAL_CONTRACT("虚拟合同"),
    LOGISTICS("物流");

    companion object {
        fun fromDbName(name: String?): RelatedType? {
            if (name == null) return null
            entries.find { it.displayName == name }?.let { return it }
            return entries.find { it.name.equals(name, ignoreCase = true) }
        }
    }
}

enum class InheritLevel(val displayName: String) {
    SELF("自身定制"),
    NEAR("近继承"),
    FAR("远继承");

    companion object {
        fun fromDbName(name: String?): InheritLevel? {
            if (name == null) return null
            // Desktop uses ordinal (0, 1, 2) stored as int
            name.toIntOrNull()?.let { ordinal ->
                entries.getOrNull(ordinal)?.let { return it }
            }
            entries.find { it.displayName == name }?.let { return it }
            return entries.find { it.name.equals(name, ignoreCase = true) }
        }

        fun fromOrdinal(ordinal: Int): InheritLevel? {
            return entries.getOrNull(ordinal)
        }
    }
}

enum class Party(val displayName: String) {
    SELF("我方"),
    CUSTOMER("客户"),
    SUPPLIER("供应商")
}

enum class TimeUnit(val displayName: String) {
    CALENDAR_DAY("自然日"),
    WORKING_DAY("工作日"),
    HOUR("小时")
}

enum class Direction(val displayName: String, val uiName: String) {
    BEFORE("BEFORE", "之前"),
    AFTER("AFTER", "之后");

    companion object {
        fun fromDbName(name: String?): Direction? {
            if (name == null) return null
            entries.find { it.displayName.equals(name, ignoreCase = true) }?.let { return it }
            return entries.find { it.name.equals(name, ignoreCase = true) }
        }
    }
}

enum class WarningLevel(val displayName: String) {
    GREEN("绿色"),
    YELLOW("黄色"),
    ORANGE("橙色"),
    RED("红色");

    companion object {
        fun fromDbName(name: String?): WarningLevel? {
            if (name == null) return null
            entries.find { it.displayName == name }?.let { return it }
            return entries.find { it.name.equals(name, ignoreCase = true) }
        }
    }
}

enum class RuleResult(val displayName: String) {
    COMPLIANT("合规"),
    VIOLATION("违规");

    companion object {
        fun fromDbName(name: String?): RuleResult? {
            if (name == null) return null
            entries.find { it.displayName == name }?.let { return it }
            return entries.find { it.name.equals(name, ignoreCase = true) }
        }
    }
}

enum class RuleStatus(val displayName: String) {
    INACTIVE("失效"),
    TEMPLATE("模板"),
    ACTIVE("生效"),
    HAS_RESULT("有结果"),
    ENDED("结束");

    companion object {
        fun fromDbName(name: String?): RuleStatus? {
            if (name == null) return null
            // 先尝试直接匹配枚举名
            entries.find { it.name == name }?.let { return it }
            // 再尝试 displayName 匹配（Desktop 兼容性）
            return entries.find { it.displayName == name }
        }
    }
}

// ==================== Rule Events ====================
//
// Desktop 三层事件体系完整对齐，trigger 和 target 共用同一套事件：
//   - ContractLevel：业务 / 供应链层（仅触发）
//   - VCLevel：虚拟合同层（触发 & 目标）
//   - LogisticsLevel：物流层（触发 & 目标，但 LOGISTICS_CREATED/PENDING 仅触发）
//   - Special：ABSOLUTE_DATE
//
// 注意：VC.SUBJECT_SHIPPED 和 Logistics.LOGISTICS_SHIPPED 在 Desktop 中
// 同名为"合同物流发货"，Mobile 用 displayName 区分，VC 加"合同"前缀，
// Logistics 加"物流"前缀，避免同一 displayName 导致查表歧义。

enum class RuleEvent(val displayName: String) {
    // --- ContractLevel（仅触发） ---
    CONTRACT_SIGNED("合同签订"),
    CONTRACT_EFFECTIVE("合同生效"),
    CONTRACT_EXPIRY("合同到期"),
    CONTRACT_RENEWED("合同更新"),
    CONTRACT_TERMINATED("合同终止"),

    // --- VCLevel（虚拟合同层） ---
    VC_CREATED("虚拟合同创建"),
    VC_STATUS_EXE("虚拟合同执行"),
    VC_STATUS_FINISH("虚拟合同完成"),
    SUBJECT_SHIPPED("合同物流发货"),      // Desktop: "合同物流发货"
    SUBJECT_SIGNED("合同物流签收"),       // Desktop: "合同物流签收"
    SUBJECT_FINISH("合同标的完成"),       // Desktop: "合同标的完成"
    CASH_PREPAID("合同预付完成"),         // Desktop: "合同预付完成"
    CASH_FINISH("合同款项结清"),          // Desktop: "合同款项结清"
    SUBJECT_CASH_FINISH("合同货款结清"),  // Desktop: "合同货款结清"
    DEPOSIT_RECEIVED("合同押金收齐"),     // Desktop: "合同押金收齐"
    DEPOSIT_RETURNED("合同押金退还"),     // Desktop: "合同押金退还"
    PAYMENT_RATIO_REACHED("付款比例达到"),// Desktop: "付款比例达到"

    // --- LogisticsLevel ---
    LOGISTICS_CREATED("物流创建"),        // Desktop: "物流创建"
    LOGISTICS_PENDING("物流待发货"),      // Desktop: "物流待发货"
    LOGISTICS_SHIPPED("物流发货"),        // Desktop: "合同物流发货"（Mobile 区分命名）
    LOGISTICS_SIGNED("物流签收"),         // Desktop: "合同物流签收"（Mobile 区分命名）
    LOGISTICS_FINISH("物流完成"),         // Desktop: "物流完成"
    EXPRESS_CREATED("快递单创建"),        // Desktop: "快递单创建"
    EXPRESS_SHIPPED("快递发出"),          // Desktop: "快递发出"
    EXPRESS_SIGNED("快递签收"),           // Desktop: "快递签收"

    // --- Special ---
    ABSOLUTE_DATE("绝对日期")
}

// ==================== Time Rule ====================

data class TimeRule(
    val id: Long = 0,
    // 关联信息
    val relatedId: Long,
    val relatedType: RelatedType,
    val inherit: InheritLevel = InheritLevel.SELF,
    // 责任方
    val party: Party? = null,
    // 触发事件
    val triggerEvent: RuleEvent? = null,
    val tgeParam1: String? = null,
    val tgeParam2: String? = null,
    val triggerTime: Long? = null,
    // 目标事件
    val targetEvent: RuleEvent,
    val taeParam1: String? = null,
    val taeParam2: String? = null,
    val targetTime: Long? = null,
    // 时间约束
    val offset: Int? = null,  // 时间偏移量
    val unit: TimeUnit? = null,
    val flagTime: Long? = null,  // 标杆时间
    val direction: Direction? = null,
    // 监控与结果
    val warning: WarningLevel? = null,
    val result: RuleResult? = null,
    val status: RuleStatus = RuleStatus.ACTIVE,
    // 时间戳
    val timestamp: Long = System.currentTimeMillis(),
    val resultstamp: Long? = null,
    val endstamp: Long? = null
) {
    /**
     * 计算预警状态
     * 基于标杆时间和当前时间计算预警级别
     */
    fun calculateWarning(currentTime: Long = System.currentTimeMillis()): WarningLevel? {
        val flag = flagTime ?: return null
        val target = targetTime ?: return null

        val remaining = target - currentTime
        val total = target - flag

        if (remaining <= 0) return WarningLevel.RED

        val ratio = remaining.toDouble() / total.toDouble()
        return when {
            ratio <= 0.25 -> WarningLevel.RED
            ratio <= 0.5 -> WarningLevel.ORANGE
            ratio <= 0.75 -> WarningLevel.YELLOW
            else -> WarningLevel.GREEN
        }
    }

    /**
     * 获取关联对象的显示名称
     */
    fun getRelatedDisplayName(): String {
        return "${relatedType.displayName} #${relatedId}"
    }

    /**
     * 判断规则是否已到期
     */
    fun isOverdue(currentTime: Long = System.currentTimeMillis()): Boolean {
        return targetTime != null && currentTime > targetTime
    }
}

// ==================== System Event ====================

enum class SystemEventType(val displayName: String) {
    VC_CREATED("虚拟合同创建"),
    VC_STATUS_CHANGED("虚拟合同状态变更"),
    LOGISTICS_CREATED("物流创建"),
    LOGISTICS_STATUS_CHANGED("物流状态变更"),
    PAYMENT_TRIGGERED("付款触发"),
    WARNING_TRIGGERED("预警触发"),
    RULE_EXECUTED("规则执行"),
    MANUAL_ACTION("手动操作")
}

data class SystemEvent(
    val id: Long = 0,
    val eventType: SystemEventType,
    val relatedId: Long? = null,
    val relatedType: String? = null,
    val description: String? = null,
    val timestamp: Long = System.currentTimeMillis(),
    val metadata: String? = null  // JSON for additional data
)
