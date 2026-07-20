package com.shanyin.erp.domain.repository

import com.shanyin.erp.domain.model.*
import kotlinx.coroutines.flow.Flow

interface ChannelCustomerRepository {
    fun getAll(): Flow<List<ChannelCustomer>>
    suspend fun getById(id: Long): ChannelCustomer?
    fun getByIdFlow(id: Long): Flow<ChannelCustomer?>
    suspend fun insert(customer: ChannelCustomer): Long
    suspend fun update(customer: ChannelCustomer)
    suspend fun delete(customer: ChannelCustomer)
    suspend fun deleteById(id: Long)
    fun getCount(): Flow<Int>
}

interface PointRepository {
    fun getAll(): Flow<List<Point>>
    suspend fun getById(id: Long): Point?
    fun getByCustomerId(customerId: Long): Flow<List<Point>>
    fun getBySupplierId(supplierId: Long): Flow<List<Point>>
    suspend fun insert(point: Point): Long
    suspend fun update(point: Point)
    suspend fun delete(point: Point)
    fun getCount(): Flow<Int>
}

interface SupplierRepository {
    fun getAll(): Flow<List<Supplier>>
    suspend fun getById(id: Long): Supplier?
    fun getByCategory(category: SupplierCategory): Flow<List<Supplier>>
    suspend fun insert(supplier: Supplier): Long
    suspend fun update(supplier: Supplier)
    suspend fun delete(supplier: Supplier)
    fun getCount(): Flow<Int>
}

interface SkuRepository {
    fun getAll(): Flow<List<Sku>>
    suspend fun getById(id: Long): Sku?
    fun getBySupplierId(supplierId: Long): Flow<List<Sku>>
    fun getByTypeLevel1(type: SkuType): Flow<List<Sku>>
    suspend fun insert(sku: Sku): Long
    suspend fun update(sku: Sku)
    suspend fun delete(sku: Sku)
    fun getCount(): Flow<Int>
}

interface ExternalPartnerRepository {
    fun getAll(): Flow<List<ExternalPartner>>
    suspend fun getById(id: Long): ExternalPartner?
    suspend fun insert(partner: ExternalPartner): Long
    suspend fun update(partner: ExternalPartner)
    suspend fun delete(partner: ExternalPartner)
    fun getCount(): Flow<Int>
}

interface BankAccountRepository {
    fun getAll(): Flow<List<BankAccount>>
    suspend fun getById(id: Long): BankAccount?
    fun getByOwnerType(ownerType: OwnerType): Flow<List<BankAccount>>
    suspend fun getDefaultByOwnerType(ownerType: OwnerType): BankAccount?
    suspend fun insert(account: BankAccount): Long
    suspend fun update(account: BankAccount)
    suspend fun delete(account: BankAccount)
    fun getCount(): Flow<Int>
    /**
     * 查询银行账户余额
     * 余额 = 收款流入 - 付款流出
     * = SUM(amount WHERE payee_account_id = id) - SUM(amount WHERE payer_account_id = id)
     */
    suspend fun getBalanceById(accountId: Long): Double
    /** 查询银行账户总流入 */
    suspend fun getTotalInflowById(accountId: Long): Double
    /** 查询银行账户总流出 */
    suspend fun getTotalOutflowById(accountId: Long): Double
    /**
     * 直接获取银行账户的原始 accountInfo JSON（绕过 domain 解析）
     * 用于 CreateCashFlowUseCase 等场景，当 domain accountInfo 解析失败时备用
     */
    suspend fun getRawAccountInfo(accountId: Long): String?
}
