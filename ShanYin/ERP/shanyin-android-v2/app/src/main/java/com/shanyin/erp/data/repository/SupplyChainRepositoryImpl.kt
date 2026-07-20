package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.shanyin.erp.data.local.dao.SkuDao
import com.shanyin.erp.data.local.dao.SupplyChainDao
import com.shanyin.erp.data.local.dao.SupplyChainItemDao
import com.shanyin.erp.data.local.entity.SupplyChainEntity
import com.shanyin.erp.data.local.entity.SupplyChainItemEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.SupplyChainItemRepository
import com.shanyin.erp.domain.repository.SupplyChainRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SupplyChainRepositoryImpl @Inject constructor(
    private val dao: SupplyChainDao,
    private val gson: Gson
) : SupplyChainRepository {

    override fun getAll(): Flow<List<SupplyChain>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): SupplyChain? =
        dao.getById(id)?.toDomain()

    override fun getBySupplierId(supplierId: Long): Flow<List<SupplyChain>> =
        dao.getBySupplierId(supplierId).map { entities -> entities.map { it.toDomain() } }

    override fun getByType(type: SupplyChainType): Flow<List<SupplyChain>> =
        dao.getByType(type.name).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(supplyChain: SupplyChain): Long =
        dao.insert(supplyChain.toEntity())

    override suspend fun update(supplyChain: SupplyChain) =
        dao.update(supplyChain.toEntity())

    override suspend fun delete(supplyChain: SupplyChain) =
        dao.delete(supplyChain.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun SupplyChainEntity.toDomain(): SupplyChain {
        return SupplyChain(
            id = id,
            supplierId = supplierId,
            supplierName = supplierName,
            type = type?.let { typeStr ->
                SupplyChainType.entries.find { it.displayName == typeStr || it.name.equals(typeStr, ignoreCase = true) }
            } ?: SupplyChainType.MATERIAL,
            contractId = contractId,
            pricingConfig = PricingConfig.fromJson(pricingConfig),
            paymentTerms = PaymentTerms.fromJson(paymentTerms)
        )
    }

    private fun SupplyChain.toEntity() = SupplyChainEntity(
        id = id,
        supplierId = supplierId,
        supplierName = supplierName,
        type = type.name,
        contractId = contractId,
        pricingConfig = pricingConfig?.toJson(),
        paymentTerms = paymentTerms?.toJson()
    )
}

@Singleton
class SupplyChainItemRepositoryImpl @Inject constructor(
    private val dao: SupplyChainItemDao,
    private val skuDao: SkuDao
) : SupplyChainItemRepository {

    override fun getAll(): Flow<List<SupplyChainItem>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): SupplyChainItem? =
        dao.getById(id)?.toDomain()

    override fun getBySupplyChainId(supplyChainId: Long): Flow<List<SupplyChainItem>> =
        dao.getBySupplyChainId(supplyChainId).map { entities -> entities.map { it.toDomain() } }

    override suspend fun getBySkuId(skuId: Long): SupplyChainItem? =
        dao.getBySkuId(skuId)?.toDomain()

    override suspend fun insert(item: SupplyChainItem): Long =
        dao.insert(item.toEntity())

    override suspend fun insertAll(items: List<SupplyChainItem>): List<Long> =
        dao.insertAll(items.map { it.toEntity() })

    override suspend fun update(item: SupplyChainItem) =
        dao.update(item.toEntity())

    override suspend fun delete(item: SupplyChainItem) =
        dao.delete(item.toEntity())

    override suspend fun deleteBySupplyChainId(supplyChainId: Long) {
        val items = dao.getBySupplyChainId(supplyChainId).first()
        items.forEach { dao.delete(it) }
    }

    private suspend fun SupplyChainItemEntity.toDomain(): SupplyChainItem {
        val skuName = skuDao.getById(skuId)?.name ?: ""
        return SupplyChainItem(
            id = id,
            supplyChainId = supplyChainId,
            skuId = skuId,
            skuName = skuName,
            price = price ?: 0.0,
            deposit = deposit ?: 0.0,
            isFloating = isFloating
        )
    }

    private fun SupplyChainItem.toEntity() = SupplyChainItemEntity(
        id = id,
        supplyChainId = supplyChainId,
        skuId = skuId,
        price = price,
        deposit = deposit,
        isFloating = isFloating
    )
}
