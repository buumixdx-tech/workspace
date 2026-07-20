package com.shanyin.erp.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "cash_flows",
    foreignKeys = [
        ForeignKey(
            entity = VirtualContractEntity::class,
            parentColumns = ["id"],
            childColumns = ["virtual_contract_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = BankAccountEntity::class,
            parentColumns = ["id"],
            childColumns = ["payer_account_id"],
            onDelete = ForeignKey.SET_NULL
        ),
        ForeignKey(
            entity = BankAccountEntity::class,
            parentColumns = ["id"],
            childColumns = ["payee_account_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [
        Index("virtual_contract_id"),
        Index("type"),
        Index("transaction_date"),
        Index("virtual_contract_id", "type"),
        Index("payer_account_id"),
        Index("payee_account_id")
    ]
)
data class CashFlowEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "virtual_contract_id")
    val virtualContractId: Long? = null,
    @ColumnInfo(name = "type")
    val type: String? = null, // 预付、履约、罚金、押金、退还押金、退款、冲抵入金、冲抵支付
    @ColumnInfo(name = "amount")
    val amount: Double = 0.0,
    @ColumnInfo(name = "payer_account_id")
    val payerAccountId: Long? = null,
    @ColumnInfo(name = "payer_account_name")
    val payerAccountName: String? = null,
    @ColumnInfo(name = "payee_account_id")
    val payeeAccountId: Long? = null,
    @ColumnInfo(name = "payee_account_name")
    val payeeAccountName: String? = null,
    @ColumnInfo(name = "finance_triggered")
    val financeTriggered: Boolean = false,
    @ColumnInfo(name = "payment_info")
    val paymentInfo: String? = null, // JSON
    @ColumnInfo(name = "voucher_path")
    val voucherPath: String? = null,
    @ColumnInfo(name = "description")
    val description: String? = null,
    @ColumnInfo(name = "transaction_date")
    val transactionDate: Long? = null,
    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis()
)
