package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.*
import kotlinx.coroutines.flow.Flow

interface FinanceAccountRepository {
    fun getAll(): Flow<List<FinanceAccount>>
    suspend fun getById(id: Long): FinanceAccount?
    fun getByCategory(category: FinanceCategory): Flow<List<FinanceAccount>>
    /** 按 level1Name 精确查找 */
    suspend fun getByName(name: String): FinanceAccount?
    suspend fun insert(account: FinanceAccount): Long
    suspend fun update(account: FinanceAccount)
    suspend fun delete(account: FinanceAccount)
    fun getCount(): Flow<Int>
}

interface CashFlowRepository {
    fun getAll(): Flow<List<CashFlow>>
    suspend fun getById(id: Long): CashFlow?
    fun getByVcId(vcId: Long): Flow<List<CashFlow>>
    fun getByType(type: CashFlowType): Flow<List<CashFlow>>
    fun getByAccountId(accountId: Long): Flow<List<CashFlow>>
    suspend fun insert(cashFlow: CashFlow): Long
    suspend fun update(cashFlow: CashFlow)
    suspend fun delete(cashFlow: CashFlow)
    fun getCount(): Flow<Int>
    fun getTotalOutflowByTypeAndAccount(type: String, accountId: Long): Flow<Double?>
    fun getTotalInflowByTypeAndAccount(type: String, accountId: Long): Flow<Double?>
    /** Rule engine: get cash flows for VC sorted by transaction date */
    suspend fun getByVcIdSorted(vcId: Long): List<CashFlow>
    /** Rule engine: get cash flows for VC filtered by types, sorted by transaction date */
    suspend fun getByVcIdAndTypes(vcId: Long, types: List<CashFlowType>): List<CashFlow>
}

interface FinancialJournalRepository {
    fun getAll(): Flow<List<FinancialJournalEntry>>
    suspend fun getById(id: Long): FinancialJournalEntry?
    fun getByVcId(vcId: Long): Flow<List<FinancialJournalEntry>>
    fun getByVoucherNo(voucherNo: String): Flow<List<FinancialJournalEntry>>
    fun getByAccountId(accountId: Long): Flow<List<FinancialJournalEntry>>
    fun getByDateRange(startDate: Long, endDate: Long): Flow<List<FinancialJournalEntry>>
    fun getByAccountIdAndDateRange(accountId: Long, startDate: Long, endDate: Long): Flow<List<FinancialJournalEntry>>
    suspend fun insert(entry: FinancialJournalEntry): Long
    suspend fun insertAll(entries: List<FinancialJournalEntry>): List<Long>
    suspend fun update(entry: FinancialJournalEntry)
    suspend fun delete(entry: FinancialJournalEntry)
    fun getCount(): Flow<Int>
    /** 查询以指定前缀的最大序号，用于生成顺序凭证号 JZ-YYYYMM-NNNN */
    suspend fun getMaxSeqForPrefix(prefix: String, prefixLength: Int): Int?
}

/**
 * 资金流向分类账（C满FlowLedger）
 *
 * 将每笔 CashFlow 按资金流向分类：
 * - mainCategory: OPERATING / INVESTING / FINANCING
 * - direction: INFLOW / OUTFLOW
 */
interface CashFlowLedgerRepository {
    fun getAll(): Flow<List<CashFlowLedger>>
    suspend fun getByJournalId(journalId: Long): CashFlowLedger?
    fun getByMainCategory(category: String): Flow<List<CashFlowLedger>>
    fun getByDateRange(startDate: Long, endDate: Long): Flow<List<CashFlowLedger>>
    suspend fun insert(ledger: CashFlowLedger): Long
    suspend fun insertAll(ledgers: List<CashFlowLedger>): List<Long>
}
