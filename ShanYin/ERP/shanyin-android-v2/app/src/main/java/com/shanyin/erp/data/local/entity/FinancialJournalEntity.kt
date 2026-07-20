package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "financial_journal",
    foreignKeys = [
        ForeignKey(
            entity = FinanceAccountEntity::class,
            parentColumns = ["id"],
            childColumns = ["account_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = VirtualContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["ref_vc_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [
        Index("account_id"),
        Index("ref_vc_id")
    ]
)
data class FinancialJournalEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "voucher_no")
    val voucherNo: String? = null, // 凭证分组号
    @ColumnInfo(name = "account_id")
    val accountId: Long? = null,
    @ColumnInfo(name = "debit")
    val debit: Double = 0.0,
    @ColumnInfo(name = "credit")
    val credit: Double = 0.0,
    @ColumnInfo(name = "summary")
    val summary: String? = null,
    @ColumnInfo(name = "ref_type")
    val refType: String? = null, // 物流、资金流
    @ColumnInfo(name = "ref_id")
    val refId: Long? = null,
    @ColumnInfo(name = "ref_vc_id")
    val refVcId: Long? = null,
    @ColumnInfo(name = "transaction_date")
    val transactionDate: Long = System.currentTimeMillis()
)
