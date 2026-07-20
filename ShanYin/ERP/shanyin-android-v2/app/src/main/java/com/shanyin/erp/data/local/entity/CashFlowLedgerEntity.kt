package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "cash_flow_ledger",
    foreignKeys = [
        ForeignKey(
            entity = FinancialJournalEntity::class,
            parentColumns = ["id"],
            childColumns = ["journal_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("journal_id")]
)
data class CashFlowLedgerEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "journal_id")
    val journalId: Long,
    @ColumnInfo(name = "main_category")
    val mainCategory: String? = null, // 经营性，投资性、融资性
    @ColumnInfo(name = "direction")
    val direction: String? = null, // 流入、流出
    @ColumnInfo(name = "amount")
    val amount: Double = 0.0
)
