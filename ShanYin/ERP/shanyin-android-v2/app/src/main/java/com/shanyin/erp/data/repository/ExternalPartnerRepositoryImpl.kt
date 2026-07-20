package com.shanyin.erp.data.repository

import com.shanyin.erp.data.local.dao.ExternalPartnerDao
import com.shanyin.erp.data.local.entity.ExternalPartnerEntity
import com.shanyin.erp.domain.model.ExternalPartner
import com.shanyin.erp.domain.model.PartnerType
import com.shanyin.erp.domain.repository.ExternalPartnerRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ExternalPartnerRepositoryImpl @Inject constructor(
    private val dao: ExternalPartnerDao
) : ExternalPartnerRepository {

    override fun getAll(): Flow<List<ExternalPartner>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): ExternalPartner? =
        dao.getById(id)?.toDomain()

    override suspend fun insert(partner: ExternalPartner): Long =
        dao.insert(partner.toEntity())

    override suspend fun update(partner: ExternalPartner) =
        dao.update(partner.toEntity())

    override suspend fun delete(partner: ExternalPartner) =
        dao.delete(partner.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun ExternalPartnerEntity.toDomain() = ExternalPartner(
        id = id,
        type = type?.let { PartnerType.entries.find { t -> t.displayName == it || t.name.equals(it, ignoreCase = true) } },
        name = name,
        address = address,
        content = content
    )

    private fun ExternalPartner.toEntity() = ExternalPartnerEntity(
        id = id,
        type = type?.name,
        name = name,
        address = address,
        content = content
    )
}
