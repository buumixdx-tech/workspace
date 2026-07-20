package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "contracts")
data class ContractEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "contract_number")
    val contractNumber: String,
    @ColumnInfo(name = "type")
    val type: String? = null, // 合作合同，设备采购合同、物料采购合同、外部合作合同
    @ColumnInfo(name = "status")
    val status: String? = null, // 签约完成、生效、过期、终止
    @ColumnInfo(name = "parties")
    val parties: String? = null, // JSON: 签约方信息
    @ColumnInfo(name = "content")
    val content: String? = null, // JSON: 合同详情
    @ColumnInfo(name = "signed_date")
    val signedDate: Long? = null,
    @ColumnInfo(name = "effective_date")
    val effectiveDate: Long? = null,
    @ColumnInfo(name = "expiry_date")
    val expiryDate: Long? = null,
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis()
)
