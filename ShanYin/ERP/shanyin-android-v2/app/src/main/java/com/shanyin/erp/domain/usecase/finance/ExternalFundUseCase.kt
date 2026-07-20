package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.data.local.dao.FinancialJournalDao
import com.shanyin.erp.data.local.entity.FinancialJournalEntity
import com.shanyin.erp.domain.model.RefType
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.usecase.finance.engine.AccountResolver
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 外部出入金 — 对应 Desktop external_fund_action
 *
 * 记录非业务类的外部出入金操作：
 * - EXT-IN (入金): 借: 银行存款, 贷: <fund_type>
 * - EXT-OUT (出金): 借: <fund_type>,  贷: 银行存款
 *
 * fund_type 格式: "科目名称 (说明)"，取第一部分作为 GL 科目名
 * 例如: "实收资本 (股东注资/增资)" → 科目 "实收资本"
 *
 * 凭证号格式: EXT-IN-{uuid} 或 EXT-OUT-{uuid}
 */
@Singleton
class ExternalFundUseCase @Inject constructor(
    private val journalDao: FinancialJournalDao,
    private val bankAccountRepo: BankAccountRepository,
    private val accountResolver: AccountResolver
) {
    data class ExternalFundRequest(
        val accountId: Long,           // 银行账户ID
        val fundType: String,         // 资金类型 "实收资本 (股东注资/增资)" 等
        val amount: Double,
        val externalEntity: String,   // 外部实体名称
        val description: String? = null,
        val isInbound: Boolean,        // true=入金, false=出金
        val transactionDate: Long = System.currentTimeMillis()
    )

    suspend operator fun invoke(request: ExternalFundRequest): String {
        if (request.amount <= 0) {
            throw IllegalArgumentException("金额必须大于 0")
        }

        val bankAccount = bankAccountRepo.getById(request.accountId)
            ?: throw IllegalArgumentException("银行账户不存在: id=${request.accountId}")

        // 凭证号: EXT-IN-{uuid} 或 EXT-OUT-{uuid}
        val prefix = if (request.isInbound) "EXT-IN-" else "EXT-OUT-"
        val voucherNo = "$prefix${UUID.randomUUID().toString().take(6).uppercase()}"

        // 从 fund_type 提取 GL 科目名 (取第一部分，分隔符 " (")
        val lv1Name = request.fundType.split(" (").first()

        // 银行存款 GL 科目
        val cashAccountId = accountResolver.resolveId("银行存款")
            ?: throw IllegalStateException("Finance account '银行存款' not found. Please seed finance_accounts table.")

        // 资金类型 GL 科目
        val fundAccountId = accountResolver.resolveId(lv1Name)
            ?: throw IllegalStateException("Finance account '$lv1Name' not found. Please seed finance_accounts table.")

        if (request.isInbound) {
            // EXT-IN: 借: 银行存款, 贷: <fund_type>
            val debitEntry = FinancialJournalEntity(
                voucherNo = voucherNo,
                accountId = cashAccountId,
                debit = request.amount,
                credit = 0.0,
                summary = "外部入金(${lv1Name}): ${request.externalEntity}",
                refType = RefType.EXTERNAL_FUND.name,
                refId = 0,
                refVcId = null,
                transactionDate = request.transactionDate
            )
            val creditEntry = FinancialJournalEntity(
                voucherNo = voucherNo,
                accountId = fundAccountId,
                debit = 0.0,
                credit = request.amount,
                summary = "资金注入: ${request.description ?: request.externalEntity}",
                refType = RefType.EXTERNAL_FUND.name,
                refId = 0,
                refVcId = null,
                transactionDate = request.transactionDate
            )
            journalDao.insert(debitEntry)
            journalDao.insert(creditEntry)
        } else {
            // EXT-OUT: 借: <fund_type>, 贷: 银行存款
            val debitEntry = FinancialJournalEntity(
                voucherNo = voucherNo,
                accountId = fundAccountId,
                debit = request.amount,
                credit = 0.0,
                summary = "非运营支出(${lv1Name}): ${request.externalEntity}",
                refType = RefType.EXTERNAL_FUND.name,
                refId = 0,
                refVcId = null,
                transactionDate = request.transactionDate
            )
            val creditEntry = FinancialJournalEntity(
                voucherNo = voucherNo,
                accountId = cashAccountId,
                debit = 0.0,
                credit = request.amount,
                summary = "外部出金: ${request.description ?: request.externalEntity}",
                refType = RefType.EXTERNAL_FUND.name,
                refId = 0,
                refVcId = null,
                transactionDate = request.transactionDate
            )
            journalDao.insert(debitEntry)
            journalDao.insert(creditEntry)
        }

        return voucherNo
    }
}