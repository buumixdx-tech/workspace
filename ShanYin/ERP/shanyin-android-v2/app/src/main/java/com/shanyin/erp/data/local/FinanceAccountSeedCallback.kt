package com.shanyin.erp.data.local

import androidx.room.RoomDatabase
import androidx.sqlite.db.SupportSQLiteDatabase
import com.shanyin.erp.data.local.entity.FinanceAccountEntity

/**
 * 财务账户种子数据回调
 *
 * 在数据库首次创建时（onCreate）自动插入预置财务科目。
 * 这些科目是 ProcessCashFlowFinanceUseCase 和财务报表的基础依赖。
 *
 * 对应 Desktop engine.py 的 ACCOUNT_CONFIG 预置科目。
 */
class FinanceAccountSeedCallback : RoomDatabase.Callback() {

    override fun onCreate(db: SupportSQLiteDatabase) {
        super.onCreate(db)

        val accounts = listOf(
            // ===== 资产类 =====
            // 1001 银行存款
            FinanceAccountSeed("银行存款", "ASSET", "DEBIT"),
            // 1002 应收账款-客户
            FinanceAccountSeed("应收账款-客户", "ASSET", "DEBIT"),
            // 1003 预付账款-供应商
            FinanceAccountSeed("预付账款-供应商", "ASSET", "DEBIT"),
            // 1004 其他应收款
            FinanceAccountSeed("其他应收款", "ASSET", "DEBIT"),
            // 1005 固定资产（原值）
            FinanceAccountSeed("固定资产-原值", "ASSET", "DEBIT"),
            // 1006 库存商品
            FinanceAccountSeed("库存商品", "ASSET", "DEBIT"),

            // ===== 负债类 =====
            // 2001 应付账款-设备款
            FinanceAccountSeed("应付账款-设备款", "LIABILITY", "CREDIT"),
            // 2002 应付账款-物料款
            FinanceAccountSeed("应付账款-物料款", "LIABILITY", "CREDIT"),
            // 2003 预收账款-客户
            FinanceAccountSeed("预收账款-客户", "LIABILITY", "CREDIT"),
            // 2004 其他应付款-押金
            FinanceAccountSeed("其他应付款-押金", "LIABILITY", "CREDIT"),
            // 2005 其他应付款-罚款
            FinanceAccountSeed("其他应付款-罚款", "LIABILITY", "CREDIT"),
            // 2006 其他应付款-保证金
            FinanceAccountSeed("其他应付款-保证金", "LIABILITY", "CREDIT"),
            // 2007 其他应付款（无二级科目，用于外部出入金 fund_type）
            FinanceAccountSeed("其他应付款", "LIABILITY", "CREDIT"),

            // ===== 权益类 =====
            // 3001 实收资本（用于外部出入金 fund_type: 股东注资/减资/分红）
            FinanceAccountSeed("实收资本", "EQUITY", "CREDIT"),

            // ===== 损益类（收入） =====
            // 4001 主营业务收入
            FinanceAccountSeed("主营业务收入", "PROFIT_LOSS", "CREDIT"),
            // 4002 其他业务收入
            FinanceAccountSeed("其他业务收入", "PROFIT_LOSS", "CREDIT"),

            // ===== 损益类（成本/费用） =====
            // 5001 主营业务成本
            FinanceAccountSeed("主营业务成本", "PROFIT_LOSS", "DEBIT"),
            // 5002 销售费用
            FinanceAccountSeed("销售费用", "PROFIT_LOSS", "DEBIT"),
            // 5003 管理费用（用于外部出金 fund_type）
            FinanceAccountSeed("管理费用", "PROFIT_LOSS", "DEBIT"),
            // 5004 财务费用
            FinanceAccountSeed("财务费用", "PROFIT_LOSS", "DEBIT")
        )

        accounts.forEach { seed ->
            db.execSQL(
                """
                INSERT INTO finance_accounts
                    (category, level1_name, level2_name, counterpart_type, counterpart_id, direction)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                arrayOf(
                    seed.category,
                    seed.name,
                    null,  // level2Name
                    null,  // counterpartType
                    null,  // counterpartId
                    seed.direction
                )
            )
        }
    }

    private data class FinanceAccountSeed(
        val name: String,
        val category: String,
        val direction: String
    )
}
