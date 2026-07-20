package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.ExternalPartnerEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ExternalPartnerDao {
    @Query("SELECT * FROM external_partners ORDER BY name ASC")
    fun getAll(): Flow<List<ExternalPartnerEntity>>

    @Query("SELECT * FROM external_partners WHERE id = :id")
    suspend fun getById(id: Long): ExternalPartnerEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: ExternalPartnerEntity): Long

    @Update
    suspend fun update(entity: ExternalPartnerEntity)

    @Delete
    suspend fun delete(entity: ExternalPartnerEntity)

    @Query("SELECT COUNT(*) FROM external_partners")
    fun getCount(): Flow<Int>
}
