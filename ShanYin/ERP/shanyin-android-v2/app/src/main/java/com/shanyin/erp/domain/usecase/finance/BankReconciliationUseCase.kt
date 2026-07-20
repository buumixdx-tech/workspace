package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.domain.model.BankAccount
import com.shanyin.erp.domain.model.CashFlow
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.CashFlowRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject

// ==================== 银行对账数据结构 ====================

/**
 * 银行对账报告
 *
 * 对比：
 * - 账面余额：系统内该银行账户的 CashFlow 汇总（流入 - 流出）
 * - 银行余额：用户输入的银行对账单余额
 * - 差额：账面余额 - 银行余额
 *
 * 未匹配项：
 * - 系统有记录但银行未确认（financeTriggered = false）
 * - 银行有记录但系统未录入（需手工导入，此处检测为 0）
 */
data class ReconciliationReport(
    val bankAccountId: Long,
    val bankAccountName: String,
    val bookBalance: Double,           // 账面余额（系统 CashFlow 汇总）
    val bankStatementBalance: Double,   // 银行对账单余额（用户输入）
    val difference: Double,             // 差额 = 账面 - 银行
    val totalInflow: Double,           // 账面总流入
    val totalOutflow: Double,          // 账面总流出
    val unmatchedInflows: List<UnmatchedCashFlow>,  // 未确认流入
    val unmatchedOutflows: List<UnmatchedCashFlow>, // 未确认流出
    val reconciledAt: Long              // 对账时间
)

/**
 * 未匹配的资金流水（系统有但银行可能没有）
 */
data class UnmatchedCashFlow(
    val id: Long,
    val type: String,
    val amount: Double,
    val counterparty: String?,   // 对方账户名称
    val transactionDate: Long,
    val description: String?,
    val financeTriggered: Boolean  // 是否已凭证化
)

// ==================== 银行对账 Use Case ====================

/**
 * 银行对账 — 对应 Desktop 银行对账功能
 *
 * 流程：
 * 1. 查询指定银行账户的所有 CashFlow
 * 2. 计算账面余额（流入 - 流出）
 * 3. 用户输入银行对账单余额
 * 4. 对比找出未确认项目（financeTriggered = false）
 *
 * 未匹配项说明：
 * - financeTriggered = false：已录入系统但尚未"确认"（尚未生成凭证）
 * - 银行有但系统无：需手工补录（此处无法自动发现）
 */
class BankReconciliationUseCase @Inject constructor(
    private val bankAccountRepo: BankAccountRepository,
    private val cashFlowRepo: CashFlowRepository
) {
    /**
     * 生成对账报告
     *
     * @param bankAccountId 银行账户ID
     * @param bankStatementBalance 银行对账单余额（用户从银行获取）
     */
    suspend operator fun invoke(
        bankAccountId: Long,
        bankStatementBalance: Double
    ): ReconciliationReport {
        val bankAccount = bankAccountRepo.getById(bankAccountId)
            ?: throw IllegalArgumentException("BankAccount not found: id=$bankAccountId")

        val allCashFlows = cashFlowRepo.getAll().first()
        val accountCashFlows = allCashFlows.filter {
            it.payerAccountId == bankAccountId || it.payeeAccountId == bankAccountId
        }

        // 计算账面余额
        val totalInflow = accountCashFlows
            .filter { it.payeeAccountId == bankAccountId }
            .sumOf { it.amount }
        val totalOutflow = accountCashFlows
            .filter { it.payerAccountId == bankAccountId }
            .sumOf { it.amount }
        val bookBalance = totalInflow - totalOutflow

        // 未匹配项：未凭证化（financeTriggered = false）的流水
        val unmatchedInflows = accountCashFlows
            .filter { it.payeeAccountId == bankAccountId && !it.financeTriggered }
            .map { it.toUnmatched() }

        val unmatchedOutflows = accountCashFlows
            .filter { it.payerAccountId == bankAccountId && !it.financeTriggered }
            .map { it.toUnmatched() }

        return ReconciliationReport(
            bankAccountId = bankAccountId,
            bankAccountName = bankAccount.accountInfo?.let {
                "${it.bankName ?: ""} ${it.accountNumber ?: ""}"
            } ?: "账户 #$bankAccountId",
            bookBalance = bookBalance,
            bankStatementBalance = bankStatementBalance,
            difference = bookBalance - bankStatementBalance,
            totalInflow = totalInflow,
            totalOutflow = totalOutflow,
            unmatchedInflows = unmatchedInflows,
            unmatchedOutflows = unmatchedOutflows,
            reconciledAt = System.currentTimeMillis()
        )
    }

    /**
     * 获取银行账户的简要对账摘要（不输入银行余额）
     */
    suspend fun getSummary(bankAccountId: Long): BankAccountReconciliationSummary {
        val bankAccount = bankAccountRepo.getById(bankAccountId)
            ?: throw IllegalArgumentException("BankAccount not found: id=$bankAccountId")

        val allCashFlows = cashFlowRepo.getAll().first()
        val accountCashFlows = allCashFlows.filter {
            it.payerAccountId == bankAccountId || it.payeeAccountId == bankAccountId
        }

        val totalInflow = accountCashFlows.filter { it.payeeAccountId == bankAccountId }.sumOf { it.amount }
        val totalOutflow = accountCashFlows.filter { it.payerAccountId == bankAccountId }.sumOf { it.amount }
        val confirmedBalance = totalInflow - totalOutflow

        val unconfirmedCount = accountCashFlows.count { !it.financeTriggered }

        return BankAccountReconciliationSummary(
            bankAccountId = bankAccountId,
            bankAccountName = bankAccount.accountInfo?.let {
                "${it.bankName ?: ""} ${it.accountNumber ?: ""}"
            } ?: "账户 #$bankAccountId",
            totalInflow = totalInflow,
            totalOutflow = totalOutflow,
            confirmedBalance = confirmedBalance,
            unconfirmedCount = unconfirmedCount
        )
    }

    private fun CashFlow.toUnmatched() = UnmatchedCashFlow(
        id = id,
        type = type?.displayName ?: "未知",
        amount = amount,
        counterparty = when {
            payerAccountId != null -> payeeAccountName
            payeeAccountId != null -> payerAccountName
            else -> null
        },
        transactionDate = transactionDate ?: timestamp,
        description = description,
        financeTriggered = financeTriggered
    )
}

/**
 * 银行账户对账摘要（无需输入银行余额）
 */
data class BankAccountReconciliationSummary(
    val bankAccountId: Long,
    val bankAccountName: String,
    val totalInflow: Double,
    val totalOutflow: Double,
    val confirmedBalance: Double,   // 已确认余额
    val unconfirmedCount: Int       // 未确认流水笔数
)
