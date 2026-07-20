package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "logistics",
    foreignKeys = [
        ForeignKey(
            entity = VirtualContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["virtual_contract_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("virtual_contract_id")]
)
data class LogisticsEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "virtual_contract_id")
    val virtualContractId: Long,
    @ColumnInfo(name = "finance_triggered")
    val financeTriggered: Boolean = false,
    @ColumnInfo(name = "status")
    val status: String? = null, // 待发货、在途、签收、完成、终止
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis()
)
