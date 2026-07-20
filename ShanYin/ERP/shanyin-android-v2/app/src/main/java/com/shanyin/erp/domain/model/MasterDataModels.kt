package com.shanyin.erp.domain.model

import com.google.gson.annotations.SerializedName

data class ChannelCustomer(
    val id: Long = 0,
    val name: String,
    val info: String? = null,
    val createdAt: Long = System.currentTimeMillis()
)

data class Point(
    val id: Long = 0,
    val customerId: Long? = null,
    val supplierId: Long? = null,
    val name: String,
    val address: String? = null,
    val type: PointType? = null,
    val receivingAddress: String? = null
)

enum class PointType(val displayName: String) {
    OPERATION("运营点位"),
    CUSTOMER_WAREHOUSE("客户仓"),
    OWN_WAREHOUSE("自有仓"),
    SUPPLIER_WAREHOUSE("供应商仓")
}

data class Supplier(
    val id: Long = 0,
    val name: String,
    val category: SupplierCategory? = null,
    val address: String? = null,
    val qualifications: String? = null,
    val info: String? = null
)

enum class SupplierCategory(val displayName: String) {
    EQUIPMENT("设备"),
    MATERIAL("物料"),
    BOTH("兼备")
}

data class Sku(
    val id: Long = 0,
    val supplierId: Long? = null,
    val name: String,
    val typeLevel1: SkuType? = null,
    val typeLevel2: String? = null,
    val model: String? = null,
    val description: String? = null,
    val certification: String? = null,
    val params: String? = null
)

enum class SkuType(val displayName: String) {
    EQUIPMENT("设备"),
    MATERIAL("物料")
}

data class ExternalPartner(
    val id: Long = 0,
    val type: PartnerType? = null,
    val name: String,
    val address: String? = null,
    val content: String? = null
)

enum class PartnerType(val displayName: String) {
    OUTSOURCING("外包服务商"),
    CUSTOMER_AFFILIATE("客户关联方"),
    SUPPLIER_AFFILIATE("供应商关联方"),
    OTHER("其他")
}

data class BankAccount(
    val id: Long = 0,
    val ownerType: OwnerType? = null,
    val ownerId: Long? = null,
    val accountInfo: BankAccountInfo? = null,
    val isDefault: Boolean = false
)

enum class OwnerType(val displayName: String) {
    CUSTOMER("客户"),
    SUPPLIER("供应商"),
    OURSELVES("我方"),
    PARTNER("合作伙伴")
}

data class BankAccountInfo(
    @SerializedName("银行名称") val bankName: String? = null,
    @SerializedName("开户名称") val accountName: String? = null,
    @SerializedName("银行账号") val accountNumber: String? = null,
    @SerializedName("开户行") val branch: String? = null,
    // English fallbacks
    @SerializedName("bankName") val bankNameEn: String? = null,
    @SerializedName("accountNumber") val accountNumberEn: String? = null
) {
    // Combined getters that check both Chinese and English
    val resolvedBankName: String? get() = bankName ?: bankNameEn
    val resolvedAccountNumber: String? get() = accountNumber ?: accountNumberEn
}
