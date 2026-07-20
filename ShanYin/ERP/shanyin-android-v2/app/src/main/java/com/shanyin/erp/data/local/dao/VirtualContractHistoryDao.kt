package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.shanyin.erp.data.local.entity.VirtualContractHistoryEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface VirtualContractHistoryDao {
    @Query("SELECT * FROM vc_history WHERE vc_id = :vcId ORDER BY change_date DESC")
    fun getByVcId(vcId: Long): Flow<List<VirtualContractHistoryEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: VirtualContractHistoryEntity): Long
}
