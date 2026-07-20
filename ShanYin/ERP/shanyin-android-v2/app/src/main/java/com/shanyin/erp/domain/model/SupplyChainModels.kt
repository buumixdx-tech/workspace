package com.shanyin.erp.domain.model

import com.google.gson.Gson

/**
 * 供应链类型
 */
enum class SupplyChainType(val displayName: String) {
    MATERIAL("物料"),
    EQUIPMENT("设备")
}

/**
 * 供应链
 */
data class SupplyChain(
    val id: Long = 0,
    val supplierId: Long,
    val supplierName: String,
    val type: SupplyChainType,
    val contractId: Long? = null,
    val pricingConfig: PricingConfig? = null,
    val paymentTerms: PaymentTerms? = null
)

/**
 * 定价配置
 */
data class PricingConfig(
    val isFloating: Boolean = false,       // 是否浮动价格
    val floatingBase: Double? = null,     // 浮动基准价
    val currency: String = "CNY",         // 币种
    val unit: String = "元/件"            // 单位
) {
    fun toJson(): String = Gson().toJson(this)

    companion object {
        fun fromJson(json: String?): PricingConfig {
            return json?.let {
                try {
                    Gson().fromJson(it, PricingConfig::class.java)
                } catch (e: Exception) {
                    PricingConfig()
                }
            } ?: PricingConfig()
        }
    }
}

/**
 * 付款条款
 */
data class PaymentTerms(
    val prepaymentPercent: Double = 0.0,  // 预付款百分比
    val paymentDays: Int = 30,             // 账期天数
    val paymentMethod: String? = null,      // 付款方式
    val notes: String? = null
) {
    fun toJson(): String = Gson().toJson(this)

    companion object {
        fun fromJson(json: String?): PaymentTerms {
            return json?.let {
                try {
                    Gson().fromJson(it, PaymentTerms::class.java)
                } catch (e: Exception) {
                    PaymentTerms()
                }
            } ?: PaymentTerms()
        }
    }
}

/**
 * 供应链明细 - 存储每个SKU的协议价格
 */
data class SupplyChainItem(
    val id: Long = 0,
    val supplyChainId: Long,
    val skuId: Long,
    val skuName: String,                   // 冗余存储便于显示
    val price: Double,                     // 协议单价
    val deposit: Double = 0.0,             // 设备押金
    val isFloating: Boolean = false        // 是否为浮动价格
)

/**
 * 供应链状态
 */
enum class SupplyChainStatus(val displayName: String) {
    ACTIVE("生效中"),
    EXPIRED("已过期"),
    TERMINATED("已终止")
}
