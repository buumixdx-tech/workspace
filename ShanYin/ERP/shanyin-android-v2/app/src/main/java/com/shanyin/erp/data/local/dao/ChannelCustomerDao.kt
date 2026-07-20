package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.ChannelCustomerEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ChannelCustomerDao {
    @Query("SELECT * FROM channel_customers ORDER BY name ASC")
    fun getAll(): Flow<List<ChannelCustomerEntity>>

    @Query("SELECT * FROM channel_customers WHERE id = :id")
    suspend fun getById(id: Long): ChannelCustomerEntity?

    @Query("SELECT * FROM channel_customers WHERE id = :id")
    fun getByIdFlow(id: Long): Flow<ChannelCustomerEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: ChannelCustomerEntity): Long

    @Update
    suspend fun update(entity: ChannelCustomerEntity)

    @Delete
    suspend fun delete(entity: ChannelCustomerEntity)

    @Query("DELETE FROM channel_customers WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM channel_customers")
    fun getCount(): Flow<Int>
}
