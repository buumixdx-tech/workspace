package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.VirtualContractEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface VirtualContractDao {
    @Query("SELECT * FROM virtual_contracts ORDER BY id DESC")
    fun getAll(): Flow<List<VirtualContractEntity>>

    @Query("SELECT * FROM virtual_contracts WHERE id = :id")
    suspend fun getById(id: Long): VirtualContractEntity?

    @Query("SELECT * FROM virtual_contracts WHERE id = :id")
    fun getByIdFlow(id: Long): Flow<VirtualContractEntity?>

    @Query("SELECT * FROM virtual_contracts WHERE business_id = :businessId")
    fun getByBusinessId(businessId: Long): Flow<List<VirtualContractEntity>>

    @Query("SELECT * FROM virtual_contracts WHERE supply_chain_id = :supplyChainId")
    fun getBySupplyChainId(supplyChainId: Long): Flow<List<VirtualContractEntity>>

    @Query("SELECT * FROM virtual_contracts WHERE related_vc_id = :relatedVcId")
    fun getByRelatedVcId(relatedVcId: Long): Flow<List<VirtualContractEntity>>

    @Query("SELECT * FROM virtual_contracts WHERE status = :status")
    fun getByStatus(status: String): Flow<List<VirtualContractEntity>>

    @Query("SELECT * FROM virtual_contracts WHERE type = :type")
    fun getByType(type: String): Flow<List<VirtualContractEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: VirtualContractEntity): Long

    @Update
    suspend fun update(entity: VirtualContractEntity)

    @Delete
    suspend fun delete(entity: VirtualContractEntity)

    @Query("SELECT COUNT(*) FROM virtual_contracts")
    fun getCount(): Flow<Int>
}
