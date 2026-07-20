package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.SupplierEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface SupplierDao {
    @Query("SELECT * FROM suppliers ORDER BY name ASC")
    fun getAll(): Flow<List<SupplierEntity>>

    @Query("SELECT * FROM suppliers WHERE id = :id")
    suspend fun getById(id: Long): SupplierEntity?

    @Query("SELECT * FROM suppliers WHERE category = :category")
    fun getByCategory(category: String): Flow<List<SupplierEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: SupplierEntity): Long

    @Update
    suspend fun update(entity: SupplierEntity)

    @Delete
    suspend fun delete(entity: SupplierEntity)

    @Query("SELECT COUNT(*) FROM suppliers")
    fun getCount(): Flow<Int>
}
