package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "finance_accounts")
data class FinanceAccountEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "category")
    val category: String? = null, // 资产、负债、权益、损益
    @ColumnInfo(name = "level1_name")
    val level1Name: String,
    @ColumnInfo(name = "level2_name")
    val level2Name: String? = null, // 交易对手名称
    @ColumnInfo(name = "counterpart_type")
    val counterpartType: String? = null, // 客户、供应商、合作伙伴、内部
    @ColumnInfo(name = "counterpart_id")
    val counterpartId: Long? = null,
    @ColumnInfo(name = "direction")
    val direction: String? = null // 借 (Debit), 贷 (Credit)
)
