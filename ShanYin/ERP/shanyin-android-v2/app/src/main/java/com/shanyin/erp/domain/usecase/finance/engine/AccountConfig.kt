package com.shanyin.erp.domain.usecase.finance.engine

import com.shanyin.erp.domain.model.CashFlowType

/**
 * Desktop ACCOUNT_CONFIG 的 Mobile 等价实现
 *
 * 定义每种 CashFlowType 对应的复式记账分录列表（一张凭证可含多条分录）
 * 运行时由 [AccountResolver] 将科目名称解析为数据库中的 accountId
 *
 * 对应 Desktop engine.py 的 ACCOUNT_CONFIG 字典和 process_cash_flow_finance() 分录生成逻辑
 */
object AccountConfig {

    // ==================== 科目名称常量（对应 finance_accounts 表的 level1Name） ====================

    /** 银行存款-默认账户 */
    const val BANK_DEFAULT = "银行存款"

    /** 应付账款-设备款 */
    const val AP_EQUIPMENT = "应付账款-设备款"

    /** 应付账款-物料款 */
    const val AP_MATERIAL = "应付账款-物料款"

    /** 其他应付款-押金 */
    const val DEPOSIT_PAYABLE = "其他应付款-押金"

    /** 应收账款-客户 */
    const val AR_CUSTOMER = "应收账款-客户"

    /** 预付账款-供应商 */
    const val PREPAYMENT = "预付账款-供应商"

    /** 预收账款-客户 */
    const val PRE_COLLECTION = "预收账款-客户"

    /** 其他应付款-罚款 */
    const val PENALTY_PAYABLE = "其他应付款-罚款"

    /** 主营业务成本 */
    const val COST_OF_GOODS = "主营业务成本"

    /** 营业外收入-罚金 */
    const val NON_OP_REVENUE_PENALTY = "营业外收入-罚金"

    /** 营业外支出-罚金 */
    const val NON_OP_COST_PENALTY = "营业外支出-罚金"

    // ==================== 物流财务专用科目 ====================

    /** 固定资产-原值 */
    const val FIXED_ASSET = "固定资产-原值"

    /** 库存商品 */
    const val INVENTORY = "库存商品"

    /** 主营业务收入 */
    const val SALES_REVENUE = "主营业务收入"

    /** 销售费用 */
    const val SALES_EXPENSE = "销售费用"

    // ==================== 通用常量 ====================

    /** 最小交易金额阈值（用于浮点数比较） */
    const val MIN_AMOUNT_THRESHOLD = 0.01

    // ==================== 分录条目 ====================

    /**
     * 单条分录
     * @param account 科目名称
     * @param debit 借方金额（=0时不写入借方）
     * @param credit 贷方金额（=0时不写入贷方）
     * @param summary 摘要
     * @param counterpartyType 对方类型（ BANK_ACCOUNT / CUSTOMER / SUPPLIER ），用于解析 cp_id
     * @param counterpartyId 对方ID（BankAccount/Customer/Supplier 的 ID）
     */
    data class JournalEntry(
        val account: String,
        val debit: Double = 0.0,
        val credit: Double = 0.0,
        val summary: String,
        val counterpartyType: String? = null,  // BANK_ACCOUNT, CUSTOMER, SUPPLIER
        val counterpartyId: Long? = null
    ) {
        init {
            require(!(debit > 0 && credit > 0)) { "debit and credit cannot both be > 0" }
        }
    }

    /**
     * 一组借贷平衡的分录
     * @param entries 分录列表
     * @param isIncome true=资金流入(我们收款), false=资金流出(我们付款)
     */
    data class JournalEntryGroup(
        val entries: List<JournalEntry>,
        val isIncome: Boolean
    )

    // ==================== 完整分录生成 ====================

    /**
     * 根据 CashFlowType 生成完整的复式记账分录组
     *
     * 核心逻辑（完全对标 Desktop process_cash_flow_finance engine.py lines 196-263）：
     *
     * 约定：
     * - isIncome=true 表示资金流入（我们收款），付款方是客户，收款方是我们
     * - isIncome=false 表示资金流出（我们付款），付款方是我们，收款方是供应商
     *
     * isIncome 由调用方根据 VC 类型判断：
     * - MATERIAL_SUPPLY → isIncome=true（客户付款给我们）
     * - 采购类 (EQUIPMENT_PROCUREMENT 等) → isIncome=false（我们付款给供应商）
     * - RETURN: 视 return_direction 而定
     *
     * @param type CashFlow 类型
     * @param amount 交易金额
     * @param isIncome 是否为收入（资金流入）
     * @param arApAmount 应收/应付核销金额（仅 PREPAYMENT/FULFILLMENT 使用）
     * @param preAmount 计入预收/预付金额（仅 PREPAYMENT/FULFILLMENT 使用，amount - arApAmount）
     * @param cpType 对方类型 ("CUSTOMER" / "SUPPLIER" / "BANK_ACCOUNT")
     * @param cpId 对方ID
     * @param bankAccountId 我方银行账户ID（用于 CASH 分录）
     * @param summary 摘要
     * @return 分录组
     */
    fun getJournalEntries(
        type: CashFlowType,
        amount: Double,
        isIncome: Boolean,
        arApAmount: Double = 0.0,
        preAmount: Double = 0.0,
        cpType: String? = null,
        cpId: Long? = null,
        bankAccountId: Long? = null,
        summary: String = ""
    ): JournalEntryGroup {
        val entries = mutableListOf<JournalEntry>()

        when (type) {
            CashFlowType.PREPAYMENT, CashFlowType.PERFORMANCE -> {
                if (isIncome) {
                    // 收款时（客户付款给我们）
                    // 1. 借: CASH
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                debit = amount,
                                credit = 0.0,
                                summary = "收到资金 ($type)",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                    // 2. 贷: AR（核销应收）/ PRE_COLLECTION（计入预收）
                    if (arApAmount > 0.01) {
                        entries.add(
                            JournalEntry(
                                account = AR_CUSTOMER,
                                credit = arApAmount,
                                summary = "核销应收",
                                counterpartyType = cpType,
                                counterpartyId = cpId
                            )
                        )
                    }
                    if (preAmount > 0.01) {
                        entries.add(
                            JournalEntry(
                                account = PRE_COLLECTION,
                                credit = preAmount,
                                summary = "计入预收",
                                counterpartyType = cpType,
                                counterpartyId = cpId
                            )
                        )
                    }
                } else {
                    // 付款时（我们付款给供应商）
                    if (arApAmount > 0.01) {
                        entries.add(
                            JournalEntry(
                                account = AP_EQUIPMENT,
                                debit = arApAmount,
                                summary = "核销应付",
                                counterpartyType = cpType,
                                counterpartyId = cpId
                            )
                        )
                    }
                    if (preAmount > 0.01) {
                        entries.add(
                            JournalEntry(
                                account = PREPAYMENT,
                                debit = preAmount,
                                summary = "计入预付",
                                counterpartyType = cpType,
                                counterpartyId = cpId
                            )
                        )
                    }
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                credit = amount,
                                summary = "支付资金 ($type)",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                }
            }

            CashFlowType.DEPOSIT -> {
                if (isIncome) {
                    // 收到押金
                    // 借: CASH
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                debit = amount,
                                summary = "收到押金",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                    // 贷: DEPOSIT_PAYABLE
                    entries.add(
                        JournalEntry(
                            account = DEPOSIT_PAYABLE,
                            credit = amount,
                            summary = "押金入账",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                } else {
                    // 支付押金
                    entries.add(
                        JournalEntry(
                            account = "其他应收款-押金", // deposit receivable
                            debit = amount,
                            summary = "支付押金",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                credit = amount,
                                summary = "支付押金",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                }
            }

            CashFlowType.DEPOSIT_REFUND -> {
                if (isIncome) {
                    // 收回押金
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                debit = amount,
                                summary = "收回押金",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                    entries.add(
                        JournalEntry(
                            account = "其他应收款-押金",
                            credit = amount,
                            summary = "收回押金冲减",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                } else {
                    // 退还押金
                    entries.add(
                        JournalEntry(
                            account = DEPOSIT_PAYABLE,
                            debit = amount,
                            summary = "退还押金",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                credit = amount,
                                summary = "转账退押金",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                }
            }

            CashFlowType.PENALTY -> {
                if (isIncome) {
                    // 收到罚金
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                debit = amount,
                                summary = "收到罚金",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                    entries.add(
                        JournalEntry(
                            account = NON_OP_REVENUE_PENALTY,
                            credit = amount,
                            summary = "罚金收入",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                } else {
                    // 交纳罚金
                    entries.add(
                        JournalEntry(
                            account = NON_OP_COST_PENALTY,
                            debit = amount,
                            summary = "罚金支出",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                credit = amount,
                                summary = "交纳罚金",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                }
            }

            CashFlowType.REFUND -> {
                if (isIncome) {
                    // 收到退款
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                debit = amount,
                                summary = "收到退款",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                    entries.add(
                        JournalEntry(
                            account = AP_EQUIPMENT,
                            credit = amount,
                            summary = "核销应付余额",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                } else {
                    // 支付退款
                    entries.add(
                        JournalEntry(
                            account = AR_CUSTOMER,
                            debit = amount,
                            summary = "支付货款使应收归零",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                credit = amount,
                                summary = "转账退还货款",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                }
            }

            CashFlowType.OFFSET_INFLOW -> {
                // 冲抵入金：提取预收冲抵 AR
                if (isIncome) {
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                debit = amount,
                                summary = "溢收录入",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                    entries.add(
                        JournalEntry(
                            account = PRE_COLLECTION,
                            credit = amount,
                            summary = "手动录入预收",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                } else {
                    entries.add(
                        JournalEntry(
                            account = PREPAYMENT,
                            debit = amount,
                            summary = "手动录入预付",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    bankAccountId?.let {
                        entries.add(
                            JournalEntry(
                                account = BANK_DEFAULT,
                                credit = amount,
                                summary = "支付资金转入预付",
                                counterpartyType = "BANK_ACCOUNT",
                                counterpartyId = it
                            )
                        )
                    }
                }
            }

            CashFlowType.OFFSET_OUTFLOW -> {
                // 冲抵支付：用预付核销应付
                if (isIncome) {
                    // 借: PRE_COLLECTION, 贷: AR
                    entries.add(
                        JournalEntry(
                            account = PRE_COLLECTION,
                            debit = amount,
                            summary = "提取预收冲抵",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    entries.add(
                        JournalEntry(
                            account = AR_CUSTOMER,
                            credit = amount,
                            summary = "冲抵核销应收",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                } else {
                    // 借: AP, 贷: PREPAYMENT
                    entries.add(
                        JournalEntry(
                            account = AP_EQUIPMENT,
                            debit = amount,
                            summary = "冲抵核销应付",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                    entries.add(
                        JournalEntry(
                            account = PREPAYMENT,
                            credit = amount,
                            summary = "扣减预付冲抵",
                            counterpartyType = cpType,
                            counterpartyId = cpId
                        )
                    )
                }
            }

            CashFlowType.DEPOSIT_OFFSET_IN -> {
                // Desktop遗留bug：该类型不生成任何凭证分录
                // 业务含义：押金冲抵入金（押金与货款互冲）
                // 此类型在Desktop中虽有if/elif但实际未接入
            }
        }

        return JournalEntryGroup(entries = entries, isIncome = isIncome)
    }
}
