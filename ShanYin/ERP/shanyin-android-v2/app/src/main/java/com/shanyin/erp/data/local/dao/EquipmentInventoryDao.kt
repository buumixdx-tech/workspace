package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.EquipmentInventoryEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface EquipmentInventoryDao {
    @Query("SELECT * FROM equipment_inventory ORDER BY id DESC")
    fun getAll(): Flow<List<EquipmentInventoryEntity>>

    @Query("SELECT * FROM equipment_inventory WHERE id = :id")
    suspend fun getById(id: Long): EquipmentInventoryEntity?

    @Query("SELECT * FROM equipment_inventory WHERE virtual_contract_id = :vcId")
    fun getByVcId(vcId: Long): Flow<List<EquipmentInventoryEntity>>

    @Query("SELECT * FROM equipment_inventory WHERE point_id = :pointId")
    fun getByPointId(pointId: Long): Flow<List<EquipmentInventoryEntity>>

    @Query("SELECT * FROM equipment_inventory WHERE operational_status = :status")
    fun getByOperationalStatus(status: String): Flow<List<EquipmentInventoryEntity>>

    @Query("SELECT * FROM equipment_inventory WHERE sn = :sn")
    suspend fun getBySn(sn: String): EquipmentInventoryEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: EquipmentInventoryEntity): Long

    @Update
    suspend fun update(entity: EquipmentInventoryEntity)

    @Delete
    suspend fun delete(entity: EquipmentInventoryEntity)

    @Query("SELECT COUNT(*) FROM equipment_inventory")
    fun getCount(): Flow<Int>
}
