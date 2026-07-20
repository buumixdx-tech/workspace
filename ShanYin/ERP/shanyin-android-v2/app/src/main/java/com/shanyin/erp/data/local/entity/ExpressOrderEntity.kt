package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "express_orders",
    foreignKeys = [
        ForeignKey(
            entity = LogisticsEntity::class,
            parentColumns = ["id"],
            childColumns = ["logistics_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("logistics_id")]
)
data class ExpressOrderEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "logistics_id")
    val logisticsId: Long,
    @ColumnInfo(name = "tracking_number")
    val trackingNumber: String? = null,
    @ColumnInfo(name = "items")
    val items: String? = null, // JSON: SKU、数量
    @ColumnInfo(name = "address_info")
    val addressInfo: String? = null, // JSON
    @ColumnInfo(name = "status")
    val status: String? = null, // 待发货、在途、签收
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis()
)
