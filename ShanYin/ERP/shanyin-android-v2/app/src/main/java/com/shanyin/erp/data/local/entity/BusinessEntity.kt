package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "business",
    foreignKeys = [
        ForeignKey(
            entity = ChannelCustomerEntity::class,
            parentColumns = ["id"],
            childColumns = ["customer_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = ContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["contract_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [Index("customer_id"), Index("contract_id")]
)
data class BusinessEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "customer_id")
    val customerId: Long? = null,
    @ColumnInfo(name = "contract_id")
    val contractId: Long? = null,
    @ColumnInfo(name = "status")
    val status: String? = null, // 前期接洽、业务评估、客户反馈、合作落地、业务开展、业务暂缓、业务终止
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis(),
    @ColumnInfo(name = "details")
    val details: String? = null // JSON: 记录业务演进历史
)
