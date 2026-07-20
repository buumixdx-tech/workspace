package com.shanyin.erp.data.repository

import com.shanyin.erp.data.local.dao.ChannelCustomerDao
import com.shanyin.erp.data.local.entity.ChannelCustomerEntity
import com.shanyin.erp.domain.model.ChannelCustomer
import com.shanyin.erp.domain.repository.ChannelCustomerRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ChannelCustomerRepositoryImpl @Inject constructor(
    private val dao: ChannelCustomerDao
) : ChannelCustomerRepository {

    override fun getAll(): Flow<List<ChannelCustomer>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): ChannelCustomer? =
        dao.getById(id)?.toDomain()

    override fun getByIdFlow(id: Long): Flow<ChannelCustomer?> =
        dao.getByIdFlow(id).map { it?.toDomain() }

    override suspend fun insert(customer: ChannelCustomer): Long =
        dao.insert(customer.toEntity())

    override suspend fun update(customer: ChannelCustomer) =
        dao.update(customer.toEntity())

    override suspend fun delete(customer: ChannelCustomer) =
        dao.delete(customer.toEntity())

    override suspend fun deleteById(id: Long) =
        dao.deleteById(id)

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun ChannelCustomerEntity.toDomain() = ChannelCustomer(
        id = id,
        name = name,
        info = info,
        createdAt = createdAt
    )

    private fun ChannelCustomer.toEntity() = ChannelCustomerEntity(
        id = id,
        name = name,
        info = info,
        createdAt = createdAt
    )
}
