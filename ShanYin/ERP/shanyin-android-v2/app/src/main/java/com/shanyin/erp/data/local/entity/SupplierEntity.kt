package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "suppliers")
data class SupplierEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "name")
    val name: String,
    @ColumnInfo(name = "category")
    val category: String? = null, // 设备、物料、兼备
    @ColumnInfo(name = "address")
    val address: String? = null,
    @ColumnInfo(name = "qualifications")
    val qualifications: String? = null,
    @ColumnInfo(name = "info")
    val info: String? = null // JSON for extra info
)
