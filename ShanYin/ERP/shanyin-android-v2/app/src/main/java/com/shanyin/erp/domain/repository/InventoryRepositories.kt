package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.*
import kotlinx.coroutines.flow.Flow

interface EquipmentInventoryRepository {
    fun getAll(): Flow<List<EquipmentInventory>>
    suspend fun getById(id: Long): EquipmentInventory?
    fun getByVcId(vcId: Long): Flow<List<EquipmentInventory>>
    fun getByPointId(pointId: Long): Flow<List<EquipmentInventory>>
    fun getByOperationalStatus(status: OperationalStatus): Flow<List<EquipmentInventory>>
    suspend fun getBySn(sn: String): EquipmentInventory?
    suspend fun insert(equipment: EquipmentInventory): Long
    suspend fun update(equipment: EquipmentInventory)
    suspend fun delete(equipment: EquipmentInventory)
    fun getCount(): Flow<Int>
}

interface MaterialInventoryRepository {
    fun getAll(): Flow<List<MaterialInventory>>
    suspend fun getById(id: Long): MaterialInventory?
    suspend fun getBySkuId(skuId: Long): MaterialInventory?
    suspend fun getBySkuIds(skuIds: List<Long>): List<MaterialInventory>
    suspend fun insert(material: MaterialInventory): Long
    suspend fun update(material: MaterialInventory)
    suspend fun delete(material: MaterialInventory)
    fun getCount(): Flow<Int>
}
