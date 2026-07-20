package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.data.local.dao.FinancialJournalDao
import com.shanyin.erp.data.local.entity.FinancialJournalEntity
import com.shanyin.erp.domain.model.CashFlow
import com.shanyin.erp.domain.model.CashFlowDirection
import com.shanyin.erp.domain.model.CashFlowMainCategory
import com.shanyin.erp.domain.model.CashFlowType
import com.shanyin.erp.domain.model.OwnerType
import com.shanyin.erp.domain.model.RefType
import com.shanyin.erp.domain.model.ReturnDirection
import com.shanyin.erp.domain.model.VCType
import com.shanyin.erp.domain.model.VirtualContract
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.CashFlowLedgerRepository
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.engine.AccountConfig
import com.shanyin.erp.domain.usecase.finance.engine.AccountResolver
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 资金流凭证化 — 对应 Desktop process_cash_flow_finance()
 *
 * 当 CashFlow financeTriggered=True 时调用，为该笔 CashFlow 生成 FinancialJournal 复式记账分录，
 * 并写入 CashFlowLedger 用于资金流向分类统计。
 *
 * 完整链路：
 * 1. 根据 CashFlowType 和 VC 上下文获取完整的分录组（可能含多条分录）
 * 2. 由 AccountResolver 将科目名称解析为 accountId
 * 3. 生成 FinancialJournal 分录，共用同一凭证号
 * 4. 写入 CashFlowLedger（关联到第一条分录的 journalId）
 * 5. 更新 CashFlow financeTriggered=True
 */
@Singleton
class ProcessCashFlowFinanceUseCase @Inject constructor(
    private val cashFlowRepo: CashFlowRepository,
    private val journalDao: FinancialJournalDao,
    private val ledgerRepo: CashFlowLedgerRepository,
    private val accountResolver: AccountResolver,
    private val vcRepo: VirtualContractRepository,
    private val bankAccountRepo: BankAccountRepository
) {
    /**
     * 对指定 CashFlow 生成财务凭证
     * @param cashFlowId 要凭证化的 CashFlow ID
     * @return 该笔 CashFlow 的 ID
     * @throws IllegalArgumentException 如果 CashFlow 不存在或已凭证化
     */
    suspend operator fun invoke(cashFlowId: Long): Long {
        val cf = cashFlowRepo.getById(cashFlowId)
            ?: throw IllegalArgumentException("CashFlow not found: id=$cashFlowId")

        if (cf.financeTriggered) {
            // 已凭证化，跳过（幂等）
            return cashFlowId
        }

        val cfType = cf.type
            ?: throw IllegalArgumentException("CashFlow type is null: id=$cashFlowId")

        // Step 1: 计算 isIncome（资金流入还是流出）和相关金额
        val ctx = buildFinanceContext(cf)

        // Step 2: 获取完整分录组（对标 Desktop process_cash_flow_finance 的 entries 生成）
        val entryGroup = AccountConfig.getJournalEntries(
            type = cfType,
            amount = cf.amount,
            isIncome = ctx.isIncome,
            arApAmount = ctx.arApAmount,
            preAmount = ctx.preAmount,
            cpType = ctx.cpType,
            cpId = ctx.cpId,
            bankAccountId = ctx.ourBankId,
            summary = buildSummary(cf)
        )

        if (entryGroup.entries.isEmpty()) {
            // 无有效分录，跳过
            return cashFlowId
        }

        // Step 3: 生成凭证号 JZ-YYYYMM-NNNN
        val transactionDate = cf.transactionDate ?: cf.timestamp
        val voucherNo = generateVoucherNo(transactionDate)

        // Step 4: 解析所有分录的 accountId
        val resolvedEntries = entryGroup.entries.map { entry ->
            val accountId = accountResolver.resolveId(entry.account)
                ?: throw IllegalStateException(
                    "Finance account not found: ${entry.account}. " +
                    "Please seed finance_accounts table."
                )
            entry to accountId
        }

        // Step 5: 写入 FinancialJournal（所有分录共用同一凭证号）
        val (firstEntry, firstAccountId) = resolvedEntries.first()
        val firstJournalId = journalDao.insert(
            FinancialJournalEntity(
                voucherNo = voucherNo,
                accountId = firstAccountId,
                debit = firstEntry.debit,
                credit = firstEntry.credit,
                summary = firstEntry.summary,
                refType = RefType.CASH_FLOW.name,
                refId = cf.id,
                refVcId = cf.virtualContractId,
                transactionDate = transactionDate
            )
        )

        // 写入其余分录
        resolvedEntries.drop(1).forEach { (entry, accountId) ->
            journalDao.insert(
                FinancialJournalEntity(
                    voucherNo = voucherNo,
                    accountId = accountId,
                    debit = entry.debit,
                    credit = entry.credit,
                    summary = entry.summary,
                    refType = RefType.CASH_FLOW.name,
                    refId = cf.id,
                    refVcId = cf.virtualContractId,
                    transactionDate = transactionDate
                )
            )
        }

        // Step 6: 写入 CashFlowLedger（关联到第一条分录的 journalId）
        val mainCategory = resolveMainCategory(cfType)
        val direction = if (entryGroup.isIncome) CashFlowDirection.INFLOW else CashFlowDirection.OUTFLOW
        val ledgerEntry = com.shanyin.erp.domain.model.CashFlowLedger(
            journalId = firstJournalId,
            mainCategory = mainCategory,
            direction = direction,
            amount = cf.amount,
            transactionDate = transactionDate
        )
        ledgerRepo.insert(ledgerEntry)

        // Step 7: 更新 CashFlow financeTriggered=True
        cashFlowRepo.update(cf.copy(financeTriggered = true))

        return cashFlowId
    }

    /**
     * 构建资金流凭证化所需的领域上下文
     * 对应 Desktop get_cashflow_finance_context() lines 575-641
     */
    private suspend fun buildFinanceContext(cf: CashFlow): FinanceContext {
        var isIncome = false
        var cpType: String? = null
        var cpId: Long? = null
        var arApAmount = 0.0
        var preAmount = 0.0
        var ourBankId: Long? = null

        val vc = cf.virtualContractId?.let { vcRepo.getById(it) }

        if (vc != null) {
            // 确定对方类型和ID
            val (type, id) = getCounterpartInfo(vc)
            cpType = type
            cpId = id

            // 确定 isIncome
            when {
                vc.type == VCType.MATERIAL_SUPPLY -> {
                    // 物料供应：客户付款给我们，资金流入
                    isIncome = true
                }
                vc.type == VCType.RETURN -> {
                    // 退货：根据 return_direction 判断资金流向
                    // US_TO_SUPPLIER: 我们退货给供应商 → 供应商退款给我们 → 资金流入 isIncome=true
                    // CUSTOMER_TO_US: 客户退货给我们 → 我们退款给客户 → 资金流出 isIncome=false
                    isIncome = vc.returnDirection == ReturnDirection.US_TO_SUPPLIER
                }
                vc.type in listOf(
                    VCType.EQUIPMENT_PROCUREMENT,
                    VCType.EQUIPMENT_STOCK,
                    VCType.MATERIAL_PROCUREMENT
                ) -> {
                    // 采购：我们付款给供应商，资金流出
                    isIncome = false
                }
            }

            // 计算 arApAmount 和 preAmount（仅对 PREPAYMENT/PERFORMANCE 有意义）
            if (cf.type == CashFlowType.PREPAYMENT || cf.type == CashFlowType.PERFORMANCE) {
                val totalAmount = vc.depositInfo.totalAmount
                if (totalAmount > 0.01) {
                    // 查询该VC此前已付款金额（不含本次）
                    val existingCfs = cashFlowRepo.getByVcId(vc.id).first()
                    val paidBefore = existingCfs
                        .filter { it.id != cf.id && it.type in listOf(
                            CashFlowType.PREPAYMENT,
                            CashFlowType.PERFORMANCE,
                            CashFlowType.OFFSET_OUTFLOW
                        ) }
                        .sumOf { it.amount }
                    val remaining = maxOf(0.0, totalAmount - paidBefore)
                    arApAmount = minOf(cf.amount, remaining)
                    preAmount = maxOf(0.0, cf.amount - remaining)
                }
            }
        }

        // 获取我方银行账户ID（根据 payer/payee 账户判断）
        val payerAccount = cf.payerAccountId?.let { bankAccountRepo.getById(it) }
        val payeeAccount = cf.payeeAccountId?.let { bankAccountRepo.getById(it) }

        // 收款方是我方（payee）→ 用 payee 账户ID；付款方是我方（payer）→ 用 payer 账户ID
        ourBankId = if (payeeAccount?.ownerType == OwnerType.OURSELVES) {
            cf.payeeAccountId
        } else if (payerAccount?.ownerType == OwnerType.OURSELVES) {
            cf.payerAccountId
        } else {
            // 降级：任选一个我方账户
            payerAccount?.takeIf { it.ownerType == OwnerType.OURSELVES }?.id
                ?: payeeAccount?.takeIf { it.ownerType == OwnerType.OURSELVES }?.id
        }

        return FinanceContext(
            isIncome = isIncome,
            cpType = cpType,
            cpId = cpId,
            arApAmount = arApAmount,
            preAmount = preAmount,
            ourBankId = ourBankId
        )
    }

    /**
     * 获取 VC 的对方信息 (counterpart type and id)
     * 对应 Desktop get_counterpart_info()
     */
    private fun getCounterpartInfo(vc: com.shanyin.erp.domain.model.VirtualContract): Pair<String?, Long?> {
        return when {
            vc.type == VCType.MATERIAL_SUPPLY -> {
                // 客户付款给我们，对方是客户
                val customerId = vc.businessId
                "CUSTOMER" to customerId
            }
            vc.type in listOf(
                VCType.EQUIPMENT_PROCUREMENT,
                VCType.EQUIPMENT_STOCK,
                VCType.MATERIAL_PROCUREMENT
            ) -> {
                // 我们付款给供应商，对方是供应商
                val supplierId = vc.supplyChainId
                "SUPPLIER" to supplierId
            }
            vc.type == VCType.RETURN -> {
                // 退货简化处理：默认视为客户退货（退款给客户）
                val customerId = vc.businessId
                "CUSTOMER" to customerId
            }
            else -> null to null
        }
    }

    /**
     * 生成凭证号: JZ-YYYYMM-NNNN
     */
    private suspend fun generateVoucherNo(transactionDate: Long): String {
        val calendar = java.util.Calendar.getInstance().apply { timeInMillis = transactionDate }
        val year = calendar.get(java.util.Calendar.YEAR)
        val month = calendar.get(java.util.Calendar.MONTH) + 1
        val prefix = String.format("JZ-%04d%02d-", year, month)
        val prefixLength = prefix.length

        val maxSeq = journalDao.getMaxSeqForPrefix(prefix, prefixLength) ?: 0
        return "$prefix${String.format("%04d", maxSeq + 1)}"
    }

    /**
     * 构建分录摘要
     */
    private fun buildSummary(cf: CashFlow): String {
        val parts = mutableListOf<String>()
        cf.type?.displayName?.let { parts.add(it) }
        cf.description?.let { parts.add(it) }
        if (cf.virtualContractId != null) {
            parts.add("VC#${cf.virtualContractId}")
        }
        return parts.joinToString(" ")
    }

    /**
     * 根据 CashFlowType 解析资金流向主分类
     */
    private fun resolveMainCategory(type: CashFlowType): CashFlowMainCategory {
        return when (type) {
            CashFlowType.OFFSET_INFLOW,
            CashFlowType.OFFSET_OUTFLOW -> CashFlowMainCategory.FINANCING
            else -> CashFlowMainCategory.OPERATING
        }
    }

    /**
     * 资金流凭证化上下文
     */
    private data class FinanceContext(
        val isIncome: Boolean,
        val cpType: String?,        // "CUSTOMER" / "SUPPLIER" / "BANK_ACCOUNT"
        val cpId: Long?,
        val arApAmount: Double,     // 应收/应付核销金额
        val preAmount: Double,      // 计入预收/预付金额
        val ourBankId: Long?        // 我方银行账户ID
    )
}
