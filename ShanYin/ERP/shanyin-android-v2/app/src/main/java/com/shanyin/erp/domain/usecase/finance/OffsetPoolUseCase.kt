package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.domain.model.CashFlow
import com.shanyin.erp.domain.model.CashFlowType
import com.shanyin.erp.domain.model.VirtualContract
import com.shanyin.erp.domain.model.VCType
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.FinanceAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.TriggerCashFlowFinanceUseCase
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject

// ==================== Offset Pool（核销池） ====================

/**
 * 核销类型
 * - PRE_COLLECTION: 用客户预收款冲抵应收账款（应收收款）
 * - PREPAYMENT: 用预付供应商款核销应付账款（应付付款）
 */
enum class OffsetPoolType {
    /** 预收账款-客户 — 冲抵客户应收账款 */
    PRE_COLLECTION,
    /** 预付账款-供应商 — 核销供应商应付账款 */
    PREPAYMENT
}

/**
 * 核销池账户信息
 */
data class OffsetPoolAccount(
    val type: OffsetPoolType,
    val accountId: Long,
    val accountName: String,
    val availableBalance: Double,  // 可用余额（核销池）
    val totalBalance: Double       // 总余额
)

/**
 * 核销结果
 */
data class OffsetResult(
    val success: Boolean,
    val message: String,
    val appliedAmount: Double = 0.0,
    val remainingPoolBalance: Double = 0.0,
    val newVcActualAmount: Double = 0.0
)

/**
 * 核销历史条目
 */
data class OffsetHistoryItem(
    val vcId: Long,
    val vcType: VCType,
    val offsetAmount: Double,
    val offsetType: OffsetPoolType,
    val poolAccountName: String,
    val timestamp: Long
)

/**
 * 查询预收/预付核销池余额
 *
 * 对应 Desktop apply_offset_to_vc() 的池余额查询部分：
 * - PRE_COLLECTION（预收账款-客户）: SUM(credit) - SUM(debit) for 预收账款 account
 * - PREPAYMENT（预付账款-供应商）: SUM(debit) - SUM(credit) for 预付账款 account
 *
 * 注意：预收/预付是负债/资产科目，余额方向与普通资产相反
 */
class GetOffsetPoolUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val financeAccountRepo: FinanceAccountRepository
) {
    /**
     * 查询指定类型的核销池余额
     */
    suspend operator fun invoke(type: OffsetPoolType): OffsetPoolAccount {
        val accountName = when (type) {
            OffsetPoolType.PRE_COLLECTION -> "预收账款-客户"
            OffsetPoolType.PREPAYMENT -> "预付账款-供应商"
        }

        val account = financeAccountRepo.getByName(accountName)
        if (account == null) {
            return OffsetPoolAccount(
                type = type,
                accountId = 0,
                accountName = accountName,
                availableBalance = 0.0,
                totalBalance = 0.0
            )
        }

        val allEntries = journalRepo.getAll().first()
        val accountEntries = allEntries.filter { it.accountId == account.id }

        val totalDebit = accountEntries.sumOf { it.debit }
        val totalCredit = accountEntries.sumOf { it.credit }

        // 预收账款（负债类）：贷方余额 = 贷 - 借
        // 预付账款（资产类）：借方余额 = 借 - 贷
        val totalBalance = when (type) {
            OffsetPoolType.PRE_COLLECTION -> totalCredit - totalDebit
            OffsetPoolType.PREPAYMENT -> totalDebit - totalCredit
        }

        // 已使用核销金额：从关联的 OFFSET_CASH_FLOW journal entries 中计算
        val usedAmount = calculateUsedAmount(type, account.id)

        return OffsetPoolAccount(
            type = type,
            accountId = account.id,
            accountName = accountName,
            availableBalance = (totalBalance - usedAmount).coerceAtLeast(0.0),
            totalBalance = totalBalance.coerceAtLeast(0.0)
        )
    }

    /** 查询所有核销池 */
    suspend fun getAllPools(): List<OffsetPoolAccount> {
        return listOf(invoke(OffsetPoolType.PRE_COLLECTION), invoke(OffsetPoolType.PREPAYMENT))
    }

    private suspend fun calculateUsedAmount(type: OffsetPoolType, accountId: Long): Double {
        val allEntries = journalRepo.getAll().first()
        val offsetTypeName = when (type) {
            OffsetPoolType.PRE_COLLECTION -> "OFFSET_INFLOW"
            OffsetPoolType.PREPAYMENT -> "OFFSET_OUTFLOW"
        }

        // 从 JournalEntry.refId 关联的 CashFlow 中查询 OFFSET 类型
        // 这里简化：查所有 refType=CASH_FLOW 且 accountId 匹配的 entries
        val usedEntries = allEntries.filter {
            it.accountId == accountId && it.refType?.name == "CASH_FLOW"
        }
        return usedEntries.sumOf { it.debit + it.credit }
    }
}

/**
 * 核销操作 — 对应 Desktop apply_offset_to_vc()
 *
 * 核销流程：
 * 1. 校验核销池余额充足
 * 2. 创建 OFFSET_INFLOW / OFFSET_OUTFLOW 类型的 CashFlow
 * 3. 自动触发凭证化（ProcessCashFlowFinanceUseCase）
 * 4. 返回核销结果
 *
 * 核销语义：
 * - PRE_COLLECTION 核销（客户预付款冲抵 AR）：
 *   借：预收账款-客户（减少），贷：应收账款-客户（减少）
 *   → Mobile: 创建 OFFSET_INFLOW CashFlow（金额流入，冲抵 AR）
 *
 * - PREPAYMENT 核销（我们预付款核销 AP）：
 *   借：应付账款-设备款（减少），贷：预付账款-供应商（减少）
 *   → Mobile: 创建 OFFSET_OUTFLOW CashFlow（金额流出，核销应付）
 */
class ApplyOffsetToVcUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val financeAccountRepo: FinanceAccountRepository,
    private val cashFlowRepo: CashFlowRepository,
    private val vcRepo: VirtualContractRepository,
    private val triggerCashFlowFinance: TriggerCashFlowFinanceUseCase
) {
    /**
     * 将核销池余额应用到指定 VC
     *
     * @param vcId 目标 VC ID
     * @param offsetAmount 核销金额
     * @param type 核销类型
     * @return OffsetResult
     */
    suspend operator fun invoke(
        vcId: Long,
        offsetAmount: Double,
        type: OffsetPoolType
    ): OffsetResult {
        // 1. 校验 VC 存在
        val vc = vcRepo.getById(vcId)
            ?: return OffsetResult(success = false, message = "VC 不存在: id=$vcId")

        // 2. 查询核销池余额
        val pool = GetOffsetPoolUseCase(journalRepo, financeAccountRepo).invoke(type)
        if (pool.availableBalance < offsetAmount) {
            return OffsetResult(
                success = false,
                message = "核销池余额不足：可用 ${String.format("%.2f", pool.availableBalance)}，申请 ${String.format("%.2f", offsetAmount)}"
            )
        }

        // 3. 创建核销 CashFlow
        val cfType = when (type) {
            OffsetPoolType.PRE_COLLECTION -> CashFlowType.OFFSET_INFLOW
            OffsetPoolType.PREPAYMENT -> CashFlowType.OFFSET_OUTFLOW
        }

        val cashFlow = CashFlow(
            virtualContractId = vcId,
            type = cfType,
            amount = offsetAmount,
            transactionDate = System.currentTimeMillis(),
            description = "核销池 ${pool.accountName} 核销"
        )

        val cfId = cashFlowRepo.insert(cashFlow)

        // 4. 自动触发凭证化（生成 FinancialJournal + CashFlowLedger）
        try {
            triggerCashFlowFinance(cfId)
        } catch (e: Exception) {
            // 凭证化失败，删除已创建的 CashFlow
            cashFlowRepo.delete(cashFlow.copy(id = cfId))
            return OffsetResult(success = false, message = "凭证化失败：${e.message}")
        }

        // 5. 计算剩余余额
        val remainingBalance = pool.availableBalance - offsetAmount

        // 6. 计算 VC 的最新 actualAmount（核销后）
        val vcActualAmount = recalculateVcActualAmount(vcId)

        return OffsetResult(
            success = true,
            message = "核销成功",
            appliedAmount = offsetAmount,
            remainingPoolBalance = remainingBalance,
            newVcActualAmount = vcActualAmount
        )
    }

    /**
     * 重新计算 VC 的 actualAmount（反映核销后的净值）
     * 核销后 actualAmount 会减少（或变为负数表示预收）
     */
    private suspend fun recalculateVcActualAmount(vcId: Long): Double {
        val cashFlows = cashFlowRepo.getByVcId(vcId).first()
        // 同 VirtualContractRepositoryImpl 的 actualAmount 计算逻辑
        return cashFlows
            .filter {
                it.type in listOf(
                    CashFlowType.PREPAYMENT, CashFlowType.PERFORMANCE,
                    CashFlowType.REFUND, CashFlowType.OFFSET_OUTFLOW,
                    CashFlowType.OFFSET_INFLOW
                )
            }
            .sumOf { it.amount }
    }
}

/**
 * 查询 VC 的核销历史
 */
class GetVcOffsetHistoryUseCase @Inject constructor(
    private val cashFlowRepo: CashFlowRepository
) {
    suspend operator fun invoke(vcId: Long): List<OffsetHistoryItem> {
        val cashFlows = cashFlowRepo.getByVcId(vcId).first()
        return cashFlows
            .filter { it.type == CashFlowType.OFFSET_INFLOW || it.type == CashFlowType.OFFSET_OUTFLOW }
            .map { cf ->
                OffsetHistoryItem(
                    vcId = vcId,
                    vcType = VCType.EQUIPMENT_PROCUREMENT, // VC type需单独查
                    offsetAmount = cf.amount,
                    offsetType = when (cf.type) {
                        CashFlowType.OFFSET_INFLOW -> OffsetPoolType.PRE_COLLECTION
                        else -> OffsetPoolType.PREPAYMENT
                    },
                    poolAccountName = when (cf.type) {
                        CashFlowType.OFFSET_INFLOW -> "预收账款-客户"
                        else -> "预付账款-供应商"
                    },
                    timestamp = cf.timestamp
                )
            }
    }
}
