package com.shanyin.erp.domain.model

import com.google.gson.Gson

/**
 * 虚拟合同类型
 */
enum class VCType(val displayName: String, val description: String) {
    EQUIPMENT_PROCUREMENT("设备采购(客户)", "向供应商采购设备后销售给客户"),
    EQUIPMENT_STOCK("设备采购(库存)", "向供应商采购设备存入自有仓库"),
    MATERIAL_PROCUREMENT("物料采购", "向供应商采购物料"),
    MATERIAL_SUPPLY("物料供应", "向客户供应物料"),
    INVENTORY_ALLOCATION("库存拨付", "仓库间库存调拨"),
    RETURN("退货", "退货处理");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "STOCK_PROCUREMENT" to EQUIPMENT_STOCK
        )

        fun fromDbName(name: String?): VCType? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        EQUIPMENT_STOCK -> "STOCK_PROCUREMENT"
        else -> this.name
    }
}

/**
 * VC 主状态
 */
enum class VCStatus(val displayName: String) {
    EXECUTING("执行"),
    COMPLETED("完成"),
    TERMINATED("终止"),
    CANCELLED("取消");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "EXE" to EXECUTING,
            "FINISH" to COMPLETED
        )

        fun fromDbName(name: String?): VCStatus? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        EXECUTING -> "EXE"
        COMPLETED -> "FINISH"
        else -> this.name
    }
}

/**
 * 标的物状态
 */
enum class SubjectStatus(val displayName: String) {
    EXECUTING("执行"),
    SHIPPED("发货"),
    SIGNED("签收"),
    COMPLETED("完成");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "EXE" to EXECUTING,
            "FINISH" to COMPLETED
        )

        fun fromDbName(name: String?): SubjectStatus? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        EXECUTING -> "EXE"
        COMPLETED -> "FINISH"
        else -> this.name
    }
}

/**
 * 资金状态
 */
enum class CashStatus(val displayName: String) {
    EXECUTING("执行"),
    PREPAID("预付"),
    COMPLETED("完成");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "EXE" to EXECUTING,
            "FINISH" to COMPLETED
        )

        fun fromDbName(name: String?): CashStatus? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        EXECUTING -> "EXE"
        COMPLETED -> "FINISH"
        else -> this.name
    }
}

/**
 * 退货方向
 */
enum class ReturnDirection(val displayName: String) {
    CUSTOMER_TO_US("客户退货给我们"),
    US_TO_SUPPLIER("我们退货给供应商")
}

/**
 * 退货物流费承担方
 */
enum class LogisticsBearer(val displayName: String) {
    SENDER("发方承担"),
    RECEIVER("收方承担")
}

/**
 * 虚拟合同标的物元素基类
 *
 * 新版统一字段结构（与Desktop desktop-version/logic/vc/schemas.py 对齐）：
 * - id: 唯一标识，格式 "sp{shippingPointId}_rp{receivingPointId}_sku{skuId}"
 * - shippingPointId/receivingPointId: 发货/收货点位ID
 * - subtotal: 小计金额 = qty × unitPrice
 * - snList: 设备序列号列表（退货/调拨时填写）
 */
sealed class VCElementBase {
    abstract val id: String                    // 唯一标识，格式 "sp{sp}_rp{rp}_sku{sku}"
    abstract val shippingPointId: Long?       // 发货点位ID
    abstract val receivingPointId: Long?       // 收货点位ID
    abstract val skuId: Long                  // SKU ID
    abstract val skuName: String              // SKU名称
    abstract val quantity: Int                 // 数量
    abstract val unitPrice: Double             // 单价
    abstract val deposit: Double              // 单台押金
    abstract val subtotal: Double           // 小计金额 = qty × unitPrice
    abstract val snList: List<String>        // 设备序列号列表
}

/**
 * SkusFormatElement：用于设备采购(客户)、库存采购、物料采购
 *
 * 新版统一格式（与Desktop VCElementSchema对齐）
 */
data class SkusFormatElement(
    override val id: String = "",                    // 生成: "sp{shippingPointId}_rp{receivingPointId}_sku{skuId}"
    override val shippingPointId: Long? = null,     // 发货点位ID（供应商仓库）
    override val receivingPointId: Long? = null,     // 收货点位ID（客户部署点）
    override val skuId: Long,
    override val skuName: String = "",
    override val quantity: Int,
    override val unitPrice: Double,
    override val deposit: Double = 0.0,            // 单台押金
    override val subtotal: Double = quantity * unitPrice, // 小计金额
    override val snList: List<String> = emptyList() // 设备序列号列表
) : VCElementBase()

/**
 * MaterialSupplyElement：用于物料供应
 *
 * 新版统一格式（与Desktop VCElementSchema对齐）
 */
data class MaterialSupplyElement(
    override val id: String = "",
    override val shippingPointId: Long? = null,     // 供应商仓库点位ID
    override val receivingPointId: Long? = null,     // 客户收货点位ID
    override val skuId: Long,
    override val skuName: String = "",
    override val quantity: Int,
    override val unitPrice: Double,
    override val deposit: Double = 0.0,
    override val subtotal: Double = quantity * unitPrice,
    override val snList: List<String> = emptyList(),
    val sourceWarehouse: String? = null             // 发货仓库（供应商仓库）
) : VCElementBase()

/**
 * ReturnElement：用于退货
 *
 * 新版统一格式（与Desktop VCElementSchema对齐）
 * 退货特有字段：goodsAmount, depositAmount, totalRefund, reason
 */
data class ReturnElement(
    override val id: String = "",
    override val shippingPointId: Long? = null,     // 原部署点位ID
    override val receivingPointId: Long? = null,     // 收货仓库点位ID
    override val skuId: Long,
    override val skuName: String = "",
    override val quantity: Int,
    override val unitPrice: Double = 0.0,           // 退货无单价
    override val deposit: Double = 0.0,             // 单台押金
    override val subtotal: Double = 0.0,           // 退货无货款小计
    override val snList: List<String> = emptyList(), // 设备序列号列表
    val receivingWarehouse: String? = null,        // 收货仓库
    val goodsAmount: Double? = null,               // 货物金额 (Desktop: goods_amount)
    val depositAmount: Double? = null,             // 押金金额 (Desktop: deposit_amount)
    val totalRefund: Double? = null,               // 退款总额 (Desktop: total_refund)
    val reason: String? = null                      // 退货原因 (Desktop: reason)
) : VCElementBase()

/**
 * AllocationElement：用于库存拨付
 *
 * 新版统一格式（与Desktop VCElementSchema对齐）
 */
data class AllocationElement(
    override val id: String = "",
    override val shippingPointId: Long? = null,     // 源仓库点位ID
    override val receivingPointId: Long? = null,    // 目标点位ID
    override val skuId: Long,
    override val skuName: String = "",
    override val quantity: Int = 1,
    override val unitPrice: Double = 0.0,           // 库存拨付无货款
    override val deposit: Double = 0.0,
    override val subtotal: Double = 0.0,           // 库存拨付无货款小计
    override val snList: List<String> = emptyList(), // 设备序列号列表
    val equipmentId: Long? = null,                 // 设备ID
    val equipmentSn: String? = null,               // 设备序列号
    val targetPointId: Long? = null              // 目标点位ID（同receivingPointId）
) : VCElementBase()

// 类型别名
typealias VCElement = VCElementBase

/**
 * 押金信息
 */
data class DepositInfo(
    val expectedDeposit: Double = 0.0,      // 应收押金金额
    val actualDeposit: Double = 0.0,        // 实收押金
    val totalAmount: Double = 0.0,          // 货款总额
    val shouldReceive: Double = 0.0,        // 动态重算应收押金
    val actualAmount: Double = 0.0,         // 实收货款
    val lastCashFlowId: Long? = null,        // 最后流水ID
    val adjustmentReason: String? = null,    // 调整原因
    val prepaymentRatio: Double = 0.0        // 预付款比例阈值（0.0~1.0）
) {
    fun toJson(): String = Gson().toJson(this)

    companion object {
        fun fromJson(json: String?): DepositInfo {
            return json?.let {
                try {
                    Gson().fromJson(it, DepositInfo::class.java)
                } catch (e: Exception) {
                    DepositInfo()
                }
            } ?: DepositInfo()
        }
    }
}

/**
 * 虚拟合同
 */
data class VirtualContract(
    val id: Long = 0,
    val description: String? = null,
    val businessId: Long? = null,
    val supplyChainId: Long? = null,
    val relatedVcId: Long? = null,           // 关联的VC ID (用于退货等)
    val type: VCType,
    val summary: String? = null,
    val elements: List<VCElement> = emptyList(),  // 标的物列表
    val depositInfo: DepositInfo = DepositInfo(), // 押金信息
    val status: VCStatus = VCStatus.EXECUTING,
    val subjectStatus: SubjectStatus = SubjectStatus.EXECUTING,
    val cashStatus: CashStatus = CashStatus.EXECUTING,
    val statusTimestamp: Long? = null,
    val subjectStatusTimestamp: Long? = null,
    val cashStatusTimestamp: Long? = null,
    val returnDirection: ReturnDirection? = null, // 退货方向（仅 RETURN VC 使用）
    val goodsAmount: Double = 0.0,               // 退货货物金额（仅 RETURN VC 使用）
    val logisticsCost: Double = 0.0,             // 退货物流费（仅 RETURN VC 使用）
    val logisticsBearer: LogisticsBearer? = null  // 退货物流费承担方（仅 RETURN VC 使用）
)

/**
 * 虚拟合同状态变更日志
 */
data class VCStatusLog(
    val id: Long = 0,
    val vcId: Long,
    val category: StatusLogCategory,
    val statusName: String,
    val timestamp: Long = System.currentTimeMillis()
)

enum class StatusLogCategory(val displayName: String) {
    STATUS("VC状态"),
    SUBJECT("标的物状态"),
    CASH("资金状态");

    companion object {
        fun fromDbName(name: String?): StatusLogCategory? {
            if (name == null) return null
            // Desktop uses lowercase: "status", "subject", "cash"
            entries.find { it.name.lowercase() == name.lowercase() }?.let { return it }
            return entries.find { it.name.equals(name, ignoreCase = true) }
        }
    }

    fun toDbName(): String = this.name.lowercase()
}

/**
 * 虚拟合同历史版本
 */
data class VCHistory(
    val id: Long = 0,
    val vcId: Long,
    val originalData: String,
    val changeDate: Long = System.currentTimeMillis(),
    val changeReason: String? = null
)
