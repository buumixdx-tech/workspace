package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.*
import kotlinx.coroutines.flow.Flow

interface VirtualContractRepository {
    fun getAll(): Flow<List<VirtualContract>>
    suspend fun getById(id: Long): VirtualContract?
    fun getByIdFlow(id: Long): Flow<VirtualContract?>
    fun getByBusinessId(businessId: Long): Flow<List<VirtualContract>>
    fun getBySupplyChainId(supplyChainId: Long): Flow<List<VirtualContract>>
    fun getByRelatedVcId(relatedVcId: Long): Flow<List<VirtualContract>>
    fun getByStatus(status: VCStatus): Flow<List<VirtualContract>>
    fun getByType(type: VCType): Flow<List<VirtualContract>>
    suspend fun insert(vc: VirtualContract): Long
    suspend fun update(vc: VirtualContract)
    suspend fun delete(vc: VirtualContract)
    fun getCount(): Flow<Int>
}

interface VCStatusLogRepository {
    fun getByVcId(vcId: Long): Flow<List<VCStatusLog>>
    suspend fun insert(log: VCStatusLog): Long
    suspend fun deleteByVcId(vcId: Long)
    /** Rule engine: get earliest status log entry by category and status name */
    suspend fun getEarliestByCategoryAndStatus(vcId: Long, category: StatusLogCategory, statusName: String): VCStatusLog?
}

interface VCHistoryRepository {
    fun getByVcId(vcId: Long): Flow<List<VCHistory>>
    suspend fun insert(history: VCHistory): Long
}
