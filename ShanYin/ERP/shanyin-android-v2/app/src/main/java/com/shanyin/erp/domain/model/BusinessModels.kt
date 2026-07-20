package com.shanyin.erp.domain.model

import com.google.gson.Gson

/**
 * 业务状态枚举
 * 前期接洽 -> 业务评估 -> 客户反馈 -> 合作落地 -> 业务开展 -> 业务暂缓/完成/终止
 */
enum class BusinessStatus(val displayName: String, val order: Int) {
    INITIAL_CONTACT("前期接洽", 0),
    EVALUATION("业务评估", 1),
    CUSTOMER_FEEDBACK("客户反馈", 2),
    COOPERATION_START("合作落地", 3),
    BUSINESS_PROGRESS("业务开展", 4),
    SUSPENDED("业务暂缓", 5),
    COMPLETED("业务完成", 6),
    TERMINATED("业务终止", 7);

    companion object {
        fun getNext(current: BusinessStatus): BusinessStatus? {
            return when (current) {
                INITIAL_CONTACT -> EVALUATION
                EVALUATION -> CUSTOMER_FEEDBACK
                CUSTOMER_FEEDBACK -> COOPERATION_START
                COOPERATION_START -> BUSINESS_PROGRESS
                BUSINESS_PROGRESS -> COMPLETED
                else -> null
            }
        }

        fun canSuspend(current: BusinessStatus): Boolean {
            return current in listOf(EVALUATION, CUSTOMER_FEEDBACK, COOPERATION_START, BUSINESS_PROGRESS)
        }

        fun canTerminate(current: BusinessStatus): Boolean {
            return current !in listOf(COMPLETED, TERMINATED)
        }

        fun canReactivate(current: BusinessStatus): Boolean {
            return current == SUSPENDED
        }

        /** 根据 name 或 displayName（中文）解析枚举 */
        fun fromString(value: String?): BusinessStatus? {
            if (value == null) return null
            return entries.find { it.name == value }
                ?: entries.find { it.displayName == value }
        }
    }
}

/**
 * 业务实体
 */
data class Business(
    val id: Long = 0,
    val customerId: Long? = null,
    val contractId: Long? = null,
    val status: BusinessStatus? = BusinessStatus.INITIAL_CONTACT,
    val timestamp: Long = System.currentTimeMillis(),
    val details: BusinessDetails = BusinessDetails()
)

/**
 * 业务详情 - 记录业务演进历史
 */
data class BusinessDetails(
    val history: List<StageTransition> = emptyList(),
    val notes: String? = null,
    val summary: String? = null,
    val paymentTerms: BusinessPaymentTerms? = null,
    val pricing: Map<String, SkuPriceItem> = emptyMap()
) {
    companion object {
        private val gson = Gson()

        /** 从 JSON 字符串解析，内部不做 status 映射，由 BusinessRepositoryImpl.toDomain() 统一处理 */
        fun fromJson(json: String?): BusinessDetails {
            return json?.let {
                try {
                    gson.fromJson(it, BusinessDetails::class.java)
                } catch (e: Exception) {
                    BusinessDetails()
                }
            } ?: BusinessDetails()
        }
    }
}

/** 商务付款条款 */
data class BusinessPaymentTerms(
    val prepaymentRatio: Double = 0.0,
    val balancePeriod: Int = 0,
    val dayRule: String? = null,
    val startTrigger: String? = null
)

/** SKU价格条目 */
data class SkuPriceItem(
    val price: Double = 0.0,
    val deposit: Double = 0.0
)

/**
 * 阶段转换记录
 */
data class StageTransition(
    val from: BusinessStatus?,
    val to: BusinessStatus?,
    val time: Long = System.currentTimeMillis(),
    val comment: String? = null
)

/**
 * 合同实体
 */
data class Contract(
    val id: Long = 0,
    val contractNumber: String,
    val type: ContractType? = null,
    val status: ContractStatus? = null,
    val parties: List<ContractParty> = emptyList(),
    val content: ContractContent? = null,
    val signedDate: Long? = null,
    val effectiveDate: Long? = null,
    val expiryDate: Long? = null,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * 合同类型
 */
enum class ContractType(val displayName: String) {
    COOPERATION("合作合同"),
    EQUIPMENT_PURCHASE("设备采购合同"),
    MATERIAL_PURCHASE("物料采购合同"),
    EXTERNAL_COOPERATION("外部合作合同")
}

/**
 * 合同状态
 */
enum class ContractStatus(val displayName: String) {
    SIGNED("签约完成"),
    EFFECTIVE("生效"),
    EXPIRED("过期"),
    TERMINATED("终止")
}

/**
 * 签约方
 */
data class ContractParty(
    val type: PartyType,
    val entityId: Long,
    val name: String
)

enum class PartyType {
    CUSTOMER, SUPPLIER, PARTNER, OURSELVES
}

/**
 * 合同内容
 */
data class ContractContent(
    val title: String? = null,
    val terms: String? = null,
    val paymentTerms: String? = null,
    val deliveryTerms: String? = null,
    val otherTerms: String? = null
)
