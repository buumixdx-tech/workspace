package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.shanyin.erp.data.local.entity.SystemEventEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface SystemEventDao {
    @Query("SELECT * FROM system_events ORDER BY created_at DESC")
    fun getAll(): Flow<List<SystemEventEntity>>

    @Query("SELECT * FROM system_events WHERE id = :id")
    suspend fun getById(id: Long): SystemEventEntity?

    @Query("SELECT * FROM system_events WHERE event_type = :eventType")
    fun getByEventType(eventType: String): Flow<List<SystemEventEntity>>

    @Query("SELECT * FROM system_events WHERE aggregate_type = :aggregateType AND aggregate_id = :aggregateId")
    fun getByAggregate(aggregateType: String, aggregateId: Long): Flow<List<SystemEventEntity>>

    @Query("SELECT * FROM system_events WHERE pushed_to_ai = 0 ORDER BY created_at ASC LIMIT :limit")
    fun getUnpushedEvents(limit: Int = 100): Flow<List<SystemEventEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: SystemEventEntity): Long

    @Query("UPDATE system_events SET pushed_to_ai = 1 WHERE id = :id")
    suspend fun markAsPushed(id: Long)

    @Query("SELECT COUNT(*) FROM system_events")
    fun getCount(): Flow<Int>
}
