package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.*
import kotlinx.coroutines.flow.Flow

interface LogisticsRepository {
    fun getAll(): Flow<List<Logistics>>
    /** 直接从数据库获取，不依赖 Flow 缓存 */
    suspend fun getAllDirect(): List<Logistics>
    suspend fun getById(id: Long): Logistics?
    fun getByVcId(vcId: Long): Flow<List<Logistics>>
    /** Returns the first logistics record for a VC (Desktop-consistent: one logistics per VC) */
    suspend fun getFirstByVcId(vcId: Long): Logistics?
    fun getByStatus(status: LogisticsStatus): Flow<List<Logistics>>
    suspend fun insert(logistics: Logistics): Long
    suspend fun update(logistics: Logistics)
    suspend fun delete(logistics: Logistics)
    fun getCount(): Flow<Int>
}

interface ExpressOrderRepository {
    fun getAll(): Flow<List<ExpressOrder>>
    /** 直接从数据库获取，不依赖 Flow 缓存 */
    suspend fun getAllDirect(): List<ExpressOrder>
    suspend fun getById(id: Long): ExpressOrder?
    fun getByLogisticsId(logisticsId: Long): Flow<List<ExpressOrder>>
    suspend fun getByTrackingNumber(trackingNumber: String): ExpressOrder?
    suspend fun insert(expressOrder: ExpressOrder): Long
    suspend fun update(expressOrder: ExpressOrder)
    suspend fun delete(expressOrder: ExpressOrder)
    fun getCount(): Flow<Int>
    /** Rule engine: get express orders for logistics (suspend version) */
    suspend fun getByLogisticsIdSuspend(logisticsId: Long): List<ExpressOrder>
}
