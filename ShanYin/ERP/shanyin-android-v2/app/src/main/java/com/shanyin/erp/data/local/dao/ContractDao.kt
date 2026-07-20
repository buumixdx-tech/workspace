package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.ContractEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ContractDao {
    @Query("SELECT * FROM contracts ORDER BY timestamp DESC")
    fun getAll(): Flow<List<ContractEntity>>

    @Query("SELECT * FROM contracts WHERE id = :id")
    suspend fun getById(id: Long): ContractEntity?

    @Query("SELECT * FROM contracts WHERE contract_number = :contractNumber")
    suspend fun getByContractNumber(contractNumber: String): ContractEntity?

    @Query("SELECT * FROM contracts WHERE status = :status")
    fun getByStatus(status: String): Flow<List<ContractEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: ContractEntity): Long

    @Update
    suspend fun update(entity: ContractEntity)

    @Delete
    suspend fun delete(entity: ContractEntity)

    @Query("SELECT COUNT(*) FROM contracts")
    fun getCount(): Flow<Int>
}
