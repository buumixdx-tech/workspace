package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.domain.model.ChannelCustomer
import com.shanyin.erp.domain.model.FinancialJournalEntry
import com.shanyin.erp.domain.model.Supplier
import com.shanyin.erp.domain.model.VirtualContract
import com.shanyin.erp.domain.repository.ChannelCustomerRepository
import com.shanyin.erp.domain.repository.FinanceAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import com.shanyin.erp.domain.repository.SupplierRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject

// ==================== AP/AR 明细账 ====================

/**
 * AP/AR 明细账条目
 */
data class ApArDetailItem(
    val date: Long,
    val voucherNo: String,
    val summary: String,
    val debit: Double,      // 借方金额（AP=应付减少，AR=应收减少）
    val credit: Double,    // 贷方金额（AP=应付增加，AR=应收增加）
    val balance: Double,    // 累计余额
    val counterpartName: String?,  // 供应商名称 / 客户名称
    val vcId: Long?,
    val refType: String?
)

/**
 * 应付账款明细账 — Desktop AP 追踪
 *
 * 查询逻辑：
 * - 从 FinancialJournal 中筛选 accountName 含"应付账款"的记录
 * - 按 refVcId 关联 VirtualContract，再从 VirtualContract.supplyChainId 查 Supplier
 * - 余额 = 累计 credit(贷方，应付增加) - 累计 debit(借方，应付减少)
 */
class GetAccountPayableDetailUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val vcRepo: VirtualContractRepository,
    private val supplierRepo: SupplierRepository,
    private val supplyChainRepo: com.shanyin.erp.domain.repository.SupplyChainRepository
) {
    suspend operator fun invoke(
        supplierId: Long? = null,
        startDate: Long? = null,
        endDate: Long? = null
    ): List<ApArDetailItem> {
        val allEntries = journalRepo.getAll().first()
        val apAccountNames = setOf("应付账款", "应付账款-设备款", "应付账款-物料款")

        // 筛选 AP 相关分录
        var filtered = allEntries.filter { entry ->
            entry.accountName in apAccountNames
        }

        // 按日期过滤
        if (startDate != null) filtered = filtered.filter { it.transactionDate >= startDate }
        if (endDate != null) filtered = filtered.filter { it.transactionDate <= endDate }

        // 按供应商过滤（需通过 VC → SupplyChain → Supplier）
        if (supplierId != null) {
            val vcIdsBySupplier = getVcIdsBySupplier(supplierId)
            filtered = filtered.filter { entry -> entry.refVcId in vcIdsBySupplier }
        }

        // 按日期排序，计算累计余额
        val sorted = filtered.sortedBy { it.transactionDate }
        var runningBalance = 0.0

        return sorted.map { entry ->
            runningBalance += (entry.credit - entry.debit)
            val counterpartName = entry.refVcId?.let { getCounterpartName(it) }
            ApArDetailItem(
                date = entry.transactionDate,
                voucherNo = entry.voucherNo ?: "",
                summary = entry.summary ?: "",
                debit = entry.debit,
                credit = entry.credit,
                balance = runningBalance,
                counterpartName = counterpartName,
                vcId = entry.refVcId,
                refType = entry.refType?.name
            )
        }
    }

    /** 获取某供应商关联的所有 VC ID */
    private suspend fun getVcIdsBySupplier(supplierId: Long): Set<Long> {
        val allVcs = vcRepo.getAll().first()
        return allVcs.filter { it.supplyChainId != null && getSupplierIdForVc(it) == supplierId }
            .map { it.id }.toSet()
    }

    /** 从 VC 的 supplyChainId 获取 supplierId */
    private suspend fun getSupplierIdForVc(vc: VirtualContract): Long? {
        val scId = vc.supplyChainId ?: return null
        return supplyChainRepo.getById(scId)?.supplierId
    }

    private suspend fun getCounterpartName(vcId: Long): String? {
        val vc = vcRepo.getById(vcId) ?: return null
        val scId = vc.supplyChainId ?: return null
        return supplyChainRepo.getById(scId)?.supplierName
    }
}

/**
 * 应收账款明细账 — Desktop AR 追踪
 *
 * 查询逻辑：
 * - 从 FinancialJournal 中筛选 accountName 含"应收账款"的记录
 * - 按 refVcId 关联 VirtualContract，再从 VirtualContract.businessId 查 Customer
 * - 余额 = 累计 debit(借方，应收增加) - 累计 credit(贷方，应收减少)
 */
class GetAccountReceivableDetailUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val vcRepo: VirtualContractRepository,
    private val customerRepo: ChannelCustomerRepository
) {
    suspend operator fun invoke(
        customerId: Long? = null,
        startDate: Long? = null,
        endDate: Long? = null
    ): List<ApArDetailItem> {
        val allEntries = journalRepo.getAll().first()
        val arAccountNames = setOf("应收账款", "应收账款-客户")

        var filtered = allEntries.filter { entry ->
            entry.accountName in arAccountNames
        }

        if (startDate != null) filtered = filtered.filter { it.transactionDate >= startDate }
        if (endDate != null) filtered = filtered.filter { it.transactionDate <= endDate }

        if (customerId != null) {
            val vcIdsByCustomer = getVcIdsByCustomer(customerId)
            filtered = filtered.filter { entry -> entry.refVcId in vcIdsByCustomer }
        }

        val sorted = filtered.sortedBy { it.transactionDate }
        var runningBalance = 0.0

        return sorted.map { entry ->
            runningBalance += (entry.debit - entry.credit)
            val counterpartName = entry.refVcId?.let { getCustomerName(it) }
            ApArDetailItem(
                date = entry.transactionDate,
                voucherNo = entry.voucherNo ?: "",
                summary = entry.summary ?: "",
                debit = entry.debit,
                credit = entry.credit,
                balance = runningBalance,
                counterpartName = counterpartName,
                vcId = entry.refVcId,
                refType = entry.refType?.name
            )
        }
    }

    private suspend fun getVcIdsByCustomer(customerId: Long): Set<Long> {
        val allVcs = vcRepo.getAll().first()
        return allVcs.filter { it.businessId == customerId }.map { it.id }.toSet()
    }

    private suspend fun getCustomerName(vcId: Long): String? {
        val vc = vcRepo.getById(vcId) ?: return null
        val customerId = vc.businessId ?: return null
        return customerRepo.getById(customerId)?.name
    }
}

// ==================== AP/AR 实时余额 ====================

/**
 * 应付账款实时余额
 * = SUM(credit) - SUM(debit) for all AP accounts
 *
 * @param supplierId 可选，按供应商筛选（需 FinanceAccount.counterpartId 关联）
 */
class GetApBalanceUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val financeAccountRepo: FinanceAccountRepository
) {
    suspend operator fun invoke(supplierId: Long? = null): Double {
        val allEntries = journalRepo.getAll().first()
        val apAccountNames = setOf("应付账款", "应付账款-设备款", "应付账款-物料款")

        val apAccountIds = financeAccountRepo.getAll().first()
            .filter { it.level1Name in apAccountNames }
            .map { it.id }.toSet()

        var entries = allEntries.filter { it.accountId in apAccountIds }

        // 按供应商筛选（需 FinanceAccount.counterpartId = supplierId）
        if (supplierId != null) {
            val supplierAccountIds = financeAccountRepo.getAll().first()
                .filter { it.counterpartId == supplierId && it.level1Name in apAccountNames }
                .map { it.id }.toSet()
            entries = entries.filter { it.accountId in supplierAccountIds }
        }

        val totalCredit = entries.sumOf { it.credit }
        val totalDebit = entries.sumOf { it.debit }
        return totalCredit - totalDebit
    }
}

/**
 * 应收账款实时余额
 * = SUM(debit) - SUM(credit) for all AR accounts
 *
 * @param customerId 可选，按客户筛选（需 FinanceAccount.counterpartId 关联）
 */
class GetArBalanceUseCase @Inject constructor(
    private val journalRepo: FinancialJournalRepository,
    private val financeAccountRepo: FinanceAccountRepository
) {
    suspend operator fun invoke(customerId: Long? = null): Double {
        val allEntries = journalRepo.getAll().first()
        val arAccountNames = setOf("应收账款", "应收账款-客户")

        val arAccountIds = financeAccountRepo.getAll().first()
            .filter { it.level1Name in arAccountNames }
            .map { it.id }.toSet()

        var entries = allEntries.filter { it.accountId in arAccountIds }

        if (customerId != null) {
            val customerAccountIds = financeAccountRepo.getAll().first()
                .filter { it.counterpartId == customerId && it.level1Name in arAccountNames }
                .map { it.id }.toSet()
            entries = entries.filter { it.accountId in customerAccountIds }
        }

        val totalDebit = entries.sumOf { it.debit }
        val totalCredit = entries.sumOf { it.credit }
        return totalDebit - totalCredit
    }
}
