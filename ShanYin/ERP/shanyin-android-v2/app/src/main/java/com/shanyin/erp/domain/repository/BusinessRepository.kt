package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.Business
import com.shanyin.erp.domain.model.BusinessStatus
import com.shanyin.erp.domain.model.Contract
import kotlinx.coroutines.flow.Flow

interface BusinessRepository {
    fun getAll(): Flow<List<Business>>
    suspend fun getById(id: Long): Business?
    fun getByIdFlow(id: Long): Flow<Business?>
    fun getByCustomerId(customerId: Long): Flow<List<Business>>
    fun getByStatus(status: BusinessStatus): Flow<List<Business>>
    suspend fun insert(business: Business): Long
    suspend fun update(business: Business)
    suspend fun delete(business: Business)
    fun getCount(): Flow<Int>
}

interface ContractRepository {
    fun getAll(): Flow<List<Contract>>
    suspend fun getById(id: Long): Contract?
    suspend fun getByContractNumber(contractNumber: String): Contract?
    fun getByStatus(status: String): Flow<List<Contract>>
    suspend fun insert(contract: Contract): Long
    suspend fun update(contract: Contract)
    suspend fun delete(contract: Contract)
    fun getCount(): Flow<Int>
}
