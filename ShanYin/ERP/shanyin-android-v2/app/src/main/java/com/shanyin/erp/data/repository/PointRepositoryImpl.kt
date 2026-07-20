package com.shanyin.erp.data.repository

import com.shanyin.erp.data.local.dao.PointDao
import com.shanyin.erp.data.local.entity.PointEntity
import com.shanyin.erp.domain.model.Point
import com.shanyin.erp.domain.model.PointType
import com.shanyin.erp.domain.repository.PointRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PointRepositoryImpl @Inject constructor(
    private val dao: PointDao
) : PointRepository {

    override fun getAll(): Flow<List<Point>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): Point? =
        dao.getById(id)?.toDomain()

    override fun getByCustomerId(customerId: Long): Flow<List<Point>> =
        dao.getByCustomerId(customerId).map { entities -> entities.map { it.toDomain() } }

    override fun getBySupplierId(supplierId: Long): Flow<List<Point>> =
        dao.getBySupplierId(supplierId).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(point: Point): Long =
        dao.insert(point.toEntity())

    override suspend fun update(point: Point) =
        dao.update(point.toEntity())

    override suspend fun delete(point: Point) =
        dao.delete(point.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun PointEntity.toDomain() = Point(
        id = id,
        customerId = customerId,
        supplierId = supplierId,
        name = name,
        address = address,
        type = type?.let { PointType.entries.find { t -> t.displayName == it || t.name.equals(it, ignoreCase = true) } },
        receivingAddress = receivingAddress
    )

    private fun Point.toEntity() = PointEntity(
        id = id,
        customerId = customerId,
        supplierId = supplierId,
        name = name,
        address = address,
        type = type?.name,
        receivingAddress = receivingAddress
    )
}
