package com.shanyin.erp.data.repository

import com.shanyin.erp.data.local.dao.SupplierDao
import com.shanyin.erp.data.local.entity.SupplierEntity
import com.shanyin.erp.domain.model.Supplier
import com.shanyin.erp.domain.model.SupplierCategory
import com.shanyin.erp.domain.repository.SupplierRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SupplierRepositoryImpl @Inject constructor(
    private val dao: SupplierDao
) : SupplierRepository {

    override fun getAll(): Flow<List<Supplier>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): Supplier? =
        dao.getById(id)?.toDomain()

    override fun getByCategory(category: SupplierCategory): Flow<List<Supplier>> =
        dao.getByCategory(category.name).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(supplier: Supplier): Long =
        dao.insert(supplier.toEntity())

    override suspend fun update(supplier: Supplier) =
        dao.update(supplier.toEntity())

    override suspend fun delete(supplier: Supplier) =
        dao.delete(supplier.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun SupplierEntity.toDomain() = Supplier(
        id = id,
        name = name,
        category = category?.let { SupplierCategory.entries.find { c -> c.displayName == it || c.name.equals(it, ignoreCase = true) } },
        address = address,
        qualifications = qualifications,
        info = info
    )

    private fun Supplier.toEntity() = SupplierEntity(
        id = id,
        name = name,
        category = category?.name,
        address = address,
        qualifications = qualifications,
        info = info
    )
}
