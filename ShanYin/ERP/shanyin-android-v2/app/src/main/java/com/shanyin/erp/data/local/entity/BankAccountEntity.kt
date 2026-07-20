package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "bank_accounts")
data class BankAccountEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "owner_type")
    val ownerType: String? = null, // 客户、供应商、我方、合作伙伴
    @ColumnInfo(name = "owner_id")
    val ownerId: Long? = null,
    @ColumnInfo(name = "account_info")
    val accountInfo: String? = null, // JSON
    @ColumnInfo(name = "is_default")
    val isDefault: Boolean = false
)
