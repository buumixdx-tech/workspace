package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "skus",
    foreignKeys = [
        ForeignKey(
            entity = SupplierEntity::class,
            parentColumns = ["id"],
            childColumns = ["supplier_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [Index("supplier_id")]
)
data class SkuEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "supplier_id")
    val supplierId: Long? = null,
    @ColumnInfo(name = "name")
    val name: String,
    @ColumnInfo(name = "type_level1")
    val typeLevel1: String? = null, // 设备 or 物料
    @ColumnInfo(name = "type_level2")
    val typeLevel2: String? = null, // Sub-category
    @ColumnInfo(name = "model")
    val model: String? = null,
    @ColumnInfo(name = "description")
    val description: String? = null,
    @ColumnInfo(name = "certification")
    val certification: String? = null,
    @ColumnInfo(name = "params")
    val params: String? = null // JSON for parameters
)
