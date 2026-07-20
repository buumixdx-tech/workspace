package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.SupplyChainItemEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface SupplyChainItemDao {
    @Query("SELECT * FROM supply_chain_items ORDER BY id DESC")
    fun getAll(): Flow<List<SupplyChainItemEntity>>

    @Query("SELECT * FROM supply_chain_items WHERE id = :id")
    suspend fun getById(id: Long): SupplyChainItemEntity?

    @Query("SELECT * FROM supply_chain_items WHERE supply_chain_id = :supplyChainId")
    fun getBySupplyChainId(supplyChainId: Long): Flow<List<SupplyChainItemEntity>>

    @Query("SELECT * FROM supply_chain_items WHERE sku_id = :skuId")
    suspend fun getBySkuId(skuId: Long): SupplyChainItemEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: SupplyChainItemEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<SupplyChainItemEntity>): List<Long>

    @Update
    suspend fun update(entity: SupplyChainItemEntity)

    @Delete
    suspend fun delete(entity: SupplyChainItemEntity)
}
