package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.shanyin.erp.data.local.dao.BankAccountDao
import com.shanyin.erp.data.local.entity.BankAccountEntity
import com.shanyin.erp.domain.model.BankAccount
import com.shanyin.erp.domain.model.BankAccountInfo
import com.shanyin.erp.domain.model.OwnerType
import com.shanyin.erp.domain.repository.BankAccountRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class BankAccountRepositoryImpl @Inject constructor(
    private val dao: BankAccountDao,
    private val gson: Gson
) : BankAccountRepository {

    override fun getAll(): Flow<List<BankAccount>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): BankAccount? =
        dao.getById(id)?.toDomain()

    override fun getByOwnerType(ownerType: OwnerType): Flow<List<BankAccount>> =
        dao.getByOwnerType(ownerType.name).map { entities -> entities.map { it.toDomain() } }

    override suspend fun getDefaultByOwnerType(ownerType: OwnerType): BankAccount? =
        dao.getDefaultByOwnerType(ownerType.name)?.toDomain()

    override suspend fun insert(account: BankAccount): Long =
        dao.insert(account.toEntity())

    override suspend fun update(account: BankAccount) =
        dao.update(account.toEntity())

    override suspend fun delete(account: BankAccount) =
        dao.delete(account.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    override suspend fun getBalanceById(accountId: Long): Double {
        val inflow = dao.getTotalInflowByAccount(accountId).first()
        val outflow = dao.getTotalOutflowByAccount(accountId).first()
        return inflow - outflow
    }

    override suspend fun getTotalInflowById(accountId: Long): Double =
        dao.getTotalInflowByAccount(accountId).first()

    override suspend fun getTotalOutflowById(accountId: Long): Double =
        dao.getTotalOutflowByAccount(accountId).first()

    override suspend fun getRawAccountInfo(accountId: Long): String? =
        dao.getById(accountId)?.accountInfo

    private fun BankAccountEntity.toDomain(): BankAccount {
        val info = accountInfo?.let {
            try {
                gson.fromJson(it, BankAccountInfo::class.java)
            } catch (e: Exception) {
                null
            }
        }
        return BankAccount(
            id = id,
            ownerType = ownerType?.let { OwnerType.entries.find { t -> t.displayName == it || t.name.equals(it, ignoreCase = true) } },
            ownerId = ownerId,
            accountInfo = info,
            isDefault = isDefault
        )
    }

    private fun BankAccount.toEntity() = BankAccountEntity(
        id = id,
        ownerType = ownerType?.name,
        ownerId = ownerId,
        accountInfo = accountInfo?.let { gson.toJson(it) },
        isDefault = isDefault
    )
}
