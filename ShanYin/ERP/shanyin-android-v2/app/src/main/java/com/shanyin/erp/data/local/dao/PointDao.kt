package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.PointEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PointDao {
    @Query("SELECT * FROM points ORDER BY name ASC")
    fun getAll(): Flow<List<PointEntity>>

    @Query("SELECT * FROM points WHERE id = :id")
    suspend fun getById(id: Long): PointEntity?

    @Query("SELECT * FROM points WHERE customer_id = :customerId")
    fun getByCustomerId(customerId: Long): Flow<List<PointEntity>>

    @Query("SELECT * FROM points WHERE supplier_id = :supplierId")
    fun getBySupplierId(supplierId: Long): Flow<List<PointEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: PointEntity): Long

    @Update
    suspend fun update(entity: PointEntity)

    @Delete
    suspend fun delete(entity: PointEntity)

    @Query("SELECT COUNT(*) FROM points")
    fun getCount(): Flow<Int>
}
