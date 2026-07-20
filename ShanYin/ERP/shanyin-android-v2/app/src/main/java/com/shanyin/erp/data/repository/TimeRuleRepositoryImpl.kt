package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.shanyin.erp.data.local.dao.SystemEventDao
import com.shanyin.erp.data.local.dao.TimeRuleDao
import com.shanyin.erp.data.local.entity.SystemEventEntity
import com.shanyin.erp.data.local.entity.TimeRuleEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.SystemEventRepository
import com.shanyin.erp.domain.repository.TimeRuleRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TimeRuleRepositoryImpl @Inject constructor(
    private val dao: TimeRuleDao
) : TimeRuleRepository {

    override fun getAll(): Flow<List<TimeRule>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): TimeRule? =
        dao.getById(id)?.toDomain()

    override fun getByRelatedIdAndType(relatedId: Long, relatedType: RelatedType): Flow<List<TimeRule>> =
        dao.getByRelatedIdAndType(relatedId, relatedType.displayName).map { entities -> entities.map { it.toDomain() } }

    override fun getByRelatedType(relatedType: RelatedType): Flow<List<TimeRule>> =
        dao.getByRelatedType(relatedType.displayName).map { entities -> entities.map { it.toDomain() } }

    override fun getByStatus(status: RuleStatus): Flow<List<TimeRule>> =
        dao.getByStatus(status.displayName).map { entities -> entities.map { it.toDomain() } }

    override fun getByWarning(warning: WarningLevel): Flow<List<TimeRule>> =
        dao.getByWarning(warning.displayName).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(rule: TimeRule): Long =
        dao.insert(rule.toEntity())

    override suspend fun update(rule: TimeRule) =
        dao.update(rule.toEntity())

    override suspend fun delete(rule: TimeRule) =
        dao.delete(rule.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    override suspend fun getTemplateRules(relatedId: Long, relatedType: RelatedType, inherit: InheritLevel): List<TimeRule> =
        dao.getTemplateRules(relatedId, relatedType.displayName, inherit.ordinal, RuleStatus.TEMPLATE.displayName)
            .map { it.toDomain() }

    override suspend fun getAllNonTemplate(): List<TimeRule> =
        dao.getAllNonTemplate(listOf(RuleStatus.TEMPLATE.displayName))
            .map { it.toDomain() }

    private fun TimeRuleEntity.toDomain() = TimeRule(
        id = id,
        relatedId = relatedId,
        relatedType = RelatedType.fromDbName(relatedType) ?: RelatedType.BUSINESS,
        inherit = InheritLevel.fromOrdinal(inherit) ?: InheritLevel.SELF,
        party = party?.let { Party.entries.find { p -> p.displayName == it } },
        triggerEvent = triggerEvent?.let { RuleEvent.entries.find { t -> t.displayName == it } },
        tgeParam1 = tgeParam1,
        tgeParam2 = tgeParam2,
        triggerTime = triggerTime,
        targetEvent = RuleEvent.entries.find { it.displayName == targetEvent } ?: RuleEvent.VC_CREATED,
        taeParam1 = taeParam1,
        taeParam2 = taeParam2,
        targetTime = targetTime,
        offset = offset,
        unit = unit?.let { TimeUnit.entries.find { u -> u.displayName == it } },
        flagTime = flagTime,
        direction = Direction.fromDbName(direction),
        warning = WarningLevel.fromDbName(warning),
        result = RuleResult.fromDbName(result),
        status = RuleStatus.fromDbName(status) ?: RuleStatus.ACTIVE,
        timestamp = timestamp,
        resultstamp = resultstamp,
        endstamp = endstamp
    )

    private fun TimeRule.toEntity() = TimeRuleEntity(
        id = id,
        relatedId = relatedId,
        relatedType = relatedType.displayName,
        inherit = inherit.ordinal,
        party = party?.displayName,
        triggerEvent = triggerEvent?.displayName,
        tgeParam1 = tgeParam1,
        tgeParam2 = tgeParam2,
        triggerTime = triggerTime,
        targetEvent = targetEvent.displayName,
        taeParam1 = taeParam1,
        taeParam2 = taeParam2,
        targetTime = targetTime,
        offset = offset,
        unit = unit?.displayName,
        flagTime = flagTime,
        direction = direction?.displayName?.lowercase(),
        warning = warning?.displayName,
        result = result?.displayName,
        status = status.displayName,
        timestamp = timestamp,
        resultstamp = resultstamp,
        endstamp = endstamp
    )
}

@Singleton
class SystemEventRepositoryImpl @Inject constructor(
    private val dao: SystemEventDao,
    private val gson: Gson
) : SystemEventRepository {

    override fun getAll(): Flow<List<SystemEvent>> =
        dao.getAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getById(id: Long): SystemEvent? =
        dao.getById(id)?.toDomain()

    override fun getByEventType(eventType: SystemEventType): Flow<List<SystemEvent>> =
        dao.getByEventType(eventType.name).map { entities -> entities.map { it.toDomain() } }

    override fun getByAggregate(aggregateType: String, aggregateId: Long): Flow<List<SystemEvent>> =
        dao.getByAggregate(aggregateType, aggregateId).map { entities -> entities.map { it.toDomain() } }

    override fun getUnpushedEvents(limit: Int): Flow<List<SystemEvent>> =
        dao.getUnpushedEvents(limit).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(event: SystemEvent): Long =
        dao.insert(event.toEntity())

    override suspend fun markAsPushed(id: Long) =
        dao.markAsPushed(id)

    override fun getCount(): Flow<Int> =
        dao.getCount()

    private fun SystemEventEntity.toDomain() = SystemEvent(
        id = id,
        eventType = SystemEventType.entries.find { it.displayName == eventType || it.name.equals(eventType, ignoreCase = true) } ?: SystemEventType.MANUAL_ACTION,
        relatedId = aggregateId,
        relatedType = aggregateType,
        description = payload,
        timestamp = createdAt,
        metadata = payload
    )

    private fun SystemEvent.toEntity() = SystemEventEntity(
        id = id,
        eventType = eventType.name,
        aggregateType = relatedType ?: "",
        aggregateId = relatedId ?: 0,
        payload = metadata,
        createdAt = timestamp,
        pushedToAi = false
    )
}
