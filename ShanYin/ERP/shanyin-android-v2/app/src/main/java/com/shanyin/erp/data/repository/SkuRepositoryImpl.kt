package com.shanyin.erp.data.repository

import com.shanyin.erp.data.local.dao.SkuDao
import com.shanyin.erp.data.local.entity.SkuEntity
import com.shanyin.erp.domain.model.Sku
import com.shanyin.erp.domain.model.SkuType
import com.shanyin.erp.domain.repository.SkuRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SkuRepositoryImpl @Inject constructor(
    private val dao: SkuDao
) : SkuRepository {

    override fun getAll(): Flow<List<Sku>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): Sku? =
        dao.getById(id)?.toDomain()

    override fun getBySupplierId(supplierId: Long): Flow<List<Sku>> =
        dao.getBySupplierId(supplierId).map { entities -> entities.map { it.toDomain() } }

    override fun getByTypeLevel1(type: SkuType): Flow<List<Sku>> =
        dao.getByTypeLevel1(type.displayName).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(sku: Sku): Long =
        dao.insert(sku.toEntity())

    override suspend fun update(sku: Sku) =
        dao.update(sku.toEntity())

    override suspend fun delete(sku: Sku) =
        dao.delete(sku.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun SkuEntity.toDomain() = Sku(
        id = id,
        supplierId = supplierId,
        name = name,
        typeLevel1 = typeLevel1?.let { SkuType.entries.find { t -> t.displayName == it } },
        typeLevel2 = typeLevel2,
        model = model,
        description = description,
        certification = certification,
        params = params
    )

    private fun Sku.toEntity() = SkuEntity(
        id = id,
        supplierId = supplierId,
        name = name,
        typeLevel1 = typeLevel1?.displayName,
        typeLevel2 = typeLevel2,
        model = model,
        description = description,
        certification = certification,
        params = params
    )
}
