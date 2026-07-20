package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.MaterialInventoryEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface MaterialInventoryDao {
    @Query("SELECT * FROM material_inventory ORDER BY id DESC")
    fun getAll(): Flow<List<MaterialInventoryEntity>>

    @Query("SELECT * FROM material_inventory WHERE id = :id")
    suspend fun getById(id: Long): MaterialInventoryEntity?

    @Query("SELECT * FROM material_inventory WHERE sku_id = :skuId")
    suspend fun getBySkuId(skuId: Long): MaterialInventoryEntity?

    @Query("SELECT * FROM material_inventory WHERE sku_id IN (:skuIds)")
    suspend fun getBySkuIds(skuIds: List<Long>): List<MaterialInventoryEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: MaterialInventoryEntity): Long

    @Update
    suspend fun update(entity: MaterialInventoryEntity)

    @Delete
    suspend fun delete(entity: MaterialInventoryEntity)

    @Query("SELECT COUNT(*) FROM material_inventory")
    fun getCount(): Flow<Int>
}
