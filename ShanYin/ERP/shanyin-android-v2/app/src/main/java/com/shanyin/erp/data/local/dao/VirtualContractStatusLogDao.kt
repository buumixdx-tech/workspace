package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.shanyin.erp.data.local.entity.VirtualContractStatusLogEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface VirtualContractStatusLogDao {
    @Query("SELECT * FROM vc_status_logs WHERE vc_id = :vcId ORDER BY timestamp DESC")
    fun getByVcId(vcId: Long): Flow<List<VirtualContractStatusLogEntity>>

    @Query("SELECT * FROM vc_status_logs WHERE vc_id = :vcId AND category = :category AND status_name = :statusName ORDER BY timestamp ASC LIMIT 1")
    suspend fun getEarliestByCategoryAndStatus(vcId: Long, category: String, statusName: String): VirtualContractStatusLogEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: VirtualContractStatusLogEntity): Long

    @Query("DELETE FROM vc_status_logs WHERE vc_id = :vcId")
    suspend fun deleteByVcId(vcId: Long)
}
