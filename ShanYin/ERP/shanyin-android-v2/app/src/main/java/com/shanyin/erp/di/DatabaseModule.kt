package com.shanyin.erp.di

import android.content.Context
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.shanyin.erp.data.local.AppDatabase
import com.shanyin.erp.data.local.FinanceAccountSeedCallback
import com.shanyin.erp.data.local.dao.*
import com.shanyin.erp.data.repository.CashFlowLedgerRepositoryImpl
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase {
        val migration1to2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE supply_chain_items ADD COLUMN deposit REAL")
            }
        }
        val migration2to3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // Normalize direction: "before" → "BEFORE", "after" → "AFTER"
                db.execSQL("UPDATE time_rules SET direction = 'BEFORE' WHERE direction = 'before'")
                db.execSQL("UPDATE time_rules SET direction = 'AFTER' WHERE direction = 'after'")
                // Normalize status: Chinese displayName → English .name
                db.execSQL("UPDATE time_rules SET status = 'INACTIVE' WHERE status = '失效'")
                db.execSQL("UPDATE time_rules SET status = 'TEMPLATE' WHERE status = '模板'")
                db.execSQL("UPDATE time_rules SET status = 'ACTIVE' WHERE status = '生效'")
                db.execSQL("UPDATE time_rules SET status = 'HAS_RESULT' WHERE status = '有结果'")
                db.execSQL("UPDATE time_rules SET status = 'ENDED' WHERE status = '结束'")
                // Normalize warning: Chinese displayName → English .name
                db.execSQL("UPDATE time_rules SET warning = 'GREEN' WHERE warning = '绿色'")
                db.execSQL("UPDATE time_rules SET warning = 'YELLOW' WHERE warning = '黄色'")
                db.execSQL("UPDATE time_rules SET warning = 'ORANGE' WHERE warning = '橙色'")
                db.execSQL("UPDATE time_rules SET warning = 'RED' WHERE warning = '红色'")
                // Normalize result: Chinese displayName → English .name
                db.execSQL("UPDATE time_rules SET result = 'COMPLIANT' WHERE result = '合规'")
                db.execSQL("UPDATE time_rules SET result = 'VIOLATION' WHERE result = '违规'")
            }
        }
        val migration3to4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // CashFlowLedgerEntity: 添加 transaction_date 字段
                db.execSQL("ALTER TABLE cash_flow_ledger ADD COLUMN transaction_date INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000)")
            }
        }
        val migration4to5 = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // 移除 transaction_date 列（与 Desktop schema 对齐）
                // SQLite 3.35+ 支持 DROP COLUMN
                db.execSQL("ALTER TABLE cash_flow_ledger DROP COLUMN transaction_date")
            }
        }
        // Versions 5→6, 6→7, 7→8 are primarily for triggering destructive migration
        // on schema hash mismatches. Since fallbackToDestructiveMigration handles
        // these, we add no-op migrations to complete the chain.
        val migration5to6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // No-op: version bump for schema hash reset
            }
        }
        val migration6to7 = object : Migration(6, 7) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // No-op: version bump for schema hash reset
            }
        }
        val migration7to8 = object : Migration(7, 8) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // No-op: version bump for schema hash reset
            }
        }
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "shanyin_erp.db"
        )
            .addMigrations(migration1to2, migration2to3, migration3to4, migration4to5, migration5to6, migration6to7, migration7to8)
            .fallbackToDestructiveMigration()
            .addCallback(FinanceAccountSeedCallback())
            .build()
    }

    @Provides
    fun provideChannelCustomerDao(db: AppDatabase) = db.channelCustomerDao()

    @Provides
    fun providePointDao(db: AppDatabase) = db.pointDao()

    @Provides
    fun provideSupplierDao(db: AppDatabase) = db.supplierDao()

    @Provides
    fun provideSkuDao(db: AppDatabase) = db.skuDao()

    @Provides
    fun provideEquipmentInventoryDao(db: AppDatabase) = db.equipmentInventoryDao()

    @Provides
    fun provideMaterialInventoryDao(db: AppDatabase) = db.materialInventoryDao()

    @Provides
    fun provideContractDao(db: AppDatabase) = db.contractDao()

    @Provides
    fun provideVirtualContractDao(db: AppDatabase) = db.virtualContractDao()

    @Provides
    fun provideVirtualContractStatusLogDao(db: AppDatabase) = db.virtualContractStatusLogDao()

    @Provides
    fun provideVirtualContractHistoryDao(db: AppDatabase) = db.virtualContractHistoryDao()

    @Provides
    fun provideExternalPartnerDao(db: AppDatabase) = db.externalPartnerDao()

    @Provides
    fun provideBankAccountDao(db: AppDatabase) = db.bankAccountDao()

    @Provides
    fun provideBusinessDao(db: AppDatabase) = db.businessDao()

    @Provides
    fun provideSupplyChainDao(db: AppDatabase) = db.supplyChainDao()

    @Provides
    fun provideSupplyChainItemDao(db: AppDatabase) = db.supplyChainItemDao()

    @Provides
    fun provideLogisticsDao(db: AppDatabase) = db.logisticsDao()

    @Provides
    fun provideExpressOrderDao(db: AppDatabase) = db.expressOrderDao()

    @Provides
    fun provideCashFlowDao(db: AppDatabase) = db.cashFlowDao()

    @Provides
    fun provideFinanceAccountDao(db: AppDatabase) = db.financeAccountDao()

    @Provides
    fun provideFinancialJournalDao(db: AppDatabase) = db.financialJournalDao()

    @Provides
    fun provideCashFlowLedgerDao(db: AppDatabase) = db.cashFlowLedgerDao()

    @Provides
    fun provideCashFlowLedgerRepository(db: AppDatabase): com.shanyin.erp.domain.repository.CashFlowLedgerRepository =
        CashFlowLedgerRepositoryImpl(db.cashFlowLedgerDao(), db.financialJournalDao())

    @Provides
    fun provideTimeRuleDao(db: AppDatabase) = db.timeRuleDao()

    @Provides
    fun provideSystemEventDao(db: AppDatabase) = db.systemEventDao()
}
