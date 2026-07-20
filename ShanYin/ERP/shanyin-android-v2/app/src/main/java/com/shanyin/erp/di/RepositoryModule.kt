package com.shanyin.erp.di

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.shanyin.erp.data.repository.*
import com.shanyin.erp.domain.repository.*
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindChannelCustomerRepository(
        impl: ChannelCustomerRepositoryImpl
    ): ChannelCustomerRepository

    @Binds
    @Singleton
    abstract fun bindPointRepository(
        impl: PointRepositoryImpl
    ): PointRepository

    @Binds
    @Singleton
    abstract fun bindSupplierRepository(
        impl: SupplierRepositoryImpl
    ): SupplierRepository

    @Binds
    @Singleton
    abstract fun bindSkuRepository(
        impl: SkuRepositoryImpl
    ): SkuRepository

    @Binds
    @Singleton
    abstract fun bindExternalPartnerRepository(
        impl: ExternalPartnerRepositoryImpl
    ): ExternalPartnerRepository

    @Binds
    @Singleton
    abstract fun bindBankAccountRepository(
        impl: BankAccountRepositoryImpl
    ): BankAccountRepository

    @Binds
    @Singleton
    abstract fun bindBusinessRepository(
        impl: BusinessRepositoryImpl
    ): BusinessRepository

    @Binds
    @Singleton
    abstract fun bindContractRepository(
        impl: ContractRepositoryImpl
    ): ContractRepository

    @Binds
    @Singleton
    abstract fun bindVirtualContractRepository(
        impl: VirtualContractRepositoryImpl
    ): VirtualContractRepository

    @Binds
    @Singleton
    abstract fun bindVCStatusLogRepository(
        impl: VCStatusLogRepositoryImpl
    ): VCStatusLogRepository

    @Binds
    @Singleton
    abstract fun bindVCHistoryRepository(
        impl: VCHistoryRepositoryImpl
    ): VCHistoryRepository

    @Binds
    @Singleton
    abstract fun bindSupplyChainRepository(
        impl: SupplyChainRepositoryImpl
    ): SupplyChainRepository

    @Binds
    @Singleton
    abstract fun bindSupplyChainItemRepository(
        impl: SupplyChainItemRepositoryImpl
    ): SupplyChainItemRepository

    @Binds
    @Singleton
    abstract fun bindEquipmentInventoryRepository(
        impl: EquipmentInventoryRepositoryImpl
    ): EquipmentInventoryRepository

    @Binds
    @Singleton
    abstract fun bindMaterialInventoryRepository(
        impl: MaterialInventoryRepositoryImpl
    ): MaterialInventoryRepository

    @Binds
    @Singleton
    abstract fun bindLogisticsRepository(
        impl: LogisticsRepositoryImpl
    ): LogisticsRepository

    @Binds
    @Singleton
    abstract fun bindExpressOrderRepository(
        impl: ExpressOrderRepositoryImpl
    ): ExpressOrderRepository

    @Binds
    @Singleton
    abstract fun bindFinanceAccountRepository(
        impl: FinanceAccountRepositoryImpl
    ): FinanceAccountRepository

    @Binds
    @Singleton
    abstract fun bindCashFlowRepository(
        impl: CashFlowRepositoryImpl
    ): CashFlowRepository

    @Binds
    @Singleton
    abstract fun bindFinancialJournalRepository(
        impl: FinancialJournalRepositoryImpl
    ): FinancialJournalRepository

    @Binds
    @Singleton
    abstract fun bindTimeRuleRepository(
        impl: TimeRuleRepositoryImpl
    ): TimeRuleRepository

    @Binds
    @Singleton
    abstract fun bindSystemEventRepository(
        impl: SystemEventRepositoryImpl
    ): SystemEventRepository
}

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideGson(): Gson = GsonBuilder()
        .registerTypeAdapter(DesktopVCElement::class.java, DesktopVCElementDeserializer())
        .create()
}
