package com.shanyin.erp.data.repository

import android.util.Log
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.shanyin.erp.data.local.dao.BankAccountDao
import com.shanyin.erp.data.local.dao.CashFlowDao
import com.shanyin.erp.data.local.dao.CashFlowLedgerDao
import com.shanyin.erp.data.local.dao.FinanceAccountDao
import com.shanyin.erp.data.local.dao.FinancialJournalDao
import com.shanyin.erp.data.local.entity.CashFlowEntity
import com.shanyin.erp.data.local.entity.CashFlowLedgerEntity
import com.shanyin.erp.data.local.entity.FinanceAccountEntity
import com.shanyin.erp.data.local.entity.FinancialJournalEntity
import com.shanyin.erp.domain.model.CashFlow
import com.shanyin.erp.domain.model.CashFlowLedger
import com.shanyin.erp.domain.model.CashFlowDirection
import com.shanyin.erp.domain.model.CashFlowMainCategory
import com.shanyin.erp.domain.model.CashFlowType
import com.shanyin.erp.domain.model.CounterpartType
import com.shanyin.erp.domain.model.AccountDirection
import com.shanyin.erp.domain.model.FinanceAccount
import com.shanyin.erp.domain.model.FinanceCategory
import com.shanyin.erp.domain.model.RefType
import com.shanyin.erp.domain.model.PaymentInfo
import com.shanyin.erp.domain.model.FinancialJournalEntry
import com.shanyin.erp.domain.repository.CashFlowLedgerRepository
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.FinanceAccountRepository
import com.shanyin.erp.domain.repository.FinancialJournalRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FinanceAccountRepositoryImpl @Inject constructor(
    private val dao: FinanceAccountDao
) : FinanceAccountRepository {

    override fun getAll(): Flow<List<FinanceAccount>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): FinanceAccount? =
        dao.getById(id)?.toDomain()

    override fun getByCategory(category: FinanceCategory): Flow<List<FinanceAccount>> =
        dao.getByCategory(category.name).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(account: FinanceAccount): Long =
        dao.insert(account.toEntity())

    override suspend fun update(account: FinanceAccount) =
        dao.update(account.toEntity())

    override suspend fun delete(account: FinanceAccount) =
        dao.delete(account.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    override suspend fun getByName(name: String): FinanceAccount? {
        return dao.getAll().first().find { it.level1Name == name }?.toDomain()
    }

    private fun FinanceAccountEntity.toDomain() = FinanceAccount(
        id = id,
        category = category?.let { FinanceCategory.entries.find { c -> c.displayName == it || c.name.equals(it, ignoreCase = true) } },
        level1Name = level1Name,
        level2Name = level2Name,
        counterpartType = counterpartType?.let { CounterpartType.entries.find { t -> t.displayName == it || t.name.equals(it, ignoreCase = true) } },
        counterpartId = counterpartId,
        direction = direction?.let { AccountDirection.entries.find { d -> d.displayName == it || d.name.equals(it, ignoreCase = true) } }
    )

    private fun FinanceAccount.toEntity() = FinanceAccountEntity(
        id = id,
        category = category?.name,
        level1Name = level1Name,
        level2Name = level2Name,
        counterpartType = counterpartType?.name,
        counterpartId = counterpartId,
        direction = direction?.name
    )
}

@Singleton
class CashFlowRepositoryImpl @Inject constructor(
    private val dao: CashFlowDao,
    private val bankAccountDao: BankAccountDao,
    private val gson: Gson
) : CashFlowRepository {

    override fun getAll(): Flow<List<CashFlow>> =
        dao.getAll().map { entities ->
            entities.mapNotNull { entity ->
                try {
                    entity.toDomain()
                } catch (e: Exception) {
                    null
                }
            }
        }

    override suspend fun getById(id: Long): CashFlow? =
        dao.getById(id)?.toDomain()

    override fun getByVcId(vcId: Long): Flow<List<CashFlow>> =
        dao.getByVcId(vcId).map { entities ->
            entities.mapNotNull { entity ->
                try { entity.toDomain() } catch (e: Exception) { null }
            }
        }

    override fun getByType(type: CashFlowType): Flow<List<CashFlow>> =
        dao.getByType(type.name).map { entities ->
            entities.mapNotNull { entity ->
                try { entity.toDomain() } catch (e: Exception) { null }
            }
        }

    override fun getByAccountId(accountId: Long): Flow<List<CashFlow>> =
        dao.getByAccountId(accountId).map { entities ->
            entities.mapNotNull { entity ->
                try { entity.toDomain() } catch (e: Exception) { null }
            }
        }

    override suspend fun insert(cashFlow: CashFlow): Long =
        dao.insert(cashFlow.toEntity())

    override suspend fun update(cashFlow: CashFlow) =
        dao.update(cashFlow.toEntity())

    override suspend fun delete(cashFlow: CashFlow) =
        dao.delete(cashFlow.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    override fun getTotalOutflowByTypeAndAccount(type: String, accountId: Long): Flow<Double?> =
        dao.getTotalOutflowByTypeAndAccount(type, accountId)

    override fun getTotalInflowByTypeAndAccount(type: String, accountId: Long): Flow<Double?> =
        dao.getTotalInflowByTypeAndAccount(type, accountId)

    override suspend fun getByVcIdSorted(vcId: Long): List<CashFlow> =
        dao.getByVcIdSorted(vcId).map { it.toDomain() }

    override suspend fun getByVcIdAndTypes(vcId: Long, types: List<CashFlowType>): List<CashFlow> =
        dao.getByVcIdAndTypes(vcId, types.map { it.name }).map { it.toDomain() }

    private suspend fun CashFlowEntity.toDomain(): CashFlow {
        // 优先用 Entity 中已存储的账户名称，兜底查 DAO
        val bankAccountEntity = payerAccountId?.let { bankAccountDao.getById(it) }
        Log.d("FinanceDebug", "toDomain: payerAccountId=$payerAccountId, payerAccountName(entity)='$payerAccountName', bankAccountEntity.accountInfo='${bankAccountEntity?.accountInfo}'")

        val payerName = payerAccountName
            ?: payerAccountId?.let { bankAccountDao.getById(it)?.accountInfo }
                ?.let { rawInfo ->
                    Log.d("FinanceDebug", "toDomain: extracting from DAO rawInfo='$rawInfo'")
                    extractBankAccountName(rawInfo)
                }
        Log.d("FinanceDebug", "toDomain: final payerName='$payerName'")

        val payeeName = payeeAccountName
            ?: payeeAccountId?.let { bankAccountDao.getById(it)?.accountInfo }
                ?.let { rawInfo ->
                    Log.d("FinanceDebug", "toDomain: extracting payee from DAO rawInfo='$rawInfo'")
                    extractBankAccountName(rawInfo)
                }
        Log.d("FinanceDebug", "toDomain: final payeeName='$payeeName'")

        val payment: PaymentInfo? = if (paymentInfo.isNullOrBlank()) {
            null
        } else {
            try {
                gson.fromJson(paymentInfo, PaymentInfo::class.java)
            } catch (e: Exception) {
                null
            }
        }

        return CashFlow(
            id = id,
            virtualContractId = virtualContractId,
            type = CashFlowType.fromDbName(type),
            amount = amount,
            payerAccountId = payerAccountId,
            payerAccountName = payerName,
            payeeAccountId = payeeAccountId,
            payeeAccountName = payeeName,
            financeTriggered = financeTriggered,
            paymentInfo = payment,
            voucherPath = voucherPath,
            description = description,
            transactionDate = transactionDate,
            timestamp = timestamp
        )
    }

    private fun extractBankAccountName(accountInfo: String): String {
        Log.d("FinanceDebug", "extractBankAccountName: input='$accountInfo'")
        return try {
            val info = gson.fromJson(accountInfo, Map::class.java)
            // 支持中英文键：银行名称/bankName, 银行账号/账号/accountNumber/accountNo
            val bankName = (info["银行名称"] as? String ?: info["bankName"] as? String ?: "").trim()
            val accountNo = (info["银行账号"] as? String ?: info["账号"] as? String ?: info["accountNumber"] as? String ?: info["accountNo"] as? String ?: "").trim()
            val result = if (bankName.isNotEmpty() || accountNo.isNotEmpty()) "$bankName $accountNo".trim() else ""
            Log.d("FinanceDebug", "extractBankAccountName: bankName='$bankName', accountNo='$accountNo', result='$result'")
            result
        } catch (e: Exception) {
            Log.e("FinanceDebug", "extractBankAccountName: exception=${e.message}")
            accountInfo
        }
    }

    private fun CashFlow.toEntity(): CashFlowEntity {
        val paymentJson = paymentInfo?.let { gson.toJson(it) }

        return CashFlowEntity(
            id = id,
            virtualContractId = virtualContractId,
            type = type?.name,
            amount = amount,
            payerAccountId = payerAccountId,
            payerAccountName = payerAccountName,
            payeeAccountId = payeeAccountId,
            payeeAccountName = payeeAccountName,
            financeTriggered = financeTriggered,
            paymentInfo = paymentJson,
            voucherPath = voucherPath,
            description = description,
            transactionDate = transactionDate,
            timestamp = timestamp
        )
    }
}

@Singleton
class FinancialJournalRepositoryImpl @Inject constructor(
    private val dao: FinancialJournalDao,
    private val financeAccountDao: FinanceAccountDao,
    private val gson: Gson
) : FinancialJournalRepository {

    override fun getAll(): Flow<List<FinancialJournalEntry>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): FinancialJournalEntry? =
        dao.getById(id)?.toDomain()

    override fun getByVcId(vcId: Long): Flow<List<FinancialJournalEntry>> =
        dao.getByVcId(vcId).map { entities -> entities.map { it.toDomain() } }

    override fun getByVoucherNo(voucherNo: String): Flow<List<FinancialJournalEntry>> =
        dao.getByVoucherNo(voucherNo).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(entry: FinancialJournalEntry): Long =
        dao.insert(entry.toEntity())

    override suspend fun insertAll(entries: List<FinancialJournalEntry>): List<Long> =
        dao.insertAll(entries.map { it.toEntity() })

    override suspend fun update(entry: FinancialJournalEntry) =
        dao.update(entry.toEntity())

    override suspend fun delete(entry: FinancialJournalEntry) =
        dao.delete(entry.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    override suspend fun getMaxSeqForPrefix(prefix: String, prefixLength: Int): Int? =
        dao.getMaxSeqForPrefix(prefix, prefixLength)

    override fun getByAccountId(accountId: Long): Flow<List<FinancialJournalEntry>> =
        dao.getByAccountId(accountId).map { entities -> entities.map { it.toDomain() } }

    override fun getByDateRange(startDate: Long, endDate: Long): Flow<List<FinancialJournalEntry>> =
        dao.getByDateRange(startDate, endDate).map { entities -> entities.map { it.toDomain() } }

    override fun getByAccountIdAndDateRange(accountId: Long, startDate: Long, endDate: Long): Flow<List<FinancialJournalEntry>> =
        dao.getByAccountIdAndDateRange(accountId, startDate, endDate).map { entities -> entities.map { it.toDomain() } }

    private suspend fun FinancialJournalEntity.toDomain(): FinancialJournalEntry {
        val accountName = accountId?.let { financeAccountDao.getById(it)?.level1Name }

        return FinancialJournalEntry(
            id = id,
            voucherNo = voucherNo,
            accountId = accountId,
            accountName = accountName,
            debit = debit,
            credit = credit,
            summary = summary,
            refType = refType?.let { RefType.entries.find { r -> r.displayName == it || r.name.equals(it, ignoreCase = true) } },
            refId = refId,
            refVcId = refVcId,
            transactionDate = transactionDate
        )
    }

    private fun FinancialJournalEntry.toEntity() = FinancialJournalEntity(
        id = id,
        voucherNo = voucherNo,
        accountId = accountId,
        debit = debit,
        credit = credit,
        summary = summary,
        refType = refType?.name,
        refId = refId,
        refVcId = refVcId,
        transactionDate = transactionDate
    )
}

@Singleton
class CashFlowLedgerRepositoryImpl @Inject constructor(
    private val dao: CashFlowLedgerDao,
    private val journalDao: FinancialJournalDao
) : CashFlowLedgerRepository {

    override fun getAll(): Flow<List<CashFlowLedger>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getByJournalId(journalId: Long): CashFlowLedger? =
        dao.getByJournalId(journalId)?.toDomain()

    override fun getByMainCategory(category: String): Flow<List<CashFlowLedger>> =
        dao.getByMainCategory(category).map { entities -> entities.map { it.toDomain() } }

    override fun getByDateRange(startDate: Long, endDate: Long): Flow<List<CashFlowLedger>> =
        dao.getAllOrdered().map { entities ->
            entities.map { it.toDomain() }.filter { ledger ->
                ledger.transactionDate in startDate..endDate
            }
        }

    override suspend fun insert(ledger: CashFlowLedger): Long =
        dao.insert(ledger.toEntity())

    override suspend fun insertAll(ledgers: List<CashFlowLedger>): List<Long> =
        dao.insertAll(ledgers.map { it.toEntity() })

    private suspend fun CashFlowLedgerEntity.toDomain(): CashFlowLedger {
        val journal = journalDao.getById(journalId)
        return CashFlowLedger(
            id = id,
            journalId = journalId,
            mainCategory = mainCategory?.let { CashFlowMainCategory.entries.find { m -> m.name == it } },
            direction = direction?.let { CashFlowDirection.entries.find { d -> d.name == it } },
            amount = amount,
            transactionDate = journal?.transactionDate ?: System.currentTimeMillis()
        )
    }

    private fun CashFlowLedger.toEntity() = CashFlowLedgerEntity(
        id = id,
        journalId = journalId,
        mainCategory = mainCategory?.name,
        direction = direction?.name,
        amount = amount
    )
}
