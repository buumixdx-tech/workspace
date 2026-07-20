package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "virtual_contracts",
    foreignKeys = [
        ForeignKey(
            entity = BusinessEntity::class,
            parentColumns = ["id"],
            childColumns = ["business_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = SupplyChainEntity::class,
            parentColumns = ["id"],
            childColumns = ["supply_chain_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [
        Index("business_id"),
        Index("status"),
        Index("type"),
        Index("supply_chain_id"),
        Index("business_id", "status")
    ]
)
data class VirtualContractEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "description")
    val description: String? = null,
    @ColumnInfo(name = "business_id")
    val businessId: Long? = null,
    @ColumnInfo(name = "supply_chain_id")
    val supplyChainId: Long? = null,
    @ColumnInfo(name = "related_vc_id")
    val relatedVcId: Long? = null,
    @ColumnInfo(name = "type")
    val type: String? = null, // 设备采购、物料供应、物料采购、退货、设备维护
    @ColumnInfo(name = "summary")
    val summary: String? = null,
    @ColumnInfo(name = "elements")
    val elements: String? = null, // JSON: SKU、数量、单价、时间、物流、支付模式
    @ColumnInfo(name = "deposit_info")
    val depositInfo: String? = null, // JSON: 应收/实收押金、总额、最后流水ID、调整原因
    @ColumnInfo(name = "status")
    val status: String? = null, // 执行、完成、终止
    @ColumnInfo(name = "subject_status")
    val subjectStatus: String? = null, // 执行、发货、签收、完成
    @ColumnInfo(name = "cash_status")
    val cashStatus: String? = null, // 执行、预付、完成
    @ColumnInfo(name = "status_timestamp")
    val statusTimestamp: Long? = null,
    @ColumnInfo(name = "subject_status_timestamp")
    val subjectStatusTimestamp: Long? = null,
    @ColumnInfo(name = "cash_status_timestamp")
    val cashStatusTimestamp: Long? = null,
    @ColumnInfo(name = "return_direction")
    val returnDirection: String? = null // 退货方向（仅 RETURN VC 使用）
)
