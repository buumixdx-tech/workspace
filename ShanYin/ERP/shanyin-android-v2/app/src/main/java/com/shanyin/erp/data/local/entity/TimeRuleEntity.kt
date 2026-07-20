package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "time_rules")
data class TimeRuleEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    // === 关联信息 ===
    @ColumnInfo(name = "related_id")
    val relatedId: Long,
    @ColumnInfo(name = "related_type")
    val relatedType: String, // 业务、供应链、虚拟合同、物流
    @ColumnInfo(name = "inherit")
    val inherit: Int = 0, // 0=自身定制, 1=近继承, 2=远继承

    // === 责任方 ===
    @ColumnInfo(name = "party")
    val party: String? = null, // 规则责任方 (我方/客户/供应商)

    // === 触发事件 ===
    @ColumnInfo(name = "trigger_event")
    val triggerEvent: String? = null, // 触发事件类型 (或 "绝对日期")
    @ColumnInfo(name = "tge_param1")
    val tgeParam1: String? = null,
    @ColumnInfo(name = "tge_param2")
    val tgeParam2: String? = null,
    @ColumnInfo(name = "trigger_time")
    val triggerTime: Long? = null,

    // === 目标事件 ===
    @ColumnInfo(name = "target_event")
    val targetEvent: String, // 目标事件类型
    @ColumnInfo(name = "tae_param1")
    val taeParam1: String? = null,
    @ColumnInfo(name = "tae_param2")
    val taeParam2: String? = null,
    @ColumnInfo(name = "target_time")
    val targetTime: Long? = null,

    // === 时间约束 ===
    @ColumnInfo(name = "offset")
    val offset: Int? = null,
    @ColumnInfo(name = "unit")
    val unit: String? = null, // 自然日、工作日
    @ColumnInfo(name = "flag_time")
    val flagTime: Long? = null, // 标杆时间
    @ColumnInfo(name = "direction")
    val direction: String? = null, // before/after

    // === 监控与结果 ===
    @ColumnInfo(name = "warning")
    val warning: String? = null, // 绿色、黄色、橙色、红色
    @ColumnInfo(name = "result")
    val result: String? = null, // 合规、违规
    @ColumnInfo(name = "status")
    val status: String = "生效", // 失效、生效、有结果、结束

    // === 时间戳 ===
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis(),
    @ColumnInfo(name = "resultstamp")
    val resultstamp: Long? = null,
    @ColumnInfo(name = "endstamp")
    val endstamp: Long? = null
)
