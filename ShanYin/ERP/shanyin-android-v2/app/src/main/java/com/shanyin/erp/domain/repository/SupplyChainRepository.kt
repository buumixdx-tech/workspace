package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.SupplyChain
import com.shanyin.erp.domain.model.SupplyChainItem
import com.shanyin.erp.domain.model.SupplyChainType
import kotlinx.coroutines.flow.Flow

interface SupplyChainRepository {
    fun getAll(): Flow<List<SupplyChain>>
    suspend fun getById(id: Long): SupplyChain?
    fun getBySupplierId(supplierId: Long): Flow<List<SupplyChain>>
    fun getByType(type: SupplyChainType): Flow<List<SupplyChain>>
    suspend fun insert(supplyChain: SupplyChain): Long
    suspend fun update(supplyChain: SupplyChain)
    suspend fun delete(supplyChain: SupplyChain)
    fun getCount(): Flow<Int>
}

interface SupplyChainItemRepository {
    fun getAll(): Flow<List<SupplyChainItem>>
    suspend fun getById(id: Long): SupplyChainItem?
    fun getBySupplyChainId(supplyChainId: Long): Flow<List<SupplyChainItem>>
    suspend fun getBySkuId(skuId: Long): SupplyChainItem?
    suspend fun insert(item: SupplyChainItem): Long
    suspend fun insertAll(items: List<SupplyChainItem>): List<Long>
    suspend fun update(item: SupplyChainItem)
    suspend fun delete(item: SupplyChainItem)
    suspend fun deleteBySupplyChainId(supplyChainId: Long)
}
