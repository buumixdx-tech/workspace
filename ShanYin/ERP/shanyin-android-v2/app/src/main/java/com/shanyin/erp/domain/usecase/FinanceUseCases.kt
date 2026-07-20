package com.shanyin.erp.domain.usecase

import com.google.gson.Gson
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.BankAccountRepository
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.FinanceAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ProcessCashFlowFinanceUseCase
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import java.util.UUID
import javax.inject.Inject

// 从银行账户 JSON 中提取名称的辅助函数
private fun extractBankAccountNameFromJson(accountInfoJson: String?): String? {
    if (accountInfoJson.isNullOrBlank()) return null
    return try {
        val map = Gson().fromJson(accountInfoJson, Map::class.java)
        // 支持中英文键：银行名称/bankName, 银行账号/账号/accountNumber/accountNo
        val bankName = (map["银行名称"] as? String ?: map["bankName"] as? String ?: "").trim()
        val accountNumber = (map["银行账号"] as? String ?: map["账号"] as? String ?: map["accountNumber"] as? String ?: map["accountNo"] as? String ?: "").trim()
        if (bankName.isNotEmpty() || accountNumber.isNotEmpty()) "$bankName $accountNumber".trim() else null
    } catch (e: Exception) {
        null
    }
}

// ==================== Finance Account Use Cases ====================

class GetAllFinanceAccountsUseCase @Inject constructor(
    private val repository: FinanceAccountRepository
) {
    operator fun invoke(): Flow<List<FinanceAccount>> = repository.getAll()
}

class GetFinanceAccountByIdUseCase @Inject constructor(
    private val repository: FinanceAccountRepository
) {
    suspend operator fun invoke(id: Long): FinanceAccount? = repository.getById(id)
}

class GetFinanceAccountsByCategoryUseCase @Inject constructor(
    private val repository: FinanceAccountRepository
) {
    operator fun invoke(category: FinanceCategory): Flow<List<FinanceAccount>> =
        repository.getByCategory(category)
}

class SaveFinanceAccountUseCase @Inject constructor(
    private val repository: FinanceAccountRepository
) {
    suspend operator fun invoke(account: FinanceAccount): Long {
        return if (account.id == 0L) {
            repository.insert(account)
        } else {
            repository.update(account)
            account.id
        }
    }
}

class DeleteFinanceAccountUseCase @Inject constructor(
    private val repository: FinanceAccountRepository
) {
    suspend operator fun invoke(account: FinanceAccount) = repository.delete(account)
}

// ==================== Cash Flow Use Cases ====================

class GetAllCashFlowsUseCase @Inject constructor(
    private val repository: CashFlowRepository
) {
    operator fun invoke(): Flow<List<CashFlow>> = repository.getAll()
}

class GetCashFlowByIdUseCase @Inject constructor(
    private val repository: CashFlowRepository
) {
    suspend operator fun invoke(id: Long): CashFlow? = repository.getById(id)
}

class GetCashFlowsByVcUseCase @Inject constructor(
    private val repository: CashFlowRepository
) {
    operator fun invoke(vcId: Long): Flow<List<CashFlow>> = repository.getByVcId(vcId)
}

class GetCashFlowsByTypeUseCase @Inject constructor(
    private val repository: CashFlowRepository
) {
    operator fun invoke(type: CashFlowType): Flow<List<CashFlow>> = repository.getByType(type)
}

class GetCashFlowsByAccountUseCase @Inject constructor(
    private val repository: CashFlowRepository
) {
    operator fun invoke(accountId: Long): Flow<List<CashFlow>> = repository.getByAccountId(accountId)
}

class CreateCashFlowUseCase @Inject constructor(
    private val repository: CashFlowRepository,
    private val vcRepository: VirtualContractRepository,
    private val bankAccountRepository: BankAccountRepository,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val triggerFinance: TriggerCashFlowFinanceUseCase
) {
    companion object {
        /** Desktop VALID_CASH_FLOW_TYPES */
        private val VALID_CASH_FLOW_TYPES = setOf(
            CashFlowType.PREPAYMENT,
            CashFlowType.PERFORMANCE,
            CashFlowType.DEPOSIT,
            CashFlowType.DEPOSIT_REFUND,
            CashFlowType.REFUND,
            CashFlowType.OFFSET_INFLOW,
            CashFlowType.OFFSET_OUTFLOW,
            CashFlowType.DEPOSIT_OFFSET_IN,
            CashFlowType.PENALTY
        )

        private val VC_STATUS_BLOCKED = setOf(VCStatus.TERMINATED, VCStatus.CANCELLED)
    }

    /**
     * 创建资金流水
     *
     * 对标 Desktop create_cash_flow_action():
     * 1. 校验 VC 状态、CashFlowType、银行账户
     * 2. 插入 CashFlow 记录
     * 3. 触发 VC 状态自动机（押金处理 + cashStatus 重算）
     * 4. 自动触发凭证化（生成 FinancialJournal + CashFlowLedger + financeTriggered=True）
     */
    suspend operator fun invoke(cashFlow: CashFlow): Long {
        // ===== 校验 =====
        cashFlow.type ?: throw IllegalArgumentException("资金流水类型不能为空")

        // 1. 校验 CashFlowType 合法
        if (cashFlow.type !in VALID_CASH_FLOW_TYPES) {
            throw IllegalArgumentException("不支持的资金流水类型: ${cashFlow.type?.displayName}")
        }

        // 2. 校验 VC 存在且状态允许
        cashFlow.virtualContractId?.let { vcId ->
            val vc = vcRepository.getById(vcId)
                ?: throw IllegalArgumentException("虚拟合同不存在: id=$vcId")

            if (vc.status in VC_STATUS_BLOCKED) {
                throw IllegalStateException("合同状态不允许录入资金流水: ${vc.status.displayName}")
            }
            if (vc.cashStatus == CashStatus.COMPLETED) {
                throw IllegalStateException("合同资金状态已结清，无法录入资金流水")
            }
        }

        // 3. 校验银行账户存在，并提取账户名称（写入 cash_flows 表供 UI 直接显示）
        // 注意：如果 domain accountInfo 解析失败（为 null），则通过 getRawAccountInfo 直接从 DAO 获取 JSON 再解析
        val payerAccount = cashFlow.payerAccountId?.let { id ->
            bankAccountRepository.getById(id)
                ?: throw IllegalArgumentException("付款银行账户不存在: id=$id")
        }
        val payeeAccount = cashFlow.payeeAccountId?.let { id ->
            bankAccountRepository.getById(id)
                ?: throw IllegalArgumentException("收款银行账户不存在: id=$id")
        }
        // 优先从 domain.accountInfo 提取，失败则用原始 JSON
        val payerAccountName = payerAccount?.accountInfo
            ?.let { info ->
                "${info.bankName ?: ""} ${info.accountNumber ?: ""}".trim().ifEmpty { null }
            }
            ?: cashFlow.payerAccountId?.let { id ->
                bankAccountRepository.getRawAccountInfo(id)?.let { rawJson ->
                    extractBankAccountNameFromJson(rawJson)
                }
            }
        val payeeAccountName = payeeAccount?.accountInfo
            ?.let { info ->
                "${info.bankName ?: ""} ${info.accountNumber ?: ""}".trim().ifEmpty { null }
            }
            ?: cashFlow.payeeAccountId?.let { id ->
                bankAccountRepository.getRawAccountInfo(id)?.let { rawJson ->
                    extractBankAccountNameFromJson(rawJson)
                }
            }

        // ===== 插入 =====
        val id = repository.insert(
            cashFlow.copy(
                payerAccountName = payerAccountName,
                payeeAccountName = payeeAccountName
            )
        )

        // 触发 VC 状态自动机：资金流变更 → 押金重定向 + cashStatus 重算
        // 注意：状态机失败不影响资金流水创建（对标 Desktop 行为）
        cashFlow.virtualContractId?.let { vcId ->
            try {
                val cfWithId = cashFlow.copy(id = id)
                stateMachine.onCashFlowChanged(vcId, cfWithId)
            } catch (e: Exception) {
                // 状态机失败不影响主流程，仅记录日志
            }
        }

        // 自动触发凭证化（对标 Desktop finance_module(cash_flow_id=...) 同步调用）
        try {
            triggerFinance(id)
        } catch (e: Exception) {
            // 凭证化失败不影响主流程，仅记录日志
            // （financeTriggered=False，用户可稍后重试）
        }
        return id
    }
}

class UpdateCashFlowUseCase @Inject constructor(
    private val repository: CashFlowRepository,
    private val vcRepository: VirtualContractRepository,
    private val bankAccountRepository: BankAccountRepository,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val triggerFinance: TriggerCashFlowFinanceUseCase
) {
    companion object {
        private val VALID_CASH_FLOW_TYPES = setOf(
            CashFlowType.PREPAYMENT,
            CashFlowType.PERFORMANCE,
            CashFlowType.DEPOSIT,
            CashFlowType.DEPOSIT_REFUND,
            CashFlowType.REFUND,
            CashFlowType.OFFSET_INFLOW,
            CashFlowType.OFFSET_OUTFLOW,
            CashFlowType.DEPOSIT_OFFSET_IN,
            CashFlowType.PENALTY
        )
        private val VC_STATUS_BLOCKED = setOf(VCStatus.TERMINATED, VCStatus.CANCELLED)
    }

    /**
     * 更新资金流水 — 对标 Desktop create_cash_flow_action() 的修改路径
     */
    suspend operator fun invoke(cashFlow: CashFlow) {
        // ===== 校验 =====
        cashFlow.type ?: throw IllegalArgumentException("资金流水类型不能为空")

        if (cashFlow.type !in VALID_CASH_FLOW_TYPES) {
            throw IllegalArgumentException("不支持的资金流水类型: ${cashFlow.type?.displayName}")
        }

        cashFlow.virtualContractId?.let { vcId ->
            val vc = vcRepository.getById(vcId)
                ?: throw IllegalArgumentException("虚拟合同不存在: id=$vcId")

            if (vc.status in VC_STATUS_BLOCKED) {
                throw IllegalStateException("合同状态不允许修改资金流水: ${vc.status.displayName}")
            }
            if (vc.cashStatus == CashStatus.COMPLETED) {
                throw IllegalStateException("合同资金状态已结清，无法修改资金流水")
            }
        }

        cashFlow.payerAccountId?.let { id ->
            if (bankAccountRepository.getById(id) == null) {
                throw IllegalArgumentException("付款银行账户不存在: id=$id")
            }
        }
        cashFlow.payeeAccountId?.let { id ->
            if (bankAccountRepository.getById(id) == null) {
                throw IllegalArgumentException("收款银行账户不存在: id=$id")
            }
        }

        // 提取账户名称并更新
        val payerAccountName = cashFlow.payerAccountId?.let { id ->
            bankAccountRepository.getById(id)?.accountInfo
                ?.let { "${it.bankName ?: ""} ${it.accountNumber ?: ""}".trim().ifEmpty { null } }
                ?: bankAccountRepository.getRawAccountInfo(id)?.let { extractBankAccountNameFromJson(it) }
        }
        val payeeAccountName = cashFlow.payeeAccountId?.let { id ->
            bankAccountRepository.getById(id)?.accountInfo
                ?.let { "${it.bankName ?: ""} ${it.accountNumber ?: ""}".trim().ifEmpty { null } }
                ?: bankAccountRepository.getRawAccountInfo(id)?.let { extractBankAccountNameFromJson(it) }
        }

        // ===== 更新 =====
        repository.update(cashFlow.copy(
            payerAccountName = payerAccountName,
            payeeAccountName = payeeAccountName
        ))

        // 触发 VC 状态自动机
        cashFlow.virtualContractId?.let { vcId ->
            stateMachine.onCashFlowChanged(vcId, cashFlow)
        }

        // 自动触发凭证化
        if (!cashFlow.financeTriggered) {
            try {
                triggerFinance(cashFlow.id)
            } catch (e: Exception) {
                // ignore
            }
        }
    }
}

class DeleteCashFlowUseCase @Inject constructor(
    private val repository: CashFlowRepository
) {
    suspend operator fun invoke(cashFlow: CashFlow) = repository.delete(cashFlow)
}

class TriggerCashFlowFinanceUseCase @Inject constructor(
    private val repository: CashFlowRepository,
    private val processFinance: ProcessCashFlowFinanceUseCase
) {
    /**
     * 将资金流水凭证化
     *
     * 对应 Desktop: 点击"确认"按钮 → process_cash_flow_finance()
     * - 生成 FinancialJournal 复式记账分录（借贷平衡）
     * - 写入 CashFlowLedger（资金流向分类）
     * - 标记 financeTriggered=True
     */
    suspend operator fun invoke(cashFlowId: Long): Long {
        return processFinance(cashFlowId)
    }
}

// ==================== Financial Journal (Double Entry) Use Cases ====================

class GetAllJournalEntriesUseCase @Inject constructor(
    private val repository: FinancialJournalRepository
) {
    operator fun invoke(): Flow<List<FinancialJournalEntry>> = repository.getAll()
}

class GetJournalEntryByIdUseCase @Inject constructor(
    private val repository: FinancialJournalRepository
) {
    suspend operator fun invoke(id: Long): FinancialJournalEntry? = repository.getById(id)
}

class GetJournalEntriesByVcUseCase @Inject constructor(
    private val repository: FinancialJournalRepository
) {
    operator fun invoke(vcId: Long): Flow<List<FinancialJournalEntry>> = repository.getByVcId(vcId)
}

class GetJournalEntriesByVoucherUseCase @Inject constructor(
    private val repository: FinancialJournalRepository
) {
    operator fun invoke(voucherNo: String): Flow<List<FinancialJournalEntry>> = repository.getByVoucherNo(voucherNo)
}

/**
 * Create a double-entry voucher (复式记账凭证)
 * In double-entry accounting, every transaction has equal debits and credits
 *
 * 凭证号格式: JZ-YYYYMM-NNNN（如 JZ-202603-0001）
 * - JZ: 记账凭证前缀
 * - YYYYMM: 交易年月
 * - NNNN: 当月顺序号（4位，不足补0）
 */
class CreateDoubleEntryVoucherUseCase @Inject constructor(
    private val repository: FinancialJournalRepository
) {
    suspend operator fun invoke(
        entries: List<FinancialJournalEntry>,
        transactionDate: Long = System.currentTimeMillis()
    ): String {
        // Validate that total debits equal total credits
        val totalDebit = entries.sumOf { it.debit }
        val totalCredit = entries.sumOf { it.credit }

        if (totalDebit != totalCredit) {
            throw IllegalArgumentException("Double-entry accounting requires debits equals credits: Debit=$totalDebit, Credit=$totalCredit")
        }

        // Generate sequential voucher number: JZ-YYYYMM-NNNN
        val calendar = java.util.Calendar.getInstance().apply { timeInMillis = transactionDate }
        val year = calendar.get(java.util.Calendar.YEAR)
        val month = calendar.get(java.util.Calendar.MONTH) + 1
        val prefix = String.format("JZ-%04d%02d-", year, month)
        val prefixLength = prefix.length  // "JZ-202603-" = 11 chars

        val maxSeq = repository.getMaxSeqForPrefix(prefix, prefixLength) ?: 0
        val voucherNo = "$prefix${String.format("%04d", maxSeq + 1)}"

        // Add voucher number to all entries
        val entriesWithVoucher = entries.map { it.copy(voucherNo = voucherNo, transactionDate = transactionDate) }

        // Insert all entries
        repository.insertAll(entriesWithVoucher)

        return voucherNo
    }
}

class DeleteJournalEntryUseCase @Inject constructor(
    private val repository: FinancialJournalRepository
) {
    suspend operator fun invoke(entry: FinancialJournalEntry) = repository.delete(entry)
}

// ==================== Financial Queries Use Cases ====================

class GetAccountBalanceUseCase @Inject constructor(
    private val journalRepository: FinancialJournalRepository
) {
    suspend operator fun invoke(accountId: Long): Double {
        val entries = journalRepository.getAll().first()
        val accountEntries = entries.filter { it.accountId == accountId }
        val totalDebit = accountEntries.sumOf { it.debit }
        val totalCredit = accountEntries.sumOf { it.credit }
        return totalDebit - totalCredit
    }
}

class GetMonthlySummaryUseCase @Inject constructor(
    private val journalRepository: FinancialJournalRepository,
    private val cashFlowRepository: CashFlowRepository
) {
    suspend operator fun invoke(year: Int, month: Int): MonthlyReport {
        val startOfMonth = getStartOfMonth(year, month)
        val endOfMonth = getEndOfMonth(year, month)

        val allEntries = journalRepository.getAll().first()
        val monthEntries = allEntries.filter {
            it.transactionDate in startOfMonth..endOfMonth
        }

        val totalRevenue = monthEntries.filter { it.credit > 0 }.sumOf { it.credit }
        val totalExpense = monthEntries.filter { it.debit > 0 }.sumOf { it.debit }

        val allCashFlows = cashFlowRepository.getAll().first()
        val monthCashFlows = allCashFlows.filter {
            (it.transactionDate ?: 0) in startOfMonth..endOfMonth
        }

        val cashInflow = monthCashFlows.sumOf { it.amount }
        val cashOutflow = 0.0 // Would need direction info

        return MonthlyReport(
            year = year,
            month = month,
            totalRevenue = totalRevenue,
            totalExpense = totalExpense,
            netProfit = totalRevenue - totalExpense,
            cashInflow = cashInflow,
            cashOutflow = cashOutflow,
            netCashFlow = cashInflow - cashOutflow
        )
    }

    private fun getStartOfMonth(year: Int, month: Int): Long {
        val calendar = java.util.Calendar.getInstance()
        calendar.set(year, month - 1, 1, 0, 0, 0)
        calendar.set(java.util.Calendar.MILLISECOND, 0)
        return calendar.timeInMillis
    }

    private fun getEndOfMonth(year: Int, month: Int): Long {
        val calendar = java.util.Calendar.getInstance()
        calendar.set(year, month - 1, 1, 23, 59, 59)
        calendar.set(java.util.Calendar.MILLISECOND, 999)
        calendar.set(java.util.Calendar.DAY_OF_MONTH, calendar.getActualMaximum(java.util.Calendar.DAY_OF_MONTH))
        return calendar.timeInMillis
    }
}

// ==================== VC Payment Progress Use Cases ====================

/**
 * VC 货款进度数据
 */
data class VcPaymentProgress(
    val isReturn: Boolean,
    val goods: VcGoodsProgress,
    val deposit: VcDepositProgress,
    val paymentTerms: PaymentTermsProgress
)

data class VcGoodsProgress(
    val total: Double,          // 合同总额
    val paid: Double,          // 已付总额（含冲抵）
    val balance: Double,        // 剩余待付
    val appliedOffsets: Double, // 已确认冲抵金额
    val poolBalance: Double,   // 冲抵池可用余额
    val netPayable: Double,     // 扣除冲抵后的应付
    val label: String,
    val paidLabel: String,
    val balanceLabel: String
)

data class VcDepositProgress(
    val should: Double,        // 应收押金
    val received: Double,       // 已收押金
    val remaining: Double       // 待收押金
)

data class PaymentTermsProgress(
    val prepaymentRatio: Double,  // 预付比例
    val balancePeriod: String?,   // 账期
    val startTrigger: String?     // 起算点
)

/**
 * 获取 VC 货款和押金进度
 * 对应 Desktop calculate_cashflow_progress()
 */
class GetVcPaymentProgressUseCase @Inject constructor(
    private val vcRepo: VirtualContractRepository,
    private val cashFlowRepo: CashFlowRepository,
    private val journalRepo: FinancialJournalRepository
) {
    suspend operator fun invoke(vcId: Long): VcPaymentProgress? {
        val vc = vcRepo.getById(vcId) ?: return null
        val cashFlows = cashFlowRepo.getByVcId(vcId).first()

        // 查询关联退货 VC（用于押金计算）
        val returnVcs = vcRepo.getByRelatedVcId(vcId).first()

        // 计算冲抵池余额
        val poolBalance = calculatePoolBalance(vc)

        val isReturn = vc.type == VCType.RETURN

        val goods = if (isReturn) {
            // 退货 VC：货款退款进度
            val totalAmount = vc.depositInfo.totalAmount
            val paidRefund = cashFlows
                .filter { it.type == CashFlowType.REFUND }
                .sumOf { it.amount }
            VcGoodsProgress(
                total = totalAmount,
                paid = paidRefund,
                balance = maxOf(0.0, totalAmount - paidRefund),
                appliedOffsets = 0.0,
                poolBalance = 0.0,
                netPayable = 0.0,
                label = "应退货款总计",
                paidLabel = "已退货款",
                balanceLabel = "待退货款余额"
            )
        } else {
            // 常规 VC：货款支付进度
            val totalAmount = vc.depositInfo.totalAmount
            val appliedOffsets = cashFlows
                .filter { it.type == CashFlowType.OFFSET_OUTFLOW }
                .sumOf { it.amount }
            val cashPaid = cashFlows
                .filter { it.type in listOf(CashFlowType.PREPAYMENT, CashFlowType.PERFORMANCE, CashFlowType.REFUND) }
                .sumOf { it.amount }
            val paid = appliedOffsets + cashPaid
            VcGoodsProgress(
                total = totalAmount,
                paid = paid,
                balance = maxOf(0.0, totalAmount - paid),
                appliedOffsets = appliedOffsets,
                poolBalance = poolBalance,
                netPayable = maxOf(0.0, totalAmount - appliedOffsets),
                label = "合同总额",
                paidLabel = "累计已付/冲抵",
                balanceLabel = "剩余待付"
            )
        }

        // 押金进度
        val deposit = if (isReturn) {
            // 退货VC：遍历所有元素求和（ReturnElement.depositAmount可能为null）
            val depShould = vc.elements.sumOf { elem ->
                val re = elem as? ReturnElement
                re?.depositAmount ?: 0.0
            }
            val depReceived = cashFlows
                .filter { it.type == CashFlowType.DEPOSIT_REFUND }
                .sumOf { it.amount }
            VcDepositProgress(
                should = depShould,
                received = depReceived,
                remaining = maxOf(0.0, depShould - depReceived)
            )
        } else {
            val depShould = vc.depositInfo.shouldReceive
            val depReceived = vc.depositInfo.actualDeposit
            VcDepositProgress(
                should = depShould,
                received = depReceived,
                remaining = maxOf(0.0, depShould - depReceived)
            )
        }

        // 账期信息
        val paymentTerms = PaymentTermsProgress(
            prepaymentRatio = vc.depositInfo.prepaymentRatio,
            balancePeriod = null,  // 暂未实现
            startTrigger = null    // 暂未实现
        )

        return VcPaymentProgress(
            isReturn = isReturn,
            goods = goods,
            deposit = deposit,
            paymentTerms = paymentTerms
        )
    }

    /**
     * 计算冲抵池可用余额
     * 对应 Desktop calculate_cashflow_progress() lines 386-417
     */
    private suspend fun calculatePoolBalance(vc: VirtualContract): Double {
        val accountLevel1 = when {
            vc.type in listOf(VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK, VCType.MATERIAL_PROCUREMENT) -> "预付账款-供应商"
            vc.type == VCType.MATERIAL_SUPPLY -> "预收账款-客户"
            else -> return 0.0
        }

        // 直接从 journal 计算余额（按 accountName 模糊匹配）
        val allEntries = journalRepo.getAll().first()
        val accountEntries = allEntries.filter { it.accountName?.contains(accountLevel1) == true }

        val totalDebit = accountEntries.sumOf { it.debit }
        val totalCredit = accountEntries.sumOf { it.credit }

        return when {
            vc.type == VCType.MATERIAL_SUPPLY -> maxOf(0.0, totalCredit - totalDebit)
            else -> maxOf(0.0, totalDebit - totalCredit)
        }
    }
}

/**
 * 建议资金流付款方/收款方
 * 对应 Desktop get_suggested_cashflow_parties()
 */
data class SuggestedParties(
    val payerOwnerType: String?,   // "CUSTOMER" / "SUPPLIER" / "BANK_ACCOUNT"
    val payerOwnerId: Long?,
    val payeeOwnerType: String?,
    val payeeOwnerId: Long?
)

class GetSuggestedCashflowPartiesUseCase @Inject constructor(
    private val vcRepo: VirtualContractRepository
) {
    /**
     * 根据 VC 类型和资金流类型建议付款方/收款方
     *
     * 规则（对标 Desktop get_suggested_cashflow_parties()）：
     * - 设备采购 + DEPOSIT:     payer=CUSTOMER, payee=OURSELVES (客户付押金给我们)
     * - 设备采购 + RETURN_DEPOSIT: payer=OURSELVES, payee=CUSTOMER (我们退押金给客户)
     * - 物料供应:              payer=CUSTOMER, payee=OURSELVES (客户付款给我们)
     * - 采购类 (PREPAYMENT等): payer=OURSELVES, payee=SUPPLIER (我们付款给供应商)
     * - RETURN US_TO_SUPPLIER: payer=SUPPLIER, payee=OURSELVES (供应商退款给我们)
     * - RETURN CUSTOMER_TO_US: payer=OURSELVES, payee=CUSTOMER (我们退款给客户)
     */
    suspend operator fun invoke(vcId: Long, cfType: CashFlowType): SuggestedParties {
        val vc = vcRepo.getById(vcId) ?: return SuggestedParties(null, null, null, null)

        return when {
            // 设备采购 + 押金收取：客户 -> 我们
            vc.type == VCType.EQUIPMENT_PROCUREMENT && cfType == CashFlowType.DEPOSIT -> {
                SuggestedParties("CUSTOMER", vc.businessId, "BANK_ACCOUNT", null)
            }
            // 设备采购 + 押金退还：我们 -> 客户
            vc.type == VCType.EQUIPMENT_PROCUREMENT && cfType == CashFlowType.DEPOSIT_REFUND -> {
                SuggestedParties("BANK_ACCOUNT", null, "CUSTOMER", vc.businessId)
            }
            // 物料供应：客户 -> 我们
            vc.type == VCType.MATERIAL_SUPPLY -> {
                SuggestedParties("CUSTOMER", vc.businessId, "BANK_ACCOUNT", null)
            }
            // 采购类（预付/履约/退款/冲抵）：我们 -> 供应商
            vc.type in listOf(VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK, VCType.MATERIAL_PROCUREMENT) -> {
                SuggestedParties("BANK_ACCOUNT", null, "SUPPLIER", vc.supplyChainId)
            }
            // 退货
            vc.type == VCType.RETURN -> {
                if (vc.returnDirection == ReturnDirection.US_TO_SUPPLIER) {
                    // 向供应商退货：供应商 -> 我们（供应商退款）
                    SuggestedParties("SUPPLIER", vc.supplyChainId, "BANK_ACCOUNT", null)
                } else {
                    // 客户退货：我们 -> 客户（我们退款）
                    SuggestedParties("BANK_ACCOUNT", null, "CUSTOMER", vc.businessId)
                }
            }
            else -> SuggestedParties(null, null, null, null)
        }
    }
}

/**
 * 根据 VC 状态过滤可用的资金流类型
 * 对应 Desktop show_cash_flow_page() 的 type_options 过滤逻辑
 */
class GetAvailableCashFlowTypesUseCase @Inject constructor(
    private val vcRepo: VirtualContractRepository,
    private val cashFlowRepo: CashFlowRepository
) {
    suspend operator fun invoke(vcId: Long): List<CashFlowType> {
        val vc = vcRepo.getById(vcId) ?: return CashFlowType.entries.toList()
        val cashFlows = cashFlowRepo.getByVcId(vcId).first()

        val isReturn = vc.type == VCType.RETURN
        val goods = vc.depositInfo.totalAmount
        val goodsBalance = calculateGoodsBalance(vc, cashFlows)
        val depositShould = vc.depositInfo.shouldReceive
        val depositRemaining = depositShould - vc.depositInfo.actualDeposit
        val prepaymentRatio = vc.depositInfo.prepaymentRatio

        if (isReturn) {
            // 退货 VC：只显示 REFUND 和 RETURN_DEPOSIT
            val types = mutableListOf<CashFlowType>()
            if (goodsBalance > 0.01) types.add(CashFlowType.REFUND)
            if (depositRemaining > 0.01) types.add(CashFlowType.DEPOSIT_REFUND)
            if (types.isEmpty()) return listOf(CashFlowType.REFUND, CashFlowType.DEPOSIT_REFUND)
            return types
        }

        val allTypes = mutableListOf(
            CashFlowType.PREPAYMENT,
            CashFlowType.PERFORMANCE,
            CashFlowType.DEPOSIT,
            CashFlowType.DEPOSIT_REFUND,
            CashFlowType.PENALTY
        )

        // 标的已完成时，移除 PREPAYMENT（不再需要预付）
        if (vc.subjectStatus == SubjectStatus.COMPLETED) {
            allTypes.remove(CashFlowType.PREPAYMENT)
        }

        // 无预付要求时，移除 PREPAYMENT
        if (prepaymentRatio <= 0) {
            allTypes.remove(CashFlowType.PREPAYMENT)
        }

        // 无押金要求时，移除押金相关类型
        if (depositShould <= 0) {
            allTypes.remove(CashFlowType.DEPOSIT)
            allTypes.remove(CashFlowType.DEPOSIT_REFUND)
        }

        // 货款已结清时，移除 PREPAYMENT 和 PERFORMANCE
        if (goodsBalance <= 0.01) {
            allTypes.remove(CashFlowType.PREPAYMENT)
            allTypes.remove(CashFlowType.PERFORMANCE)
        }

        // 押金已结清时，移除 DEPOSIT
        if (depositRemaining <= 0.01) {
            allTypes.remove(CashFlowType.DEPOSIT)
        }

        return allTypes
    }

    private fun calculateGoodsBalance(vc: VirtualContract, cashFlows: List<CashFlow>): Double {
        val totalAmount = vc.depositInfo.totalAmount
        if (totalAmount <= 0.01) return 0.0

        val paidGoods = cashFlows
            .filter { it.type in listOf(CashFlowType.PREPAYMENT, CashFlowType.PERFORMANCE, CashFlowType.REFUND, CashFlowType.OFFSET_OUTFLOW) }
            .sumOf { it.amount }

        return maxOf(0.0, totalAmount - paidGoods)
    }
}
