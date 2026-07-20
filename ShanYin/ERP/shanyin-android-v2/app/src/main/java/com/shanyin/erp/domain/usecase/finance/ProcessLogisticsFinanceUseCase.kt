package com.shanyin.erp.domain.usecase.finance

import com.shanyin.erp.data.local.dao.FinancialJournalDao
import com.shanyin.erp.data.local.entity.FinancialJournalEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.LogisticsRepository
import com.shanyin.erp.domain.repository.MaterialInventoryRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.engine.AccountConfig
import com.shanyin.erp.domain.usecase.finance.engine.AccountResolver
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 物流状态变更 → 生成财务凭证
 *
 * 对应 Desktop process_logistics_finance()
 *
 * 触发时机：
 * - 物流状态变为 SIGNED（签收）时，自动生成凭证
 * - 或通过 TriggerFinanceUseCase 手动触发
 *
 * 凭证生成规则（按 VC 类型和物流状态）：
 *
 * SIGNED（签收时）：
 * - EQUIPMENT_PROCUREMENT:     借: 固定资产-原值,       贷: 应付账款-设备款
 * - EQUIPMENT_STOCK:           借: 库存商品,           贷: 应付账款-设备款
 * - MATERIAL_PROCUREMENT:       借: 库存商品,           贷: 应付账款-物料款
 * - MATERIAL_SUPPLY:            借: 应收账款-客户,        贷: 主营业务收入
 *                               借: 主营业务成本,         贷: 库存商品  （成本结转）
 *
 * COMPLETED（完成时，仅退货）：
 * - RETURN CUSTOMER_TO_US:      借: 主营业务收入,         贷: 应收账款-客户  （退货收入冲减）
 *                               + 物流费分录（根据 logistics_bearer 角色）
 * - RETURN US_TO_SUPPLIER:      借: 应付账款-设备款,      贷: 库存商品  （退货）
 *                               + 物流费分录
 */
@Singleton
class ProcessLogisticsFinanceUseCase @Inject constructor(
    private val logisticsRepo: LogisticsRepository,
    private val vcRepo: VirtualContractRepository,
    private val journalDao: FinancialJournalDao,
    private val accountResolver: AccountResolver,
    private val materialInventoryRepo: MaterialInventoryRepository
) {
    suspend operator fun invoke(logisticsId: Long, force: Boolean = false): Long {
        val logistics = logisticsRepo.getById(logisticsId)
            ?: throw IllegalArgumentException("Logistics not found: id=$logisticsId")

        if (logistics.financeTriggered && !force) {
            return logisticsId
        }

        val vc = vcRepo.getById(logistics.virtualContractId)
            ?: throw IllegalArgumentException("VC not found for logistics: id=$logisticsId")

        when (logistics.status) {
            LogisticsStatus.SIGNED -> createSignedEntries(logistics, vc)
            LogisticsStatus.COMPLETED -> createCompletedEntries(logistics, vc)
            else -> { /* 其他状态不生成凭证 */ }
        }

        logisticsRepo.update(logistics.copy(financeTriggered = true))
        return logisticsId
    }

    private suspend fun createSignedEntries(logistics: Logistics, vc: VirtualContract) {
        val transactionDate = logistics.timestamp
        val vcId = vc.id

        when (vc.type) {
            VCType.EQUIPMENT_PROCUREMENT,
            VCType.EQUIPMENT_STOCK -> {
                // 借: 固定资产-原值, 贷: 应付账款-设备款
                createJournalPair(
                    logisticsId = logistics.id,
                    debitAccount = AccountConfig.FIXED_ASSET,
                    creditAccount = AccountConfig.AP_EQUIPMENT,
                    amount = vc.depositInfo.totalAmount,
                    transactionDate = transactionDate,
                    summary = "设备采购入库 ${vc.description ?: ""} VC#${vcId}",
                    vcId = vcId
                )
            }

            VCType.MATERIAL_PROCUREMENT -> {
                // 借: 库存商品, 贷: 应付账款-物料款
                createJournalPair(
                    logisticsId = logistics.id,
                    debitAccount = AccountConfig.INVENTORY,
                    creditAccount = AccountConfig.AP_MATERIAL,
                    amount = vc.depositInfo.totalAmount,
                    transactionDate = transactionDate,
                    summary = "物料采购入库 ${vc.description ?: ""} VC#${vcId}",
                    vcId = vcId
                )
            }

            VCType.MATERIAL_SUPPLY -> {
                // 第1组：确认收入
                // 借: 应收账款-客户, 贷: 主营业务收入
                createJournalPair(
                    logisticsId = logistics.id,
                    debitAccount = AccountConfig.AR_CUSTOMER,
                    creditAccount = AccountConfig.SALES_REVENUE,
                    amount = vc.depositInfo.totalAmount,
                    transactionDate = transactionDate,
                    summary = "物料供应确认收入 ${vc.description ?: ""} VC#${vcId}",
                    vcId = vcId
                )

                // 第2组：结转销售成本（Desktop: items_cost > 0 时写入）
                // 计算销货成本：从 MaterialInventory 按 SKU 查找加权平均采购价
                val itemsCost = calculateSupplyCost(vc)
                if (itemsCost > AccountConfig.MIN_AMOUNT_THRESHOLD) {
                    // 借: 主营业务成本, 贷: 库存商品
                    createJournalPair(
                        logisticsId = logistics.id,
                        debitAccount = AccountConfig.COST_OF_GOODS,
                        creditAccount = AccountConfig.INVENTORY,
                        amount = itemsCost,
                        transactionDate = transactionDate,
                        summary = "结转物料销售成本 VC#${vcId}",
                        vcId = vcId
                    )
                }
            }

            VCType.RETURN -> {
                // 退货在 COMPLETED 时处理
            }

            VCType.INVENTORY_ALLOCATION -> {
                // 库存拨付无货款概念
            }
        }
    }

    /**
     * 计算 MATERIAL_SUPPLY 的销货成本
     *
     * 逻辑：按 Desktop get_logistics_finance_context() 的 items_cost 计算方式：
     * - 从 MaterialInventory 读取各 SKU 的加权平均采购价（averagePrice）
     * - × 对应 supply quantity
     *
     * 如果 MaterialInventory 中无记录，则使用 vc.elements 的 unitPrice（简化）
     */
    private suspend fun calculateSupplyCost(vc: VirtualContract): Double {
        val validElements = vc.elements.filter { it.quantity > AccountConfig.MIN_AMOUNT_THRESHOLD }
        if (validElements.isEmpty()) return 0.0

        // 批量查询所有 SKU 的库存，避免 N+1 查询
        val skuIds = validElements.map { it.skuId }
        val inventories = materialInventoryRepo.getBySkuIds(skuIds).associateBy { it.skuId }

        var totalCost = 0.0
        for (element in validElements) {
            val inventory = inventories[element.skuId]
            val costPrice = if (inventory != null && inventory.averagePrice > AccountConfig.MIN_AMOUNT_THRESHOLD) {
                inventory.averagePrice
            } else {
                // 降级：用 vc.elements 的 unitPrice（此为供应单价，非采购成本）
                // 注：理想情况应在 SupplyChainItem 中存储采购成本基准
                element.unitPrice
            }
            totalCost += element.quantity * costPrice
        }
        return totalCost
    }

    /**
     * 安全解析 LogisticsBearer 枚举，避免 DB 中的非法值导致崩溃
     * 默认返回 SENDER（与 Desktop 行为一致）
     */
    private fun safeBearer(value: String?): LogisticsBearer {
        return try {
            value?.let { LogisticsBearer.valueOf(it) } ?: LogisticsBearer.SENDER
        } catch (e: IllegalArgumentException) {
            LogisticsBearer.SENDER
        }
    }

    private suspend fun createCompletedEntries(logistics: Logistics, vc: VirtualContract) {
        if (vc.type != VCType.RETURN) return

        val transactionDate = logistics.timestamp
        val vcId = vc.id

        // 直接从 VC 域模型读取退货元数据（repository 层已解析）
        val returnDirection = vc.returnDirection?.name ?: return  // 无方向则跳过
        val goodsAmount = vc.goodsAmount
        val logisticsCost = vc.logisticsCost
        val logisticsBearer = safeBearer(vc.logisticsBearer?.name)

        when (returnDirection) {
            "CUSTOMER_TO_US" -> {
                // 客户退货给我方：冲减收入 + 物样入库 + 物流费处理

                // 第1组：冲减收入（Dr收入, Cr应收）
                if (goodsAmount > AccountConfig.MIN_AMOUNT_THRESHOLD) {
                    createJournalPair(
                        logisticsId = logistics.id,
                        debitAccount = AccountConfig.SALES_REVENUE,
                        creditAccount = AccountConfig.AR_CUSTOMER,
                        amount = goodsAmount,
                        transactionDate = transactionDate,
                        summary = "退货收入冲减 ${vc.description ?: ""} VC#$vcId",
                        vcId = vcId
                    )
                }

                // 第2组：物流费（按 bearer 角色决定分录）
                createLogisticsFeeEntries(
                    logistics = logistics,
                    vcId = vcId,
                    direction = ReturnDirection.CUSTOMER_TO_US,
                    bearer = logisticsBearer,
                    logisticsCost = logisticsCost,
                    transactionDate = transactionDate
                )
            }

            "US_TO_SUPPLIER" -> {
                // 我方向供应商退货：冲减库存和应付 + 物流费

                // 第1组：冲减库存（Dr应付, Cr库存）
                if (goodsAmount > AccountConfig.MIN_AMOUNT_THRESHOLD) {
                    createJournalPair(
                        logisticsId = logistics.id,
                        debitAccount = AccountConfig.AP_EQUIPMENT,
                        creditAccount = AccountConfig.INVENTORY,
                        amount = goodsAmount,
                        transactionDate = transactionDate,
                        summary = "退货冲销应付 ${vc.description ?: ""} VC#$vcId",
                        vcId = vcId
                    )
                }

                // 第2组：物流费
                createLogisticsFeeEntries(
                    logistics = logistics,
                    vcId = vcId,
                    direction = ReturnDirection.US_TO_SUPPLIER,
                    bearer = logisticsBearer,
                    logisticsCost = logisticsCost,
                    transactionDate = transactionDate
                )
            }
        }
    }

    /**
     * 退货物流费分录
     *
     * 对应 Desktop lines 176-192:
     * - CUSTOMER_TO_US + RECEIVER(收方承担): Dr 销售费用, Cr 应收账款-客户（物流费补偿）
     * - CUSTOMER_TO_US + SENDER(发方承担):   Dr 应收账款-客户, Cr 销售费用（收回代垫）
     * - US_TO_SUPPLIER + SENDER:           Dr 销售费用, Cr 应付账款-设备款（我方承担）
     * - US_TO_SUPPLIER + RECEIVER:          Dr 应付账款-设备款, Cr 销售费用（代垫冲销）
     */
    private suspend fun createLogisticsFeeEntries(
        logistics: Logistics,
        vcId: Long,
        direction: ReturnDirection,
        bearer: LogisticsBearer,
        logisticsCost: Double,
        transactionDate: Long
    ) {
        if (logisticsCost < AccountConfig.MIN_AMOUNT_THRESHOLD) return

        when (direction) {
            ReturnDirection.CUSTOMER_TO_US -> {
                when (bearer) {
                    LogisticsBearer.RECEIVER -> {
                        // 我方承担运费：Dr 销售费用, Cr 应收账款-客户（应收客户物流费补偿）
                        createJournalPair(
                            logisticsId = logistics.id,
                            debitAccount = AccountConfig.SALES_EXPENSE,
                            creditAccount = AccountConfig.AR_CUSTOMER,
                            amount = logisticsCost,
                            transactionDate = transactionDate,
                            summary = "退货物流费-我方承担 VC#$vcId",
                            vcId = vcId
                        )
                    }
                    LogisticsBearer.SENDER -> {
                        // 客户自付：Dr 应收账款-客户, Cr 销售费用（收回代垫款）
                        createJournalPair(
                            logisticsId = logistics.id,
                            debitAccount = AccountConfig.AR_CUSTOMER,
                            creditAccount = AccountConfig.SALES_EXPENSE,
                            amount = logisticsCost,
                            transactionDate = transactionDate,
                            summary = "退货物流费-客户自付收回 VC#$vcId",
                            vcId = vcId
                        )
                    }
                }
            }
            ReturnDirection.US_TO_SUPPLIER -> {
                when (bearer) {
                    LogisticsBearer.SENDER -> {
                        // 我方承担：Dr 销售费用, Cr 应付账款-设备款
                        createJournalPair(
                            logisticsId = logistics.id,
                            debitAccount = AccountConfig.SALES_EXPENSE,
                            creditAccount = AccountConfig.AP_EQUIPMENT,
                            amount = logisticsCost,
                            transactionDate = transactionDate,
                            summary = "退货物流费-我方承担 VC#$vcId",
                            vcId = vcId
                        )
                    }
                    LogisticsBearer.RECEIVER -> {
                        // 代垫供应商：Dr 应付账款-设备款, Cr 销售费用（冲销代垫）
                        createJournalPair(
                            logisticsId = logistics.id,
                            debitAccount = AccountConfig.AP_EQUIPMENT,
                            creditAccount = AccountConfig.SALES_EXPENSE,
                            amount = logisticsCost,
                            transactionDate = transactionDate,
                            summary = "退货物流费-代垫供应商 VC#$vcId",
                            vcId = vcId
                        )
                    }
                }
            }
        }
    }

    private suspend fun createJournalPair(
        logisticsId: Long,
        debitAccount: String,
        creditAccount: String,
        amount: Double,
        transactionDate: Long,
        summary: String,
        vcId: Long
    ) {
        if (amount < AccountConfig.MIN_AMOUNT_THRESHOLD) return

        val debitId = accountResolver.resolveId(debitAccount)
            ?: throw IllegalStateException("Finance account not found: $debitAccount. Please seed finance_accounts table.")
        val creditId = accountResolver.resolveId(creditAccount)
            ?: throw IllegalStateException("Finance account not found: $creditAccount. Please seed finance_accounts table.")

        // 凭证号格式: LOG-{logistics_id}-{timestamp}
        val voucherNo = "LOG-${logisticsId}-${String.format("%06X", logisticsId)}"

        val debitEntry = FinancialJournalEntity(
            voucherNo = voucherNo,
            accountId = debitId,
            debit = amount,
            credit = 0.0,
            summary = summary,
            refType = RefType.LOGISTICS.name,
            refId = logisticsId,
            refVcId = vcId,
            transactionDate = transactionDate
        )

        val creditEntry = FinancialJournalEntity(
            voucherNo = voucherNo,
            accountId = creditId,
            debit = 0.0,
            credit = amount,
            summary = summary,
            refType = RefType.LOGISTICS.name,
            refId = logisticsId,
            refVcId = vcId,
            transactionDate = transactionDate
        )

        journalDao.insert(debitEntry)
        journalDao.insert(creditEntry)
    }
}
