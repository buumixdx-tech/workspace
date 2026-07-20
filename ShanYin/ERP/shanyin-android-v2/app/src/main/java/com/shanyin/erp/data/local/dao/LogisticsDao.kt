package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.LogisticsEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface LogisticsDao {
    @Query("SELECT * FROM logistics ORDER BY timestamp DESC")
    fun getAll(): Flow<List<LogisticsEntity>>

    /** 直接查询，不返回 Flow */
    @Query("SELECT * FROM logistics ORDER BY timestamp DESC")
    suspend fun getAllDirect(): List<LogisticsEntity>

    @Query("SELECT * FROM logistics WHERE id = :id")
    suspend fun getById(id: Long): LogisticsEntity?

    @Query("SELECT * FROM logistics WHERE virtual_contract_id = :vcId")
    fun getByVcId(vcId: Long): Flow<List<LogisticsEntity>>

    @Query("SELECT * FROM logistics WHERE status = :status")
    fun getByStatus(status: String): Flow<List<LogisticsEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: LogisticsEntity): Long

    @Update
    suspend fun update(entity: LogisticsEntity)

    @Delete
    suspend fun delete(entity: LogisticsEntity)

    @Query("SELECT COUNT(*) FROM logistics")
    fun getCount(): Flow<Int>
}
