package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.SkuEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface SkuDao {
    @Query("SELECT * FROM skus ORDER BY name ASC")
    fun getAll(): Flow<List<SkuEntity>>

    @Query("SELECT * FROM skus WHERE id = :id")
    suspend fun getById(id: Long): SkuEntity?

    @Query("SELECT * FROM skus WHERE supplier_id = :supplierId")
    fun getBySupplierId(supplierId: Long): Flow<List<SkuEntity>>

    @Query("SELECT * FROM skus WHERE type_level1 = :typeLevel1")
    fun getByTypeLevel1(typeLevel1: String): Flow<List<SkuEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: SkuEntity): Long

    @Update
    suspend fun update(entity: SkuEntity)

    @Delete
    suspend fun delete(entity: SkuEntity)

    @Query("SELECT COUNT(*) FROM skus")
    fun getCount(): Flow<Int>
}
