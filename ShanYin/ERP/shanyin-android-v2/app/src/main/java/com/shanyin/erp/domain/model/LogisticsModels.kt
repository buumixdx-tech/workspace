package com.shanyin.erp.domain.model

// ==================== Logistics Status ====================

enum class LogisticsStatus(val displayName: String) {
    PENDING("待发货"),
    IN_TRANSIT("在途"),
    SIGNED("签收"),
    COMPLETED("完成");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "TRANSIT" to IN_TRANSIT,
            "FINISH" to COMPLETED
        )

        fun fromDbName(name: String?): LogisticsStatus? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        IN_TRANSIT -> "TRANSIT"
        COMPLETED -> "FINISH"
        else -> this.name
    }
}

enum class ExpressStatus(val displayName: String) {
    PENDING("待发货"),
    IN_TRANSIT("在途"),
    SIGNED("签收");

    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "TRANSIT" to IN_TRANSIT
        )

        fun fromDbName(name: String?): ExpressStatus? {
            if (name == null) return null
            entries.find { it.name == name }?.let { return it }
            DESKTOP_TO_MOBILE[name]?.let { return it }
            return entries.find { it.displayName == name }
        }
    }

    fun toDbName(): String = when (this) {
        IN_TRANSIT -> "TRANSIT"
        else -> this.name
    }
}

// ==================== Address Info ====================

/**
 * 快递单地址信息 - 收发分离结构
 * 与 Desktop address_info 格式对齐
 */
data class AddressInfo(
    // ========== 收货方信息 ==========
    val receivingPointId: Long? = null,          // 收货点位ID
    val receivingPointName: String? = null,     // 收货点位名称
    val receivingContact: String? = null,       // 收货联系人
    val receivingPhone: String? = null,          // 收货联系电话
    val receivingProvince: String? = null,       // 收货省份
    val receivingCity: String? = null,           // 收货城市
    val receivingDistrict: String? = null,        // 收货区县
    val receivingAddress: String? = null,        // 收货详细地址

    // ========== 发货方信息 ==========
    val shippingPointId: Long? = null,           // 发货点位ID
    val shippingPointName: String? = null,       // 发货点位名称
    val shippingContact: String? = null,        // 发货联系人
    val shippingPhone: String? = null,           // 发货联系电话
    val shippingProvince: String? = null,        // 发货省份
    val shippingCity: String? = null,            // 发货城市
    val shippingDistrict: String? = null,        // 发货区县
    val shippingAddress: String? = null,          // 发货详细地址

    // ========== 兼容旧数据字段 ==========
    val contactName: String? = null,             // 旧：收货联系人
    val phone: String? = null,                   // 旧：收货电话
    val province: String? = null,                // 旧：收货省份
    val city: String? = null,                    // 旧：收货城市
    val district: String? = null,                // 旧：收货区县
    val address: String? = null                 // 旧：收货详细地址
) {
    fun toDisplayString(): String {
        return listOfNotNull(
            receivingProvince ?: province,
            receivingCity ?: city,
            receivingDistrict ?: district,
            receivingAddress ?: address
        ).joinToString("")
    }

    // 兼容旧字段 getter - 优先返回新字段，兼容旧数据
    fun getContactNameCompat(): String? = receivingContact ?: contactName
    fun getPhoneCompat(): String? = receivingPhone ?: phone
    fun getProvinceCompat(): String? = receivingProvince ?: province
    fun getCityCompat(): String? = receivingCity ?: city
    fun getDistrictCompat(): String? = receivingDistrict ?: district
    fun getAddressCompat(): String? = receivingAddress ?: address
}

// ==================== Express Item ====================

data class ExpressItem(
    val skuId: Long,
    val skuName: String,
    val quantity: Int
)

// ==================== Logistics ====================

data class Logistics(
    val id: Long = 0,
    val virtualContractId: Long,
    val vcTypeName: String? = null,
    val financeTriggered: Boolean = false,
    val status: LogisticsStatus = LogisticsStatus.PENDING,
    val timestamp: Long = System.currentTimeMillis(),
    val expressOrders: List<ExpressOrder> = emptyList()
)

// ==================== Express Order ====================

data class ExpressOrder(
    val id: Long = 0,
    val logisticsId: Long,
    val trackingNumber: String? = null,
    val items: List<ExpressItem> = emptyList(),
    val addressInfo: AddressInfo = AddressInfo(),
    val status: ExpressStatus = ExpressStatus.PENDING,
    val timestamp: Long = System.currentTimeMillis()
)

// ==================== Warehouse Confirmation ====================

data class WarehouseConfirmation(
    val id: Long = 0,
    val logisticsId: Long,
    val expressOrderId: Long? = null,
    val warehouseName: String,
    val confirmedAt: Long = System.currentTimeMillis(),
    val confirmedBy: String? = null,
    val notes: String? = null
)
