package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "supply_chains",
    foreignKeys = [
        ForeignKey(
            entity = SupplierEntity::class,
            parentColumns = ["id"],
            childColumns = ["supplier_id"],
            onDelete = ForeignKey.CASCADE
        ),
        ForeignKey(
            entity = ContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["contract_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [Index("supplier_id"), Index("contract_id")]
)
data class SupplyChainEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "supplier_id")
    val supplierId: Long,
    @ColumnInfo(name = "supplier_name")
    val supplierName: String,
    @ColumnInfo(name = "type")
    val type: String? = null, // 物料 or 设备
    @ColumnInfo(name = "contract_id")
    val contractId: Long? = null,
    @ColumnInfo(name = "pricing_config")
    val pricingConfig: String? = null, // JSON
    @ColumnInfo(name = "payment_terms")
    val paymentTerms: String? = null // JSON
)
