package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.BankAccountEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface BankAccountDao {
    @Query("SELECT * FROM bank_accounts ORDER BY owner_type, id")
    fun getAll(): Flow<List<BankAccountEntity>>

    @Query("SELECT * FROM bank_accounts WHERE id = :id")
    suspend fun getById(id: Long): BankAccountEntity?

    @Query("SELECT * FROM bank_accounts WHERE owner_type = :ownerType")
    fun getByOwnerType(ownerType: String): Flow<List<BankAccountEntity>>

    @Query("SELECT * FROM bank_accounts WHERE is_default = 1 AND owner_type = :ownerType")
    suspend fun getDefaultByOwnerType(ownerType: String): BankAccountEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: BankAccountEntity): Long

    @Update
    suspend fun update(entity: BankAccountEntity)

    @Delete
    suspend fun delete(entity: BankAccountEntity)

    @Query("SELECT COUNT(*) FROM bank_accounts")
    fun getCount(): Flow<Int>

    /**
     * 查询指定银行账户作为收款方的总流入
     * WHERE payee_account_id = :accountId
     */
    @Query("SELECT COALESCE(SUM(amount), 0.0) FROM cash_flows WHERE payee_account_id = :accountId")
    fun getTotalInflowByAccount(accountId: Long): Flow<Double>

    /**
     * 查询指定银行账户作为付款方的总流出
     * WHERE payer_account_id = :accountId
     */
    @Query("SELECT COALESCE(SUM(amount), 0.0) FROM cash_flows WHERE payer_account_id = :accountId")
    fun getTotalOutflowByAccount(accountId: Long): Flow<Double>
}
