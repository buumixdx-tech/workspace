package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "material_inventory",
    foreignKeys = [
        ForeignKey(
            entity = SkuEntity::class,
            parentColumns = ["id"],
            childColumns = ["sku_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("sku_id", unique = true)]
)
data class MaterialInventoryEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "sku_id")
    val skuId: Long,
    @ColumnInfo(name = "stock_distribution")
    val stockDistribution: String? = null, // JSON: {"仓库名称": 数量}
    @ColumnInfo(name = "average_price")
    val averagePrice: Double = 0.0,
    @ColumnInfo(name = "total_balance")
    val totalBalance: Double = 0.0
)
