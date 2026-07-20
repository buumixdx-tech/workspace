package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "points",
    foreignKeys = [
        ForeignKey(
            entity = ChannelCustomerEntity::class,
            parentColumns = ["id"],
            childColumns = ["customer_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = SupplierEntity::class,
            parentColumns = ["id"],
            childColumns = ["supplier_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [
        Index("customer_id"),
        Index("supplier_id")
    ]
)
data class PointEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "customer_id")
    val customerId: Long? = null,
    @ColumnInfo(name = "supplier_id")
    val supplierId: Long? = null,
    @ColumnInfo(name = "name")
    val name: String,
    @ColumnInfo(name = "address")
    val address: String? = null,
    @ColumnInfo(name = "type")
    val type: String? = null, // 运营点位、客户仓、自有仓、供应商仓
    @ColumnInfo(name = "receiving_address")
    val receivingAddress: String? = null
)
