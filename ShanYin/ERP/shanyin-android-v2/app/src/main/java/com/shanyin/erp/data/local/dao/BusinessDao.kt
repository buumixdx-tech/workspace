package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.BusinessEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface BusinessDao {
    @Query("SELECT * FROM business ORDER BY timestamp DESC")
    fun getAll(): Flow<List<BusinessEntity>>

    @Query("SELECT * FROM business WHERE id = :id")
    suspend fun getById(id: Long): BusinessEntity?

    @Query("SELECT * FROM business WHERE id = :id")
    fun getByIdFlow(id: Long): Flow<BusinessEntity?>

    @Query("SELECT * FROM business WHERE customer_id = :customerId")
    fun getByCustomerId(customerId: Long): Flow<List<BusinessEntity>>

    @Query("SELECT * FROM business WHERE status = :status")
    fun getByStatus(status: String): Flow<List<BusinessEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: BusinessEntity): Long

    @Update
    suspend fun update(entity: BusinessEntity)

    @Delete
    suspend fun delete(entity: BusinessEntity)

    @Query("SELECT COUNT(*) FROM business")
    fun getCount(): Flow<Int>
}
