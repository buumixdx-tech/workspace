package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.shanyin.erp.data.local.entity.CashFlowLedgerEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface CashFlowLedgerDao {
    @Query("SELECT * FROM cash_flow_ledger ORDER BY id DESC")
    fun getAll(): Flow<List<CashFlowLedgerEntity>>

    @Query("SELECT * FROM cash_flow_ledger WHERE journal_id = :journalId")
    suspend fun getByJournalId(journalId: Long): CashFlowLedgerEntity?

    @Query("SELECT * FROM cash_flow_ledger WHERE main_category = :category ORDER BY id DESC")
    fun getByMainCategory(category: String): Flow<List<CashFlowLedgerEntity>>

    @Query("SELECT * FROM cash_flow_ledger ORDER BY id DESC")
    fun getAllOrdered(): Flow<List<CashFlowLedgerEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: CashFlowLedgerEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<CashFlowLedgerEntity>): List<Long>
}
