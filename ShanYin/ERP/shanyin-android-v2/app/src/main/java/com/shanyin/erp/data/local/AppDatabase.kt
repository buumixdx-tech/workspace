package com.shanyin.erp.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.shanyin.erp.data.local.dao.*
import com.shanyin.erp.data.local.entity.*

@Database(
    entities = [
        ChannelCustomerEntity::class,
        PointEntity::class,
        SupplierEntity::class,
        SkuEntity::class,
        EquipmentInventoryEntity::class,
        MaterialInventoryEntity::class,
        ContractEntity::class,
        VirtualContractEntity::class,
        VirtualContractStatusLogEntity::class,
        VirtualContractHistoryEntity::class,
        ExternalPartnerEntity::class,
        BankAccountEntity::class,
        BusinessEntity::class,
        SupplyChainEntity::class,
        SupplyChainItemEntity::class,
        LogisticsEntity::class,
        ExpressOrderEntity::class,
        CashFlowEntity::class,
        FinanceAccountEntity::class,
        FinancialJournalEntity::class,
        CashFlowLedgerEntity::class,
        TimeRuleEntity::class,
        SystemEventEntity::class
    ],
    version = 9,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun channelCustomerDao(): ChannelCustomerDao
    abstract fun pointDao(): PointDao
    abstract fun supplierDao(): SupplierDao
    abstract fun skuDao(): SkuDao
    abstract fun equipmentInventoryDao(): EquipmentInventoryDao
    abstract fun materialInventoryDao(): MaterialInventoryDao
    abstract fun contractDao(): ContractDao
    abstract fun virtualContractDao(): VirtualContractDao
    abstract fun virtualContractStatusLogDao(): VirtualContractStatusLogDao
    abstract fun virtualContractHistoryDao(): VirtualContractHistoryDao
    abstract fun externalPartnerDao(): ExternalPartnerDao
    abstract fun bankAccountDao(): BankAccountDao
    abstract fun businessDao(): BusinessDao
    abstract fun supplyChainDao(): SupplyChainDao
    abstract fun supplyChainItemDao(): SupplyChainItemDao
    abstract fun logisticsDao(): LogisticsDao
    abstract fun expressOrderDao(): ExpressOrderDao
    abstract fun cashFlowDao(): CashFlowDao
    abstract fun financeAccountDao(): FinanceAccountDao
    abstract fun financialJournalDao(): FinancialJournalDao
    abstract fun cashFlowLedgerDao(): CashFlowLedgerDao
    abstract fun timeRuleDao(): TimeRuleDao
    abstract fun systemEventDao(): SystemEventDao
}
