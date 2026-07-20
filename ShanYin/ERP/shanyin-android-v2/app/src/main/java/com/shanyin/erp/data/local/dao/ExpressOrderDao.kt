package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.ExpressOrderEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ExpressOrderDao {
    @Query("SELECT * FROM express_orders ORDER BY timestamp DESC")
    fun getAll(): Flow<List<ExpressOrderEntity>>

    /** 直接查询，不返回 Flow */
    @Query("SELECT * FROM express_orders ORDER BY timestamp DESC")
    suspend fun getAllDirect(): List<ExpressOrderEntity>

    @Query("SELECT * FROM express_orders WHERE id = :id")
    suspend fun getById(id: Long): ExpressOrderEntity?

    @Query("SELECT * FROM express_orders WHERE logistics_id = :logisticsId")
    fun getByLogisticsId(logisticsId: Long): Flow<List<ExpressOrderEntity>>

    @Query("SELECT * FROM express_orders WHERE logistics_id = :logisticsId")
    suspend fun getByLogisticsIdSuspend(logisticsId: Long): List<ExpressOrderEntity>

    @Query("SELECT * FROM express_orders WHERE tracking_number = :trackingNumber")
    suspend fun getByTrackingNumber(trackingNumber: String): ExpressOrderEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: ExpressOrderEntity): Long

    @Update
    suspend fun update(entity: ExpressOrderEntity)

    @Delete
    suspend fun delete(entity: ExpressOrderEntity)

    @Query("SELECT COUNT(*) FROM express_orders")
    fun getCount(): Flow<Int>
}
