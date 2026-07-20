package com.shanyin.erp.domain.model

// ==================== Finance Account ====================

enum class FinanceCategory(val displayName: String) {
    ASSET("资产"),
    LIABILITY("负债"),
    EQUITY("权益"),
    PROFIT_LOSS("损益")
}

enum class CounterpartType(val displayName: String) {
    CUSTOMER("客户"),
    SUPPLIER("供应商"),
    PARTNER("合作伙伴"),
    INTERNAL("内部")
}

enum class AccountDirection(val displayName: String) {
    DEBIT("借"),
    CREDIT("贷")
}

data class FinanceAccount(
    val id: Long = 0,
    val category: FinanceCategory? = null,
    val level1Name: String,
    val level2Name: String? = null,
    val counterpartType: CounterpartType? = null,
    val counterpartId: Long? = null,
    val direction: AccountDirection? = null
)

// ==================== Cash Flow ====================

enum class CashFlowType(val displayName: String) {
    PREPAYMENT("预付"),
    PERFORMANCE("履约"),
    PENALTY("罚金"),
    DEPOSIT("押金"),
    DEPOSIT_REFUND("退还押金"),
    REFUND("退款"),
    OFFSET_INFLOW("冲抵入金"),
    OFFSET_OUTFLOW("冲抵支付"),
    DEPOSIT_OFFSET_IN("押金冲抵入金");

    /**
     * 从数据库存储的名称解析为 CashFlowType
     * 同时兼容 Mobile 枚举名和 Desktop 数据库中的旧名称
     */
    companion object {
        private val DESKTOP_TO_MOBILE = mapOf(
            "FULFILLMENT" to PERFORMANCE,
            "RETURN_DEPOSIT" to DEPOSIT_REFUND,
            "OFFSET_PAY" to OFFSET_OUTFLOW,
            "OFFSET_IN" to OFFSET_INFLOW
        )

        fun fromDbName(name: String?): CashFlowType? {
            if (name == null) return null
            // 先尝试直接匹配 Mobile 枚举名
            entries.find { it.name == name }?.let { return it }
            // 再尝试 Desktop 名称映射
            DESKTOP_TO_MOBILE[name]?.let { return it }
            // 最后尝试 displayName 匹配
            return entries.find { it.displayName == name }
        }
    }

    /**
     * 转换为 Desktop 数据库存储的名称（用于同步到 Desktop）
     * 仅对有 Desktop 别名的类型返回别名
     */
    fun toDesktopName(): String = when (this) {
        PERFORMANCE -> "FULFILLMENT"
        DEPOSIT_REFUND -> "RETURN_DEPOSIT"
        OFFSET_OUTFLOW -> "OFFSET_PAY"
        OFFSET_INFLOW -> "OFFSET_IN"
        else -> this.name
    }
}

data class PaymentInfo(
    val paymentMethod: String? = null,
    val bankName: String? = null,
    val accountNo: String? = null,
    val referenceNo: String? = null
)

data class CashFlow(
    val id: Long = 0,
    val virtualContractId: Long? = null,
    val type: CashFlowType? = null,
    val amount: Double = 0.0,
    val payerAccountId: Long? = null,
    val payerAccountName: String? = null,
    val payeeAccountId: Long? = null,
    val payeeAccountName: String? = null,
    val financeTriggered: Boolean = false,
    val paymentInfo: PaymentInfo? = null,
    val voucherPath: String? = null,
    val description: String? = null,
    val transactionDate: Long? = null,
    val timestamp: Long = System.currentTimeMillis()
)

// ==================== Cash Flow Ledger ====================

enum class CashFlowDirection(val displayName: String) {
    INFLOW("流入"),
    OUTFLOW("流出")
}

enum class CashFlowMainCategory(val displayName: String) {
    OPERATING("经营性"),
    INVESTING("投资性"),
    FINANCING("融资性")
}

data class CashFlowLedger(
    val id: Long = 0,
    val journalId: Long,
    val mainCategory: CashFlowMainCategory? = null,
    val direction: CashFlowDirection? = null,
    val amount: Double = 0.0,
    val transactionDate: Long = System.currentTimeMillis()
)

// ==================== Financial Journal (Double Entry) ====================

enum class RefType(val displayName: String) {
    LOGISTICS("物流"),
    CASH_FLOW("资金流"),
    INTERNAL_TRANSFER("内部划拨"),
    EXTERNAL_FUND("外部出入金")
}

data class FinancialJournalEntry(
    val id: Long = 0,
    val voucherNo: String? = null,  // Groups entries with same voucher
    val accountId: Long? = null,
    val accountName: String? = null,
    val debit: Double = 0.0,
    val credit: Double = 0.0,
    val summary: String? = null,
    val refType: RefType? = null,
    val refId: Long? = null,
    val refVcId: Long? = null,
    val transactionDate: Long = System.currentTimeMillis()
) {
    companion object {
        /**
         * 从 CashFlow 创建 FinancialJournalEntry（借方或贷方分录）
         * @param cf 源 CashFlow
         * @param accountId 科目ID（借方科目或贷方科目）
         * @param accountName 科目名称
         * @param isDebit true=借方分录, false=贷方分录
         */
        fun fromCashFlow(
            cf: CashFlow,
            accountId: Long,
            accountName: String,
            isDebit: Boolean
        ): FinancialJournalEntry = FinancialJournalEntry(
            accountId = accountId,
            accountName = accountName,
            debit = if (isDebit) cf.amount else 0.0,
            credit = if (isDebit) 0.0 else cf.amount,
            summary = "${cf.type?.displayName ?: ""} ${cf.description ?: ""}".trim(),
            refType = RefType.CASH_FLOW,
            refId = cf.id,
            refVcId = cf.virtualContractId,
            transactionDate = cf.transactionDate ?: cf.timestamp
        )
    }
}

data class Voucher(
    val voucherNo: String,
    val entries: List<FinancialJournalEntry>,
    val transactionDate: Long
) {
    val totalDebit: Double get() = entries.sumOf { it.debit }
    val totalCredit: Double get() = entries.sumOf { it.credit }
    val isBalanced: Boolean get() = totalDebit == totalCredit
}

// ==================== Monthly Report ====================

data class MonthlyReport(
    val id: Long = 0,
    val year: Int,
    val month: Int,
    val totalRevenue: Double = 0.0,      // 总收入
    val totalExpense: Double = 0.0,       // 总支出
    val netProfit: Double = 0.0,           // 净利润
    val totalAssetInflow: Double = 0.0,   // 资产流入
    val totalLiabilityOutflow: Double = 0.0, // 负债流出
    val cashInflow: Double = 0.0,          // 现金流入
    val cashOutflow: Double = 0.0,         // 现金流出
    val netCashFlow: Double = 0.0,         // 净现金流
    val vcCount: Int = 0,                  // 合同数量
    val completedVcCount: Int = 0,          // 完成合同数
    val logisticsCount: Int = 0             // 物流单数量
)
