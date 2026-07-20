package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.domain.model.CashFlowDirection
import com.shanyin.erp.domain.model.CashFlowMainCategory
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.CashFlowLedgerRepository
import com.shanyin.erp.domain.repository.FinanceAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import java.util.Calendar
import javax.inject.Inject

// ==================== 财务报表数据结构 ====================

/**
 * 损益表（P&L Statement）
 *
 * 结构：
 * - 收入: 主营业务收入 + 其他业务收入
 * - 成本: 主营业务成本
 * - 费用: 销售费用 + 管理费用 + 财务费用
 * - 其他利得/损失
 * - 净利润 = 收入 - 成本 - 费用
 */
data class ProfitAndLossStatement(
    val year: Int,
    val month: Int,
    val revenue: Double = 0.0,          // 主营业务收入
    val otherRevenue: Double = 0.0,      // 其他业务收入
    val totalRevenue: Double = 0.0,      // 收入合计
    val costOfSales: Double = 0.0,       // 主营业务成本
    val grossProfit: Double = 0.0,       // 毛利润
    val sellingExpense: Double = 0.0,    // 销售费用
    val adminExpense: Double = 0.0,      // 管理费用
    val financialExpense: Double = 0.0,  // 财务费用
    val totalExpense: Double = 0.0,      // 费用合计
    val netProfit: Double = 0.0         // 净利润
)

/**
 * 资产负债表（Balance Sheet）
 *
 * 结构：
 * - 资产: 流动资产 + 非流动资产
 * - 负债: 流动负债
 * - 所有者权益
 * - 负债合计 + 所有者权益合计
 */
data class BalanceSheet(
    val year: Int,
    val month: Int,
    // 资产
    val bankBalances: Double = 0.0,        // 银行存款
    val accountsReceivable: Double = 0.0,   // 应收账款
    val prepayments: Double = 0.0,          // 预付账款
    val otherReceivables: Double = 0.0,     // 其他应收款
    val totalCurrentAssets: Double = 0.0,   // 流动资产合计
    val totalNonCurrentAssets: Double = 0.0, // 非流动资产合计
    val totalAssets: Double = 0.0,           // 资产总计
    // 负债
    val accountsPayable: Double = 0.0,      // 应付账款
    val advanceCollections: Double = 0.0,    // 预收账款
    val otherPayables: Double = 0.0,         // 其他应付款（押金）
    val totalCurrentLiabilities: Double = 0.0, // 流动负债合计
    val totalLiabilities: Double = 0.0,      // 负债总计
    // 权益
    val totalEquity: Double = 0.0            // 所有者权益合计
)

/**
 * 现金流量表（Cash Flow Statement）
 *
 * 基于 CashFlowLedger 分类汇总：
 * - 经营活动现金流: OPERATING
 * - 投资活动现金流: INVESTING
 * - 筹资活动现金流: FINANCING
 */
data class CashFlowStatement(
    val year: Int,
    val month: Int,
    val operatingInflow: Double = 0.0,
    val operatingOutflow: Double = 0.0,
    val operatingNetFlow: Double = 0.0,   // 经营活动净现金流
    val investingInflow: Double = 0.0,
    val investingOutflow: Double = 0.0,
    val investingNetFlow: Double = 0.0,    // 投资活动净现金流
    val financingInflow: Double = 0.0,
    val financingOutflow: Double = 0.0,
    val financingNetFlow: Double = 0.0,   // 筹资活动净现金流
    val totalNetFlow: Double = 0.0        // 现金净增加额
)

// ==================== 财务报表 Use Cases ====================

/**
 * 损益表 — 对应 Desktop 利润表
 *
 * 计算逻辑：
 * - 收入: FinancialJournal 中贷方科目为收入类（主营业务收入等）
 * - 成本: 借方科目为成本类（主营业务成本等）
 * - 费用: 借方科目为费用类（销售费用、管理费用、财务费用）
 *
 * 预置科目名称（需在 finance_accounts 表中预置）：
 * - 收入类: 主营业务收入, 其他业务收入
 * - 成本类: 主营业务成本
 * - 费用类: 销售费用, 管理费用, 财务费用
 */
class GetProfitAndLossStatementUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository
) {
    suspend operator fun invoke(year: Int, month: Int): ProfitAndLossStatement {
        val (startDate, endDate) = getMonthRange(year, month)
        val entries = journalRepo.getAll().first()
            .filter { it.transactionDate in startDate..endDate }

        val revenueNames = setOf("主营业务收入")
        val otherRevenueNames = setOf("其他业务收入")
        val costNames = setOf("主营业务成本")
        val sellingNames = setOf("销售费用")
        val adminNames = setOf("管理费用")
        val financialNames = setOf("财务费用")

        val revenue = entries.filter { it.accountName in revenueNames }.sumOf { it.credit }
        val otherRevenue = entries.filter { it.accountName in otherRevenueNames }.sumOf { it.credit }
        val totalRevenue = revenue + otherRevenue

        val costOfSales = entries.filter { it.accountName in costNames }.sumOf { it.debit }
        val grossProfit = totalRevenue - costOfSales

        val sellingExpense = entries.filter { it.accountName in sellingNames }.sumOf { it.debit }
        val adminExpense = entries.filter { it.accountName in adminNames }.sumOf { it.debit }
        val financialExpense = entries.filter { it.accountName in financialNames }.sumOf { it.debit }
        val totalExpense = sellingExpense + adminExpense + financialExpense

        val netProfit = grossProfit - totalExpense

        return ProfitAndLossStatement(
            year = year,
            month = month,
            revenue = revenue,
            otherRevenue = otherRevenue,
            totalRevenue = totalRevenue,
            costOfSales = costOfSales,
            grossProfit = grossProfit,
            sellingExpense = sellingExpense,
            adminExpense = adminExpense,
            financialExpense = financialExpense,
            totalExpense = totalExpense,
            netProfit = netProfit
        )
    }

    private fun getMonthRange(year: Int, month: Int): Pair<Long, Long> {
        val calendar = Calendar.getInstance().apply {
            set(year, month - 1, 1, 0, 0, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val start = calendar.timeInMillis
        calendar.set(Calendar.DAY_OF_MONTH, calendar.getActualMaximum(Calendar.DAY_OF_MONTH))
        calendar.set(23, 59, 59)
        calendar.set(Calendar.MILLISECOND, 999)
        val end = calendar.timeInMillis
        return start to end
    }
}

/**
 * 资产负债表 — 对应 Desktop 资产负债表
 *
 * 计算逻辑：
 * - 资产类科目余额 = Σdebit - Σcredit
 * - 负债类科目余额 = Σcredit - Σdebit
 *
 * 银行存款: "银行存款" 账户余额
 * 应收账款: "应收账款-客户" 账户余额（AR）
 * 预付账款: "预付账款-供应商" 账户余额
 * 应付账款: "应付账款-设备款/物料款" 账户余额（AP）
 * 预收账款: "预收账款-客户" 账户余额
 * 其他应付款: "其他应付款-押金" 账户余额
 */
class GetBalanceSheetUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val bankAccountRepo: BankAccountRepository
) {
    suspend operator fun invoke(year: Int, month: Int): BalanceSheet {
        val (_, endDate) = getMonthRange(year, month)
        val entries = journalRepo.getAll().first()
            .filter { it.transactionDate <= endDate }

        // 资产类：借方余额 = Σdebit - Σcredit
        val bankNames = setOf("银行存款")
        val arNames = setOf("应收账款", "应收账款-客户")
        val prepaymentNames = setOf("预付账款", "预付账款-供应商")

        val bankBalances = calculateAssetBalance(entries, bankNames)
        val accountsReceivable = calculateAssetBalance(entries, arNames)
        val prepayments = calculateAssetBalance(entries, prepaymentNames)

        // 负债类：贷方余额 = Σcredit - Σdebit
        val apNames = setOf("应付账款", "应付账款-设备款", "应付账款-物料款")
        val advanceNames = setOf("预收账款", "预收账款-客户")
        val otherPayableNames = setOf("其他应付款", "其他应付款-押金")

        val accountsPayable = calculateLiabilityBalance(entries, apNames)
        val advanceCollections = calculateLiabilityBalance(entries, advanceNames)
        val otherPayables = calculateLiabilityBalance(entries, otherPayableNames)

        val totalCurrentAssets = bankBalances + accountsReceivable + prepayments + otherReceivables(entries)
        val totalLiabilities = accountsPayable + advanceCollections + otherPayables
        val totalEquity = totalCurrentAssets - totalLiabilities  // 简化：权益 = 资产 - 负债

        return BalanceSheet(
            year = year,
            month = month,
            bankBalances = bankBalances,
            accountsReceivable = accountsReceivable,
            prepayments = prepayments,
            otherReceivables = otherReceivables(entries),
            totalCurrentAssets = totalCurrentAssets,
            totalAssets = totalCurrentAssets,
            accountsPayable = accountsPayable,
            advanceCollections = advanceCollections,
            otherPayables = otherPayables,
            totalCurrentLiabilities = totalLiabilities,
            totalLiabilities = totalLiabilities,
            totalEquity = totalEquity
        )
    }

    /** 资产类科目余额 = Σdebit - Σcredit */
    private fun calculateAssetBalance(entries: List<com.shanyin.erp.domain.model.FinancialJournalEntry>, names: Set<String>): Double {
        val relevant = entries.filter { it.accountName in names }
        return relevant.sumOf { it.debit } - relevant.sumOf { it.credit }
    }

    /** 负债类科目余额 = Σcredit - Σdebit */
    private fun calculateLiabilityBalance(entries: List<com.shanyin.erp.domain.model.FinancialJournalEntry>, names: Set<String>): Double {
        val relevant = entries.filter { it.accountName in names }
        return relevant.sumOf { it.credit } - relevant.sumOf { it.debit }
    }

    private fun otherReceivables(entries: List<com.shanyin.erp.domain.model.FinancialJournalEntry>): Double {
        // 其他应收款：简化处理，暂无专门科目
        return 0.0
    }

    private fun getMonthRange(year: Int, month: Int): Pair<Long, Long> {
        val calendar = Calendar.getInstance().apply {
            set(year, month - 1, 1, 0, 0, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val start = calendar.timeInMillis
        calendar.set(Calendar.DAY_OF_MONTH, calendar.getActualMaximum(Calendar.DAY_OF_MONTH))
        calendar.set(23, 59, 59)
        calendar.set(Calendar.MILLISECOND, 999)
        val end = calendar.timeInMillis
        return start to end
    }
}

/**
 * 现金流量表 — 基于 CashFlowLedger 分类
 *
 * 对应 Desktop 现金流量表：
 * - 经营活动: OPERATING（CashFlowLedger.mainCategory）
 * - 投资活动: INVESTING
 * - 筹资活动: FINANCING
 *
 * 现金流 = Σ(CashFlowLedger.amount) 按 direction 和 mainCategory 分类汇总
 */
class GetCashFlowStatementUseCase @Inject constructor(
    private val ledgerRepo: CashFlowLedgerRepository,
    private val journalRepo: FinancialJournalRepository
) {
    suspend operator fun invoke(year: Int, month: Int): CashFlowStatement {
        val (startDate, endDate) = getMonthRange(year, month)

        // 从 CashFlowLedger 获取分类汇总（CashFlowLedger.transactionDate 已迁移）
        val monthLedgers = ledgerRepo.getByDateRange(startDate, endDate).first()

        // 按 mainCategory 分类
        val operating = monthLedgers.filter { it.mainCategory == com.shanyin.erp.domain.model.CashFlowMainCategory.OPERATING }
        val investing = monthLedgers.filter { it.mainCategory == com.shanyin.erp.domain.model.CashFlowMainCategory.INVESTING }
        val financing = monthLedgers.filter { it.mainCategory == com.shanyin.erp.domain.model.CashFlowMainCategory.FINANCING }

        val operatingInflow = operating.filter { it.direction == com.shanyin.erp.domain.model.CashFlowDirection.INFLOW }.sumOf { it.amount }
        val operatingOutflow = operating.filter { it.direction == com.shanyin.erp.domain.model.CashFlowDirection.OUTFLOW }.sumOf { it.amount }
        val operatingNetFlow = operatingInflow - operatingOutflow

        val investingInflow = investing.filter { it.direction == com.shanyin.erp.domain.model.CashFlowDirection.INFLOW }.sumOf { it.amount }
        val investingOutflow = investing.filter { it.direction == com.shanyin.erp.domain.model.CashFlowDirection.OUTFLOW }.sumOf { it.amount }
        val investingNetFlow = investingInflow - investingOutflow

        val financingInflow = financing.filter { it.direction == com.shanyin.erp.domain.model.CashFlowDirection.INFLOW }.sumOf { it.amount }
        val financingOutflow = financing.filter { it.direction == com.shanyin.erp.domain.model.CashFlowDirection.OUTFLOW }.sumOf { it.amount }
        val financingNetFlow = financingInflow - financingOutflow

        return CashFlowStatement(
            year = year,
            month = month,
            operatingInflow = operatingInflow,
            operatingOutflow = operatingOutflow,
            operatingNetFlow = operatingNetFlow,
            investingInflow = investingInflow,
            investingOutflow = investingOutflow,
            investingNetFlow = investingNetFlow,
            financingInflow = financingInflow,
            financingOutflow = financingOutflow,
            financingNetFlow = financingNetFlow,
            totalNetFlow = operatingNetFlow + investingNetFlow + financingNetFlow
        )
    }

    private fun getMonthRange(year: Int, month: Int): Pair<Long, Long> {
        val calendar = Calendar.getInstance().apply {
            set(year, month - 1, 1, 0, 0, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val start = calendar.timeInMillis
        calendar.set(Calendar.DAY_OF_MONTH, calendar.getActualMaximum(Calendar.DAY_OF_MONTH))
        calendar.set(23, 59, 59)
        calendar.set(Calendar.MILLISECOND, 999)
        val end = calendar.timeInMillis
        return start to end
    }
}
