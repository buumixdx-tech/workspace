package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "vc_status_logs",
    foreignKeys = [
        ForeignKey(
            entity = VirtualContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["vc_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("vc_id")]
)
data class VirtualContractStatusLogEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "vc_id")
    val vcId: Long,
    @ColumnInfo(name = "category")
    val category: String, // 'status', 'subject', 'cash'
    @ColumnInfo(name = "status_name")
    val statusName: String, // e.g., '已发货', '完成'
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis()
)
