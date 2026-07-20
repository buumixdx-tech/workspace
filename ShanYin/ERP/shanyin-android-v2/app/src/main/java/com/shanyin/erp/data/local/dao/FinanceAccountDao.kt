package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.FinanceAccountEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface FinanceAccountDao {
    @Query("SELECT * FROM finance_accounts ORDER BY category, level1_name")
    fun getAll(): Flow<List<FinanceAccountEntity>>

    @Query("SELECT * FROM finance_accounts WHERE id = :id")
    suspend fun getById(id: Long): FinanceAccountEntity?

    @Query("SELECT * FROM finance_accounts WHERE category = :category")
    fun getByCategory(category: String): Flow<List<FinanceAccountEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: FinanceAccountEntity): Long

    @Update
    suspend fun update(entity: FinanceAccountEntity)

    @Delete
    suspend fun delete(entity: FinanceAccountEntity)

    @Query("SELECT COUNT(*) FROM finance_accounts")
    fun getCount(): Flow<Int>
}
