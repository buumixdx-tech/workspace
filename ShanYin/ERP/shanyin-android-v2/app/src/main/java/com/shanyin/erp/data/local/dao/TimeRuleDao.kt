package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.TimeRuleEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface TimeRuleDao {
    @Query("SELECT * FROM time_rules ORDER BY timestamp DESC")
    fun getAll(): Flow<List<TimeRuleEntity>>

    @Query("SELECT * FROM time_rules WHERE id = :id")
    suspend fun getById(id: Long): TimeRuleEntity?

    @Query("SELECT * FROM time_rules WHERE related_id = :relatedId AND related_type = :relatedType")
    fun getByRelatedIdAndType(relatedId: Long, relatedType: String): Flow<List<TimeRuleEntity>>

    @Query("SELECT * FROM time_rules WHERE related_id = :relatedId AND related_type = :relatedType AND inherit = :inherit AND status = :status")
    suspend fun getTemplateRules(relatedId: Long, relatedType: String, inherit: Int, status: String): List<TimeRuleEntity>

    @Query("SELECT * FROM time_rules WHERE related_type = :relatedType")
    fun getByRelatedType(relatedType: String): Flow<List<TimeRuleEntity>>

    @Query("SELECT * FROM time_rules WHERE status = :status")
    fun getByStatus(status: String): Flow<List<TimeRuleEntity>>

    @Query("SELECT * FROM time_rules WHERE warning = :warning")
    fun getByWarning(warning: String): Flow<List<TimeRuleEntity>>

    @Query("SELECT * FROM time_rules WHERE status NOT IN (:skipStatuses)")
    suspend fun getAllNonTemplate(skipStatuses: List<String>): List<TimeRuleEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: TimeRuleEntity): Long

    @Update
    suspend fun update(entity: TimeRuleEntity)

    @Delete
    suspend fun delete(entity: TimeRuleEntity)

    @Query("SELECT COUNT(*) FROM time_rules")
    fun getCount(): Flow<Int>
}
