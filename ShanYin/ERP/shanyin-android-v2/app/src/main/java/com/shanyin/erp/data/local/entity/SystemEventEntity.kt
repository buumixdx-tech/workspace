package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "system_events")
data class SystemEventEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "event_type")
    val eventType: String, // VC_CREATED, LOGISTICS_SIGNED, AR_CLEARED
    @ColumnInfo(name = "aggregate_type")
    val aggregateType: String, // VirtualContract, CashFlow, etc.
    @ColumnInfo(name = "aggregate_id")
    val aggregateId: Long,
    @ColumnInfo(name = "payload")
    val payload: String? = null, // JSON: 关键快照数据
    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis(),
    @ColumnInfo(name = "pushed_to_ai")
    val pushedToAi: Boolean = false
)
