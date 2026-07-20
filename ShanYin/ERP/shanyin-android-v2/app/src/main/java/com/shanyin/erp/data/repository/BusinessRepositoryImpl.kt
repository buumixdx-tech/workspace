package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.reflect.TypeToken
import com.shanyin.erp.data.local.dao.BusinessDao
import com.shanyin.erp.data.local.dao.ContractDao
import com.shanyin.erp.data.local.entity.BusinessEntity
import com.shanyin.erp.data.local.entity.ContractEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.BusinessRepository
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import com.shanyin.erp.domain.repository.ContractRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class BusinessRepositoryImpl @Inject constructor(
    private val dao: BusinessDao,
    private val gson: Gson
) : BusinessRepository {

    override fun getAll(): Flow<List<Business>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): Business? =
        dao.getById(id)?.toDomain()

    override fun getByIdFlow(id: Long): Flow<Business?> =
        dao.getByIdFlow(id).map { it?.toDomain() }

    override fun getByCustomerId(customerId: Long): Flow<List<Business>> =
        dao.getByCustomerId(customerId).map { entities -> entities.map { it.toDomain() } }

    override fun getByStatus(status: BusinessStatus): Flow<List<Business>> =
        dao.getByStatus(status.name).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(business: Business): Long =
        dao.insert(business.toEntity())

    override suspend fun update(business: Business) =
        dao.update(business.toEntity())

    override suspend fun delete(business: Business) =
        dao.delete(business.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun BusinessEntity.toDomain(): Business {
        val detailsJson = details
        val businessDetails = if (detailsJson.isNullOrBlank()) {
            BusinessDetails()
        } else {
            try {
                parseBusinessDetails(detailsJson)
            } catch (e: Exception) {
                BusinessDetails()
            }
        }
        return Business(
            id = id,
            customerId = customerId,
            contractId = contractId,
            status = status?.let { statusStr ->
                BusinessStatus.entries.find { s -> s.name == statusStr }
                    ?: BusinessStatus.entries.find { s -> s.displayName == statusStr }
            } ?: BusinessStatus.INITIAL_CONTACT,
            timestamp = timestamp,
            details = businessDetails
        )
    }

    /** 手动解析 details JSON，手动将 history 中的 from/to 中文名映射为 BusinessStatus 枚举 */
    private fun parseBusinessDetails(json: String): BusinessDetails {
        val obj = gson.fromJson(json, com.google.gson.JsonObject::class.java)
        val history = mutableListOf<StageTransition>()
        obj.getAsJsonArray("history")?.forEach { elem ->
            val h = elem.asJsonObject
            val fromStr = h.get("from")?.takeIf { !it.isJsonNull }?.asString
            val toStr = h.get("to")?.takeIf { !it.isJsonNull }?.asString
            val time = h.get("time")?.takeIf { !it.isJsonNull }?.let { elem ->
                when {
                    elem.isJsonPrimitive && elem.asJsonPrimitive.isNumber -> elem.asLong
                    else -> elem.asString.let { parseTs(it) }
                }
            } ?: System.currentTimeMillis()
            val comment = h.get("comment")?.takeIf { !it.isJsonNull }?.asString
            history.add(StageTransition(
                from = BusinessStatus.fromString(fromStr),
                to = BusinessStatus.fromString(toStr),
                time = time,
                comment = comment
            ))
        }
        val notes = obj.get("notes")?.takeIf { !it.isJsonNull }?.asString
        val summary = obj.get("summary")?.takeIf { !it.isJsonNull }?.asString

        // payment_terms - 支持 snake_case (Desktop 导入) 和 camelCase (Android 写入)
        val ptObj = obj.getAsJsonObject("payment_terms") ?: obj.getAsJsonObject("paymentTerms")
        val paymentTerms = ptObj?.let { pt ->
            BusinessPaymentTerms(
                prepaymentRatio = pt.get("prepayment_ratio")?.takeIf { !it.isJsonNull }?.asJsonPrimitive?.asDouble
                    ?: pt.get("prepaymentRatio")?.takeIf { !it.isJsonNull }?.asJsonPrimitive?.asDouble ?: 0.0,
                balancePeriod = pt.get("balance_period")?.takeIf { !it.isJsonNull }?.asJsonPrimitive?.asInt
                    ?: pt.get("balancePeriod")?.takeIf { !it.isJsonNull }?.asJsonPrimitive?.asInt ?: 0,
                dayRule = pt.get("day_rule")?.takeIf { !it.isJsonNull }?.asString
                    ?: pt.get("dayRule")?.takeIf { !it.isJsonNull }?.asString,
                startTrigger = pt.get("start_trigger")?.takeIf { !it.isJsonNull }?.asString
                    ?: pt.get("startTrigger")?.takeIf { !it.isJsonNull }?.asString
            )
        }

        // pricing
        val pricing = mutableMapOf<String, SkuPriceItem>()
        obj.getAsJsonObject("pricing")?.entrySet()?.forEach { (skuName, value) ->
            val item = value.asJsonObject
            pricing[skuName] = SkuPriceItem(
                price = item.get("price")?.takeIf { !it.isJsonNull }?.asJsonPrimitive?.asDouble ?: 0.0,
                deposit = item.get("deposit")?.takeIf { !it.isJsonNull }?.asJsonPrimitive?.asDouble ?: 0.0
            )
        }

        return BusinessDetails(history, notes, summary, paymentTerms, pricing)
    }

    private fun parseTs(ts: String): Long {
        return try {
            LocalDateTime.parse(ts, DateTimeFormatter.ISO_LOCAL_DATE_TIME)
                .toInstant(ZoneOffset.UTC).toEpochMilli()
        } catch (e: Exception) {
            System.currentTimeMillis()
        }
    }

    private fun Business.toEntity() = BusinessEntity(
        id = id,
        customerId = customerId,
        contractId = contractId,
        status = status?.name,
        timestamp = timestamp,
        details = gson.toJson(details)
    )
}

@Singleton
class ContractRepositoryImpl @Inject constructor(
    private val dao: ContractDao,
    private val gson: Gson
) : ContractRepository {

    override fun getAll(): Flow<List<Contract>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): Contract? =
        dao.getById(id)?.toDomain()

    override suspend fun getByContractNumber(contractNumber: String): Contract? =
        dao.getByContractNumber(contractNumber)?.toDomain()

    override fun getByStatus(status: String): Flow<List<Contract>> =
        dao.getByStatus(status).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(contract: Contract): Long =
        dao.insert(contract.toEntity())

    override suspend fun update(contract: Contract) =
        dao.update(contract.toEntity())

    override suspend fun delete(contract: Contract) =
        dao.delete(contract.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun ContractEntity.toDomain(): Contract {
        val partiesList: List<ContractParty> = if (parties.isNullOrBlank()) {
            emptyList()
        } else {
            try {
                val type = object : TypeToken<List<ContractParty>>() {}.type
                gson.fromJson(parties, type)
            } catch (e: Exception) {
                emptyList()
            }
        }

        val content = if (content.isNullOrBlank()) {
            null
        } else {
            try {
                gson.fromJson(content, ContractContent::class.java)
            } catch (e: Exception) {
                null
            }
        }

        return Contract(
            id = id,
            contractNumber = contractNumber,
            type = type?.let { ContractType.entries.find { t -> t.displayName == it || t.name.equals(it, ignoreCase = true) } },
            status = status?.let { ContractStatus.entries.find { s -> s.displayName == it || s.name.equals(it, ignoreCase = true) } },
            parties = partiesList,
            content = content,
            signedDate = signedDate,
            effectiveDate = effectiveDate,
            expiryDate = expiryDate,
            timestamp = timestamp
        )
    }

    private fun Contract.toEntity() = ContractEntity(
        id = id,
        contractNumber = contractNumber,
        type = type?.name,
        status = status?.name,
        parties = gson.toJson(parties),
        content = content?.let { gson.toJson(it) },
        signedDate = signedDate,
        effectiveDate = effectiveDate,
        expiryDate = expiryDate,
        timestamp = timestamp
    )
}
