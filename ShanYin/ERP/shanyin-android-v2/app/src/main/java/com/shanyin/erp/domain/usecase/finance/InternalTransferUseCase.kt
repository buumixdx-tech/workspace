package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.data.local.dao.FinancialJournalDao
import com.shanyin.erp.data.local.entity.FinancialJournalEntity
import com.shanyin.erp.domain.model.RefType
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import com.shanyin.erp.domain.usecase.finance.engine.AccountResolver
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 内部资金划拨 — 对应 Desktop internal_transfer_action
 *
 * 将资金从一个银行账户划拨到另一个银行账户，生成复式记账凭证：
 * - 借: 银行存款（目标账户）
 * - 贷: 银行存款（源账户）
 *
 * 凭证号格式: TRF-{uuid}（与 Desktop 保持一致）
 */
@Singleton
class InternalTransferUseCase @Inject constructor(
    private val journalDao: FinancialJournalDao,
    private val bankAccountRepo: BankAccountRepository,
    private val accountResolver: AccountResolver
) {
    data class TransferRequest(
        val fromBankAccountId: Long,
        val toBankAccountId: Long,
        val amount: Double,
        val description: String?,
        val transactionDate: Long = System.currentTimeMillis()
    )

    suspend operator fun invoke(request: TransferRequest): String {
        if (request.fromBankAccountId == request.toBankAccountId) {
            throw IllegalArgumentException("源账户与目标账户不能相同")
        }
        if (request.amount <= 0) {
            throw IllegalArgumentException("划拨金额必须大于 0")
        }

        val fromAccount = bankAccountRepo.getById(request.fromBankAccountId)
            ?: throw IllegalArgumentException("源银行账户不存在: id=${request.fromBankAccountId}")
        val toAccount = bankAccountRepo.getById(request.toBankAccountId)
            ?: throw IllegalArgumentException("目标银行账户不存在: id=${request.toBankAccountId}")

        // 凭证号: TRF-{6位UUID}
        val voucherNo = "TRF-${UUID.randomUUID().toString().take(6).uppercase()}"
        val summary = "内转: ${request.description ?: "资金调拨"}"

        // 借方: 银行存款（目标账户）
        val toAccountId = accountResolver.resolveId("银行存款")
            ?: throw IllegalStateException("Finance account '银行存款' not found. Please seed finance_accounts table.")
        // 贷方: 银行存款（源账户）
        val fromAccountId = accountResolver.resolveId("银行存款")
            ?: throw IllegalStateException("Finance account '银行存款' not found. Please seed finance_accounts table.")

        // 借方分录（目标账户增加）
        val debitEntry = FinancialJournalEntity(
            voucherNo = voucherNo,
            accountId = toAccountId,
            debit = request.amount,
            credit = 0.0,
            summary = summary,
            refType = RefType.INTERNAL_TRANSFER.name,
            refId = 0,
            refVcId = null,
            transactionDate = request.transactionDate
        )

        // 贷方分录（源账户减少）
        val creditEntry = FinancialJournalEntity(
            voucherNo = voucherNo,
            accountId = fromAccountId,
            debit = 0.0,
            credit = request.amount,
            summary = summary,
            refType = RefType.INTERNAL_TRANSFER.name,
            refId = 0,
            refVcId = null,
            transactionDate = request.transactionDate
        )

        journalDao.insert(debitEntry)
        journalDao.insert(creditEntry)

        return voucherNo
    }
}
