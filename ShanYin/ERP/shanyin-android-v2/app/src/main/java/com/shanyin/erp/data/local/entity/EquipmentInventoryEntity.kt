package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "equipment_inventory",
    foreignKeys = [
        ForeignKey(
            entity = SkuEntity::class,
            parentColumns = ["id"],
            childColumns = ["sku_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = VirtualContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["virtual_contract_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = PointEntity::class,
            parentColumns = ["id"],
            childColumns = ["point_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [
        Index("virtual_contract_id"),
        Index("point_id"),
        Index("operational_status"),
        Index("sku_id")
    ]
)
data class EquipmentInventoryEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "sku_id")
    val skuId: Long? = null,
    @ColumnInfo(name = "sn")
    val sn: String? = null, // Device serial number
    @ColumnInfo(name = "operational_status")
    val operationalStatus: String? = null, // 库存、运营、处置
    @ColumnInfo(name = "device_status")
    val deviceStatus: String? = null, // 正常、维修、损坏、故障、维护、锁机
    @ColumnInfo(name = "virtual_contract_id")
    val virtualContractId: Long? = null,
    @ColumnInfo(name = "point_id")
    val pointId: Long? = null,
    @ColumnInfo(name = "deposit_amount")
    val depositAmount: Double = 0.0,
    @ColumnInfo(name = "deposit_timestamp")
    val depositTimestamp: Long? = null
)
