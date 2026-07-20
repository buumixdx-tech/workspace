package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.shanyin.erp.data.local.dao.EquipmentInventoryDao
import com.shanyin.erp.data.local.dao.MaterialInventoryDao
import com.shanyin.erp.data.local.dao.SkuDao
import com.shanyin.erp.data.local.dao.VirtualContractDao
import com.shanyin.erp.data.local.dao.PointDao
import com.shanyin.erp.data.local.entity.EquipmentInventoryEntity
import com.shanyin.erp.data.local.entity.MaterialInventoryEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.MaterialInventoryRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class EquipmentInventoryRepositoryImpl @Inject constructor(
    private val dao: EquipmentInventoryDao,
    private val skuDao: SkuDao,
    private val vcDao: VirtualContractDao,
    private val pointDao: PointDao,
    private val gson: Gson
) : EquipmentInventoryRepository {

    override fun getAll(): Flow<List<EquipmentInventory>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): EquipmentInventory? =
        dao.getById(id)?.toDomain()

    override fun getByVcId(vcId: Long): Flow<List<EquipmentInventory>> =
        dao.getByVcId(vcId).map { entities -> entities.map { it.toDomain() } }

    override fun getByPointId(pointId: Long): Flow<List<EquipmentInventory>> =
        dao.getByPointId(pointId).map { entities -> entities.map { it.toDomain() } }

    override fun getByOperationalStatus(status: OperationalStatus): Flow<List<EquipmentInventory>> =
        dao.getByOperationalStatus(status.name).map { entities -> entities.map { it.toDomain() } }

    override suspend fun getBySn(sn: String): EquipmentInventory? =
        dao.getBySn(sn)?.toDomain()

    override suspend fun insert(equipment: EquipmentInventory): Long =
        dao.insert(equipment.toEntity())

    override suspend fun update(equipment: EquipmentInventory) =
        dao.update(equipment.toEntity())

    override suspend fun delete(equipment: EquipmentInventory) =
        dao.delete(equipment.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private suspend fun EquipmentInventoryEntity.toDomain(): EquipmentInventory {
        val skuName = skuId?.let { id -> skuDao.getById(id)?.name }
        val vcTypeName = virtualContractId?.let { id ->
            vcDao.getById(id)?.type?.let { typeStr ->
                VCType.fromDbName(typeStr)?.displayName
            }
        }
        val pointName = pointId?.let { id -> pointDao.getById(id)?.name }

        return EquipmentInventory(
            id = id,
            skuId = skuId,
            skuName = skuName,
            sn = sn,
            operationalStatus = OperationalStatus.fromDbName(operationalStatus) ?: OperationalStatus.IN_STOCK,
            deviceStatus = deviceStatus?.let {
                DeviceStatus.entries.find { s -> s.displayName == it || s.name.equals(it, ignoreCase = true) }
            } ?: DeviceStatus.NORMAL,
            virtualContractId = virtualContractId,
            vcTypeName = vcTypeName,
            pointId = pointId,
            pointName = pointName,
            depositAmount = depositAmount,
            depositTimestamp = depositTimestamp
        )
    }

    private fun EquipmentInventory.toEntity() = EquipmentInventoryEntity(
        id = id,
        skuId = skuId,
        sn = sn,
        operationalStatus = operationalStatus.name,
        deviceStatus = deviceStatus.name,
        virtualContractId = virtualContractId,
        pointId = pointId,
        depositAmount = depositAmount,
        depositTimestamp = depositTimestamp
    )
}

@Singleton
class MaterialInventoryRepositoryImpl @Inject constructor(
    private val dao: MaterialInventoryDao,
    private val skuDao: SkuDao,
    private val pointDao: PointDao,
    private val gson: Gson
) : MaterialInventoryRepository {

    override fun getAll(): Flow<List<MaterialInventory>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): MaterialInventory? =
        dao.getById(id)?.toDomain()

    override suspend fun getBySkuId(skuId: Long): MaterialInventory? =
        dao.getBySkuId(skuId)?.toDomain()

    override suspend fun getBySkuIds(skuIds: List<Long>): List<MaterialInventory> =
        dao.getBySkuIds(skuIds).map { it.toDomain() }

    override suspend fun insert(material: MaterialInventory): Long =
        dao.insert(material.toEntity())

    override suspend fun update(material: MaterialInventory) =
        dao.update(material.toEntity())

    override suspend fun delete(material: MaterialInventory) =
        dao.delete(material.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private suspend fun MaterialInventoryEntity.toDomain(): MaterialInventory {
        val skuName = skuDao.getById(skuId)?.name ?: ""

        val stockDistList: List<StockDistribution> = if (stockDistribution.isNullOrEmpty()) {
            emptyList()
        } else {
            try {
                // 尝试解析 Mobile 格式: List<StockDistribution>
                val listType = object : TypeToken<List<StockDistribution>>() {}.type
                val parsed: List<StockDistribution>? = gson.fromJson(stockDistribution, listType)
                if (!parsed.isNullOrEmpty()) {
                    parsed
                } else {
                    // 降级解析 Desktop 格式: Map<String, Int> (warehouse_name -> quantity)
                    // 格式: {"仓库A": 100, "仓库B": 50}
                    val mapType = object : TypeToken<Map<String, Int>>() {}.type
                    val map: Map<String, Int>? = gson.fromJson(stockDistribution, mapType)
                    if (!map.isNullOrEmpty()) {
                        // 查找对应的 Point 记录获取 pointId
                        val pointMap = mutableMapOf<String, Long>()
                        try {
                            val allPoints = pointDao.getAll().first()
                            for (point in allPoints) {
                                pointMap[point.name] = point.id
                            }
                        } catch (e: Exception) {
                            // ignore
                        }
                        map.map { (name, qty) ->
                            StockDistribution(
                                pointId = pointMap[name] ?: 0L,
                                pointName = name,
                                quantity = qty
                            )
                        }
                    } else {
                        emptyList()
                    }
                }
            } catch (e: Exception) {
                // 最后尝试 Desktop Map 格式
                try {
                    val mapType = object : TypeToken<Map<String, Int>>() {}.type
                    val map: Map<String, Int>? = gson.fromJson(stockDistribution, mapType)
                    if (!map.isNullOrEmpty()) {
                        val pointMap = mutableMapOf<String, Long>()
                        try {
                            val allPoints = pointDao.getAll().first()
                            for (point in allPoints) {
                                pointMap[point.name] = point.id
                            }
                        } catch (ex: Exception) {
                            // ignore
                        }
                        map.map { (name, qty) ->
                            StockDistribution(
                                pointId = pointMap[name] ?: 0L,
                                pointName = name,
                                quantity = qty
                            )
                        }
                    } else {
                        emptyList()
                    }
                } catch (ex: Exception) {
                    emptyList()
                }
            }
        }

        return MaterialInventory(
            id = id,
            skuId = skuId,
            skuName = skuName,
            stockDistribution = stockDistList,
            averagePrice = averagePrice,
            totalBalance = totalBalance
        )
    }

    private fun MaterialInventory.toEntity(): MaterialInventoryEntity {
        val stockDistJson = if (stockDistribution.isEmpty()) {
            null
        } else {
            gson.toJson(stockDistribution)
        }

        return MaterialInventoryEntity(
            id = id,
            skuId = skuId,
            stockDistribution = stockDistJson,
            averagePrice = averagePrice,
            totalBalance = totalBalance
        )
    }
}
