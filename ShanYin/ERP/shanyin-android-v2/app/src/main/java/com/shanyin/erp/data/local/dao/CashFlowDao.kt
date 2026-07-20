package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.CashFlowEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface CashFlowDao {
    @Query("SELECT * FROM cash_flows ORDER BY timestamp DESC")
    fun getAll(): Flow<List<CashFlowEntity>>

    @Query("SELECT * FROM cash_flows WHERE id = :id")
    suspend fun getById(id: Long): CashFlowEntity?

    @Query("SELECT * FROM cash_flows WHERE virtual_contract_id = :vcId")
    fun getByVcId(vcId: Long): Flow<List<CashFlowEntity>>

    @Query("SELECT * FROM cash_flows WHERE type = :type")
    fun getByType(type: String): Flow<List<CashFlowEntity>>

    @Query("SELECT * FROM cash_flows WHERE payer_account_id = :accountId OR payee_account_id = :accountId")
    fun getByAccountId(accountId: Long): Flow<List<CashFlowEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: CashFlowEntity): Long

    @Update
    suspend fun update(entity: CashFlowEntity)

    @Delete
    suspend fun delete(entity: CashFlowEntity)

    @Query("SELECT COUNT(*) FROM cash_flows")
    fun getCount(): Flow<Int>

    @Query("SELECT SUM(amount) FROM cash_flows WHERE type = :type AND payer_account_id = :accountId")
    fun getTotalOutflowByTypeAndAccount(type: String, accountId: Long): Flow<Double?>

    @Query("SELECT SUM(amount) FROM cash_flows WHERE type = :type AND payee_account_id = :accountId")
    fun getTotalInflowByTypeAndAccount(type: String, accountId: Long): Flow<Double?>

    @Query("SELECT * FROM cash_flows WHERE virtual_contract_id = :vcId ORDER BY transaction_date ASC")
    suspend fun getByVcIdSorted(vcId: Long): List<CashFlowEntity>

    @Query("SELECT * FROM cash_flows WHERE virtual_contract_id = :vcId AND type IN (:types) ORDER BY transaction_date ASC")
    suspend fun getByVcIdAndTypes(vcId: Long, types: List<String>): List<CashFlowEntity>
}
