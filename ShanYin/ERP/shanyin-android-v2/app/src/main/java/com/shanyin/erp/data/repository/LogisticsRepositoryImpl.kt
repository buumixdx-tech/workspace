package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.shanyin.erp.data.local.dao.ExpressOrderDao
import com.shanyin.erp.data.local.dao.LogisticsDao
import com.shanyin.erp.data.local.dao.VirtualContractDao
import com.shanyin.erp.data.local.entity.ExpressOrderEntity
import com.shanyin.erp.data.local.entity.LogisticsEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.ExpressOrderRepository
import com.shanyin.erp.domain.repository.LogisticsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

// Shared extension functions at file level for shared entities
private fun ExpressOrderEntity.toDomain(gson: Gson): ExpressOrder {
    val itemsList: List<ExpressItem> = if (items.isNullOrBlank()) {
        emptyList()
    } else {
        try {
            val type = object : TypeToken<List<ExpressItem>>() {}.type
            gson.fromJson(items, type) ?: emptyList()
        } catch (e: Exception) {
            emptyList()
        }
    }

    val address: AddressInfo = if (addressInfo.isNullOrBlank()) {
        AddressInfo()
    } else {
        try {
            gson.fromJson(addressInfo, AddressInfo::class.java) ?: AddressInfo()
        } catch (e: Exception) {
            AddressInfo()
        }
    }

    return ExpressOrder(
        id = id,
        logisticsId = logisticsId,
        trackingNumber = trackingNumber,
        items = itemsList,
        addressInfo = address,
        status = ExpressStatus.fromDbName(status) ?: ExpressStatus.PENDING,
        timestamp = timestamp
    )
}

private fun ExpressOrder.toEntity(gson: Gson): ExpressOrderEntity {
    val itemsJson = if (items.isEmpty()) null else gson.toJson(items)
    val addressJson = gson.toJson(addressInfo)

    return ExpressOrderEntity(
        id = id,
        logisticsId = logisticsId,
        trackingNumber = trackingNumber,
        items = itemsJson,
        addressInfo = addressJson,
        status = status.name,
        timestamp = timestamp
    )
}

@Singleton
class LogisticsRepositoryImpl @Inject constructor(
    private val dao: LogisticsDao,
    private val expressOrderDao: ExpressOrderDao,
    private val vcDao: VirtualContractDao,
    private val gson: Gson
) : LogisticsRepository {

    override fun getAll(): Flow<List<Logistics>> =
        dao.getAll().map { entities ->
            entities.mapNotNull { entity ->
                try { entity.toDomain() } catch (e: Exception) { null }
            }
        }

    /** 直接从数据库获取，不依赖 Flow */
    override suspend fun getAllDirect(): List<Logistics> {
        return dao.getAllDirect().mapNotNull { entity ->
            try { entity.toDomain() } catch (e: Exception) { null }
        }
    }

    override suspend fun getById(id: Long): Logistics? =
        dao.getById(id)?.toDomain()

    override fun getByVcId(vcId: Long): Flow<List<Logistics>> =
        dao.getByVcId(vcId).map { entities ->
            entities.mapNotNull { entity ->
                try { entity.toDomain() } catch (e: Exception) { null }
            }
        }

    override suspend fun getFirstByVcId(vcId: Long): Logistics? {
        val entities = dao.getByVcId(vcId).first()
        for (entity in entities) {
            try {
                return entity.toDomain()
            } catch (e: Exception) {
                // continue
            }
        }
        return null
    }

    override fun getByStatus(status: LogisticsStatus): Flow<List<Logistics>> =
        dao.getByStatus(status.name).map { entities ->
            entities.mapNotNull { entity ->
                try { entity.toDomain() } catch (e: Exception) { null }
            }
        }

    override suspend fun insert(logistics: Logistics): Long =
        dao.insert(logistics.toEntity())

    override suspend fun update(logistics: Logistics) =
        dao.update(logistics.toEntity())

    override suspend fun delete(logistics: Logistics) =
        dao.delete(logistics.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private suspend fun LogisticsEntity.toDomain(): Logistics {
        val vcTypeName = vcDao.getById(virtualContractId)?.type?.let {
            VCType.fromDbName(it)?.displayName
        }
        val expressOrdersEntities = expressOrderDao.getByLogisticsId(id).first()
        val expressOrders = expressOrdersEntities.map { it.toDomain(gson) }

        return Logistics(
            id = id,
            virtualContractId = virtualContractId,
            vcTypeName = vcTypeName,
            financeTriggered = financeTriggered,
            status = LogisticsStatus.fromDbName(status) ?: LogisticsStatus.PENDING,
            timestamp = timestamp,
            expressOrders = expressOrders
        )
    }

    private fun Logistics.toEntity() = LogisticsEntity(
        id = id,
        virtualContractId = virtualContractId,
        financeTriggered = financeTriggered,
        status = status.name,
        timestamp = timestamp
    )
}

@Singleton
class ExpressOrderRepositoryImpl @Inject constructor(
    private val dao: ExpressOrderDao,
    private val gson: Gson
) : ExpressOrderRepository {

    override fun getAll(): Flow<List<ExpressOrder>> =
        dao.getAll().map { entities -> entities.map { it.toDomain(gson) } }

    /** 直接从数据库获取，不依赖 Flow */
    override suspend fun getAllDirect(): List<ExpressOrder> =
        dao.getAllDirect().map { it.toDomain(gson) }

    override suspend fun getById(id: Long): ExpressOrder? =
        dao.getById(id)?.toDomain(gson)

    override fun getByLogisticsId(logisticsId: Long): Flow<List<ExpressOrder>> =
        dao.getByLogisticsId(logisticsId).map { entities -> entities.map { it.toDomain(gson) } }

    override suspend fun getByTrackingNumber(trackingNumber: String): ExpressOrder? =
        dao.getByTrackingNumber(trackingNumber)?.toDomain(gson)

    override suspend fun insert(expressOrder: ExpressOrder): Long =
        dao.insert(expressOrder.toEntity(gson))

    override suspend fun update(expressOrder: ExpressOrder) =
        dao.update(expressOrder.toEntity(gson))

    override suspend fun delete(expressOrder: ExpressOrder) =
        dao.delete(expressOrder.toEntity(gson))

    override fun getCount(): Flow<Int> =
        dao.getCount()

    override suspend fun getByLogisticsIdSuspend(logisticsId: Long): List<ExpressOrder> =
        dao.getByLogisticsIdSuspend(logisticsId).map { it.toDomain(gson) }
}
