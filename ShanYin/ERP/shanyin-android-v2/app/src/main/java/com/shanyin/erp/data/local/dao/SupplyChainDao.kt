package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.SupplyChainEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface SupplyChainDao {
    @Query("SELECT * FROM supply_chains ORDER BY id DESC")
    fun getAll(): Flow<List<SupplyChainEntity>>

    @Query("SELECT * FROM supply_chains WHERE id = :id")
    suspend fun getById(id: Long): SupplyChainEntity?

    @Query("SELECT * FROM supply_chains WHERE supplier_id = :supplierId")
    fun getBySupplierId(supplierId: Long): Flow<List<SupplyChainEntity>>

    @Query("SELECT * FROM supply_chains WHERE type = :type")
    fun getByType(type: String): Flow<List<SupplyChainEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: SupplyChainEntity): Long

    @Update
    suspend fun update(entity: SupplyChainEntity)

    @Delete
    suspend fun delete(entity: SupplyChainEntity)

    @Query("SELECT COUNT(*) FROM supply_chains")
    fun getCount(): Flow<Int>
}
