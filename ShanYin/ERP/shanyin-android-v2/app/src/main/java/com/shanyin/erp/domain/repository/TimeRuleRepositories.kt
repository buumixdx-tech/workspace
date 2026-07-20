package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.*
import kotlinx.coroutines.flow.Flow

interface TimeRuleRepository {
    fun getAll(): Flow<List<TimeRule>>
    suspend fun getById(id: Long): TimeRule?
    fun getByRelatedIdAndType(relatedId: Long, relatedType: RelatedType): Flow<List<TimeRule>>
    fun getByRelatedType(relatedType: RelatedType): Flow<List<TimeRule>>
    fun getByStatus(status: RuleStatus): Flow<List<TimeRule>>
    fun getByWarning(warning: WarningLevel): Flow<List<TimeRule>>
    suspend fun insert(rule: TimeRule): Long
    suspend fun update(rule: TimeRule)
    suspend fun delete(rule: TimeRule)
    fun getCount(): Flow<Int>
    /** 查询模板规则（用于继承复制） */
    suspend fun getTemplateRules(relatedId: Long, relatedType: RelatedType, inherit: InheritLevel): List<TimeRule>
    /** 规则引擎：查询所有非模板状态的规则 */
    suspend fun getAllNonTemplate(): List<TimeRule>
}

interface SystemEventRepository {
    fun getAll(): Flow<List<SystemEvent>>
    suspend fun getById(id: Long): SystemEvent?
    fun getByEventType(eventType: SystemEventType): Flow<List<SystemEvent>>
    fun getByAggregate(aggregateType: String, aggregateId: Long): Flow<List<SystemEvent>>
    fun getUnpushedEvents(limit: Int = 100): Flow<List<SystemEvent>>
    suspend fun insert(event: SystemEvent): Long
    suspend fun markAsPushed(id: Long)
    fun getCount(): Flow<Int>
}
