package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "supply_chain_items",
    foreignKeys = [
        ForeignKey(
            entity = SupplyChainEntity::class,
            parentColumns = ["id"],
            childColumns = ["supply_chain_id"],
            onDelete = ForeignKey.CASCADE
        ),
        ForeignKey(
            entity = SkuEntity::class,
            parentColumns = ["id"],
            childColumns = ["sku_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("supply_chain_id"), Index("sku_id")]
)
data class SupplyChainItemEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "supply_chain_id")
    val supplyChainId: Long,
    @ColumnInfo(name = "sku_id")
    val skuId: Long,
    @ColumnInfo(name = "price")
    val price: Double? = null,
    @ColumnInfo(name = "deposit")
    val deposit: Double? = null,
    @ColumnInfo(name = "is_floating")
    val isFloating: Boolean = false
)
