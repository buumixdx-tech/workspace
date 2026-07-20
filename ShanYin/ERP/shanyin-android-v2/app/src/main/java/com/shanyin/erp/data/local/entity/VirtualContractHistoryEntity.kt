package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "vc_history",
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
data class VirtualContractHistoryEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "vc_id")
    val vcId: Long,
    @ColumnInfo(name = "original_data")
    val originalData: String? = null, // JSON
    @ColumnInfo(name = "change_date")
    val changeDate: Long = System.currentTimeMillis(),
    @ColumnInfo(name = "change_reason")
    val changeReason: String? = null
)
