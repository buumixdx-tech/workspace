package com.shanyin.erp.domain.model

// ==================== Equipment Inventory ====================

enum class OperationalStatus(val displayName: String) {
    IN_STOCK("库存"),
    IN_OPERATION("运营"),
    DISPOSAL("处置");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "STOCK" to IN_STOCK,
            "OPERATING" to IN_OPERATION,
            "DISPOSED" to DISPOSAL
        )

        fun fromDbName(name: String?): OperationalStatus? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        IN_STOCK -> "STOCK"
        IN_OPERATION -> "OPERATING"
        DISPOSAL -> "DISPOSED"
        else -> this.name
    }
}

enum class DeviceStatus(val displayName: String) {
    NORMAL("正常"),
    MAINTENANCE("维修"),
    DAMAGED("损坏"),
    FAULT("故障"),
    MAINTENANCE_REQUIRED("维护"),
    LOCKED("锁机")
}

data class EquipmentInventory(
    val id: Long = 0,
    val skuId: Long? = null,
    val skuName: String? = null,
    val sn: String? = null,
    val operationalStatus: OperationalStatus = OperationalStatus.IN_STOCK,
    val deviceStatus: DeviceStatus = DeviceStatus.NORMAL,
    val virtualContractId: Long? = null,
    val vcTypeName: String? = null,
    val pointId: Long? = null,
    val pointName: String? = null,
    val depositAmount: Double = 0.0,
    val depositTimestamp: Long? = null
)

// ==================== Material Inventory ====================

/**
 * 库存分布
 * pointId: 点位ID（统一使用Points体系）
 * pointName: 点位名称（用于显示）
 * quantity: 库存数量
 */
data class StockDistribution(
    val pointId: Long,
    val pointName: String,
    val quantity: Int
)

data class MaterialInventory(
    val id: Long = 0,
    val skuId: Long,
    val skuName: String,
    val stockDistribution: List<StockDistribution> = emptyList(),
    val averagePrice: Double = 0.0,
    val totalBalance: Double = 0.0
)

// ==================== Inventory Transfer ====================

data class InventoryTransfer(
    val id: Long = 0,
    val fromWarehouse: String,
    val toWarehouse: String,
    val skuId: Long,
    val skuName: String,
    val quantity: Int,
    val timestamp: Long = System.currentTimeMillis(),
    val note: String? = null
)

// ==================== Inventory Check ====================

data class InventoryCheck(
    val id: Long = 0,
    val warehouseName: String,
    val skuId: Long,
    val skuName: String,
    val systemQuantity: Int,
    val actualQuantity: Int,
    val difference: Int = actualQuantity - systemQuantity,
    val checkTimestamp: Long = System.currentTimeMillis(),
    val note: String? = null
)
