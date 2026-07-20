package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.ExpressOrderRepository
import com.shanyin.erp.domain.repository.LogisticsRepository
import com.shanyin.erp.domain.repository.MaterialInventoryRepository
import com.shanyin.erp.domain.repository.PointRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import com.shanyin.erp.domain.usecase.finance.ProcessLogisticsFinanceUseCase
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

// ==================== Logistics Use Cases ====================

class GenerateExpressOrderSuggestionsUseCase @Inject constructor(
    private val pointRepository: PointRepository
) {
    /**
     * 根据 VC 的 elements 生成快递单建议
     *
     * 新版 VC elements 格式：每个 element = 1 快递单
     * - element.shippingPointId / receivingPointId → 发货/收货点位
     * - element.skuId / skuName / quantity → 货品明细
     *
     * 对应 Desktop "初始化物流方案建议" 逻辑，但更简化：element 直接映射为 express order
     *
     * @return List<ExpressOrderSuggestion> 快递单建议列表（未保存）
     */
    suspend operator fun invoke(vc: VirtualContract): List<ExpressOrderSuggestion> {
        if (vc.elements.isEmpty()) return emptyList()

        return vc.elements.mapIndexed { index, element ->
            // 查询点位信息
            val shippingPoint = element.shippingPointId?.let { pointRepository.getById(it) }
            val receivingPoint = element.receivingPointId?.let { pointRepository.getById(it) }

            // 生成快递单号（临时，提交时可修改）
            val timestamp = System.currentTimeMillis()
            val trackingPrefix = when (vc.type) {
                VCType.RETURN -> "RET"
                VCType.MATERIAL_SUPPLY -> "SUP"
                else -> "EXP"
            }
            val trackingNumber = "$trackingPrefix${timestamp.toString().takeLast(8)}${index}"

            // 构建地址信息
            val addressInfo = AddressInfo(
                shippingPointId = element.shippingPointId,
                shippingPointName = shippingPoint?.name ?: "",
                shippingAddress = shippingPoint?.receivingAddress ?: shippingPoint?.address ?: "",
                receivingPointId = element.receivingPointId,
                receivingPointName = receivingPoint?.name ?: "",
                receivingAddress = receivingPoint?.receivingAddress ?: receivingPoint?.address ?: ""
            )

            // 货品明细（每个 element 一个 SKU）
            val expressItem = ExpressItem(
                skuId = element.skuId,
                skuName = element.skuName,
                quantity = element.quantity
            )

            ExpressOrderSuggestion(
                trackingNumber = trackingNumber,
                items = listOf(expressItem),
                addressInfo = addressInfo,
                elementId = element.id
            )
        }
    }
}

/**
 * 快递单建议（未保存）
 */
data class ExpressOrderSuggestion(
    val trackingNumber: String,
    val items: List<ExpressItem>,
    val addressInfo: AddressInfo,
    val elementId: String  // 对应的 VC element ID
)

class GetAllLogisticsUseCase @Inject constructor(
    private val repository: LogisticsRepository
) {
    operator fun invoke(): Flow<List<Logistics>> = repository.getAll()
}

class GetLogisticsByIdUseCase @Inject constructor(
    private val repository: LogisticsRepository
) {
    suspend operator fun invoke(id: Long): Logistics? = repository.getById(id)
}

class GetLogisticsByVcUseCase @Inject constructor(
    private val repository: LogisticsRepository
) {
    operator fun invoke(vcId: Long): Flow<List<Logistics>> = repository.getByVcId(vcId)
}

class GetLogisticsByStatusUseCase @Inject constructor(
    private val repository: LogisticsRepository
) {
    operator fun invoke(status: LogisticsStatus): Flow<List<Logistics>> = repository.getByStatus(status)
}

class CreateLogisticsUseCase @Inject constructor(
    private val repository: LogisticsRepository,
    private val vcRepository: VirtualContractRepository,
    private val syncRules: SyncRulesFromVirtualContractUseCase
) {
    companion object {
        /** Desktop VC_STATUS_BLOCKED_FOR_LOGISTICS = [FINISH, TERMINATED, CANCELLED] */
        private val BLOCKED_STATUSES = setOf(
            VCStatus.COMPLETED,
            VCStatus.TERMINATED,
            VCStatus.CANCELLED
        )
    }

    suspend operator fun invoke(virtualContractId: Long): Long {
        // VC 状态约束检查
        val vc = vcRepository.getById(virtualContractId)
            ?: throw IllegalArgumentException("VC 不存在")

        if (vc.status in BLOCKED_STATUSES) {
            throw IllegalStateException("VC 状态为 [${vc.status.displayName}]，无法创建物流方案")
        }

        // Desktop-consistent: 一个 VC 只能有一个物流主单；有则返回已有的，不新建
        val existing = repository.getFirstByVcId(virtualContractId)
        if (existing != null) {
            return existing.id
        }

        val logistics = Logistics(
            virtualContractId = virtualContractId,
            status = LogisticsStatus.PENDING
        )
        val logisticsId = repository.insert(logistics)

        // TODO: 暂时跳过规则同步，避免崩溃问题
        // syncRules(virtualContractId, logisticsId)

        return logisticsId
    }
}

class UpdateLogisticsStatusUseCase @Inject constructor(
    private val repository: LogisticsRepository,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val processLogisticsFinance: ProcessLogisticsFinanceUseCase
) {
    suspend operator fun invoke(logisticsId: Long, status: LogisticsStatus): Long {
        val logistics = repository.getById(logisticsId)
            ?: throw IllegalArgumentException("Logistics not found")
        val updated = logistics.copy(status = status)
        repository.update(updated)

        // 触发 VC 状态自动机：物流状态变更 → VC subjectStatus 镜像更新
        stateMachine.onLogisticsStatusChanged(logistics.virtualContractId, status)

        // SIGNED / COMPLETED 时自动生成财务凭证（对应 Desktop process_logistics_finance）
        if (status in listOf(LogisticsStatus.SIGNED, LogisticsStatus.COMPLETED)) {
            processLogisticsFinance(logisticsId)
        }

        return logisticsId
    }
}

class TriggerFinanceUseCase @Inject constructor(
    private val repository: LogisticsRepository,
    private val processLogisticsFinance: ProcessLogisticsFinanceUseCase
) {
    /**
     * 触发物流财务凭证化
     *
     * 对应 Desktop: 物流状态变更时或手动触发
     * 内部调用 ProcessLogisticsFinanceUseCase 生成 FinancialJournal 分录
     */
    suspend operator fun invoke(logisticsId: Long): Long {
        return processLogisticsFinance(logisticsId)
    }
}

class DeleteLogisticsUseCase @Inject constructor(
    private val repository: LogisticsRepository
) {
    suspend operator fun invoke(logistics: Logistics) = repository.delete(logistics)
}

// ==================== Express Order Use Cases ====================

class GetAllExpressOrdersUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    operator fun invoke(): Flow<List<ExpressOrder>> = repository.getAll()
}

class GetExpressOrderByIdUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    suspend operator fun invoke(id: Long): ExpressOrder? = repository.getById(id)
}

class GetExpressOrdersByLogisticsUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    operator fun invoke(logisticsId: Long): Flow<List<ExpressOrder>> = repository.getByLogisticsId(logisticsId)
}

class GetExpressOrderByTrackingUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    suspend operator fun invoke(trackingNumber: String): ExpressOrder? =
        repository.getByTrackingNumber(trackingNumber)
}

class CreateExpressOrderUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    suspend operator fun invoke(
        logisticsId: Long,
        trackingNumber: String?,
        items: List<ExpressItem>,
        addressInfo: AddressInfo
    ): Long {
        val expressOrder = ExpressOrder(
            logisticsId = logisticsId,
            trackingNumber = trackingNumber,
            items = items,
            addressInfo = addressInfo,
            status = ExpressStatus.PENDING
        )
        return repository.insert(expressOrder)
    }
}

class UpdateExpressOrderStatusUseCase @Inject constructor(
    private val expressOrderRepo: ExpressOrderRepository,
    private val logisticsRepo: LogisticsRepository,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val processLogisticsFinance: ProcessLogisticsFinanceUseCase
) {
    /**
     * 更新快递单状态 → 自动推导物流状态 → 联动 VC 状态机
     *
     * Desktop 等效：update_express_status API → logistics_state_machine → VC subject_status
     */
    suspend operator fun invoke(expressOrderId: Long, status: ExpressStatus): Long {
        val expressOrder = expressOrderRepo.getById(expressOrderId)
            ?: throw IllegalArgumentException("Express order not found")
        val updated = expressOrder.copy(status = status)
        expressOrderRepo.update(updated)

        // 自动推导 Logistics 状态
        val logisticsId = expressOrder.logisticsId
        val logistics = logisticsRepo.getById(logisticsId) ?: throw IllegalStateException("Logistics not found")

        // COMPLETED 是人工锁定状态，不自动推导
        if (logistics.status != LogisticsStatus.COMPLETED) {
            val derivedStatus = deriveLogisticsStatus(logisticsId)
            if (derivedStatus != logistics.status) {
                val updatedLogistics = logistics.copy(status = derivedStatus)
                logisticsRepo.update(updatedLogistics)

                // 联动 VC 状态机
                stateMachine.onLogisticsStatusChanged(logistics.virtualContractId, derivedStatus)

                // SIGNED / COMPLETED 时生成财务凭证
                if (derivedStatus == LogisticsStatus.SIGNED || derivedStatus == LogisticsStatus.COMPLETED) {
                    processLogisticsFinance(logisticsId)
                }
            }
        }

        return expressOrderId
    }

    /**
     * 根据所有 ExpressOrder 推导 Logistics 状态
     *
     * Desktop 等效：logistics_state_machine()
     * - 全部 SIGNED → SIGNED
     * - 存在 IN_TRANSIT 或全部 IN_TRANSIT/SIGNED → IN_TRANSIT
     * - 否则 → PENDING
     */
    private suspend fun deriveLogisticsStatus(logisticsId: Long): LogisticsStatus {
        val expressOrders = expressOrderRepo.getByLogisticsIdSuspend(logisticsId)
        if (expressOrders.isEmpty()) return LogisticsStatus.PENDING

        val allSigned = expressOrders.all { it.status == ExpressStatus.SIGNED }
        val anyInTransit = expressOrders.any { it.status == ExpressStatus.IN_TRANSIT }
        val allInTransitOrSigned = expressOrders.all {
            it.status == ExpressStatus.IN_TRANSIT || it.status == ExpressStatus.SIGNED
        }

        return when {
            allSigned -> LogisticsStatus.SIGNED
            anyInTransit || allInTransitOrSigned -> LogisticsStatus.IN_TRANSIT
            else -> LogisticsStatus.PENDING
        }
    }
}

class UpdateExpressOrderTrackingUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    suspend operator fun invoke(expressOrderId: Long, trackingNumber: String): Long {
        val expressOrder = repository.getById(expressOrderId)
            ?: throw IllegalArgumentException("Express order not found")
        val updated = expressOrder.copy(trackingNumber = trackingNumber)
        repository.update(updated)
        return expressOrderId
    }
}

class DeleteExpressOrderUseCase @Inject constructor(
    private val repository: ExpressOrderRepository
) {
    suspend operator fun invoke(expressOrder: ExpressOrder) = repository.delete(expressOrder)
}

// ==================== Confirm Inbound Use Case ====================

class ConfirmInboundUseCase @Inject constructor(
    private val logisticsRepo: LogisticsRepository,
    private val expressOrderRepo: ExpressOrderRepository,
    private val vcRepo: VirtualContractRepository,
    private val equipmentInventoryRepo: EquipmentInventoryRepository,
    private val materialInventoryRepo: MaterialInventoryRepository,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val processLogisticsFinance: ProcessLogisticsFinanceUseCase
) {
    /**
     * 确认入库 — 对应 Desktop confirm_inbound_action
     *
     * 完整流程：
     * 1. 防重复入库检查
     * 2. 创建库存记录（设备按 SN 逐条，物料按汇总更新）
     * 3. 锁定 Logistics.status = COMPLETED（人工锁定，不参与自动推导）
     * 4. 触发 VC 状态机（subjectStatus → COMPLETED）
     * 5. 触发财务凭证生成
     *
     * @param logisticsId 物流单 ID
     * @param snList 设备序列号列表（设备采购类型必须，物料/其他类型可为空）
     */
    suspend operator fun invoke(logisticsId: Long, snList: List<String> = emptyList()) {
        val logistics = logisticsRepo.getById(logisticsId)
            ?: throw IllegalArgumentException("物流单不存在")

        // 防重复入库
        if (logistics.status == LogisticsStatus.COMPLETED) {
            throw IllegalStateException("该物流单已完成入库，请勿重复操作")
        }

        val vc = vcRepo.getById(logistics.virtualContractId)
            ?: throw IllegalStateException("关联 VC 不存在")

        val expressOrders = expressOrderRepo.getByLogisticsIdSuspend(logisticsId)

        // 按 VC 类型执行库存创建
        createInventoryByVcType(vc, expressOrders, snList)

        // 锁定 Logistics.status = COMPLETED（不参与自动推导）
        val updatedLogistics = logistics.copy(status = LogisticsStatus.COMPLETED)
        logisticsRepo.update(updatedLogistics)

        // 触发 VC 状态机：subjectStatus → COMPLETED
        stateMachine.onLogisticsStatusChanged(logistics.virtualContractId, LogisticsStatus.COMPLETED)

        // 触发财务凭证生成
        processLogisticsFinance(logisticsId)
    }

    private suspend fun createInventoryByVcType(
        vc: VirtualContract,
        expressOrders: List<ExpressOrder>,
        snList: List<String>
    ) {
        when (vc.type) {
            VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK -> {
                // 设备采购/库存：逐条创建 EquipmentInventory（需要 SN）
                val equipmentSnList = snList.filter { it.isNotBlank() }
                if (equipmentSnList.isEmpty()) {
                    throw IllegalArgumentException("设备入库需要提供 SN 列表")
                }

                // 按 expressOrders 合并 items（去重），按 SN 数量创建记录
                val allItems = expressOrders.flatMap { it.items }.groupBy { it.skuId }
                val itemsWithQty = allItems.map { (skuId, items) ->
                    items.first().copy(quantity = items.sumOf { it.quantity })
                }

                for ((idx, sn) in equipmentSnList.withIndex()) {
                    // SN 唯一性检查
                    val existing = equipmentInventoryRepo.getBySn(sn)
                    if (existing != null) {
                        throw IllegalStateException("SN [$sn] 已存在于系统中，无法重复入库")
                    }

                    // 找到该 SN 对应的 SKU（循环分配）
                    val item = itemsWithQty.getOrNull(idx % itemsWithQty.size)
                        ?: itemsWithQty.firstOrNull()
                        ?: throw IllegalStateException("SN 数量超过 ExpressOrder 中的 SKU 总数")

                    // 约定押金（deposit）：从 VC.elements 取
                    // 使用统一的 deposit 字段，兼容 SkusFormatElement/MaterialSupplyElement
                    val element = vc.elements.find { it.skuId == item.skuId }
                    val depositAmount = element?.deposit ?: 0.0

                    // 从 ExpressOrder 的 AddressInfo 获取收货点位
                    val receivingPointId = expressOrders.firstOrNull()?.addressInfo?.receivingPointId
                    val receivingPointName = expressOrders.firstOrNull()?.addressInfo?.receivingPointName

                    val equipment = EquipmentInventory(
                        sn = sn,
                        skuId = item.skuId,
                        skuName = item.skuName,
                        virtualContractId = vc.id,
                        vcTypeName = vc.type.displayName,
                        operationalStatus = OperationalStatus.IN_OPERATION,
                        deviceStatus = DeviceStatus.NORMAL,
                        pointId = receivingPointId,
                        pointName = receivingPointName,
                        depositAmount = depositAmount,
                        depositTimestamp = System.currentTimeMillis()
                    )
                    equipmentInventoryRepo.insert(equipment)
                }
            }

            VCType.MATERIAL_PROCUREMENT -> {
                // 物料采购：更新 MaterialInventory（累加库存，按收货点位分仓库记录）
                // 按 skuId 分组，同一 SKU 的数量累加到同一仓库
                val itemsBySku = mutableMapOf<Long, Triple<String, Long?, Int>>() // skuId -> (skuName, recvPointId, totalQty)

                for (order in expressOrders) {
                    val recvPointId = order.addressInfo.receivingPointId
                    val recvPointName = order.addressInfo.receivingPointName ?: "默认仓库"
                    for (item in order.items) {
                        val existing = itemsBySku[item.skuId]
                        if (existing != null) {
                            itemsBySku[item.skuId] = Triple(existing.first, recvPointId, existing.third + item.quantity)
                        } else {
                            itemsBySku[item.skuId] = Triple(item.skuName, recvPointId, item.quantity)
                        }
                    }
                }

                for ((skuId, data) in itemsBySku) {
                    val (skuName, recvPointId, totalQty) = data
                    val existing = materialInventoryRepo.getBySkuId(skuId)

                    if (existing != null) {
                        // 更新现有库存：累加 totalBalance，按仓库累加 stock_distribution
                        val newDistribution = existing.stockDistribution.toMutableList()
                        val existingIdx = newDistribution.indexOfFirst { it.pointId == recvPointId }
                        if (existingIdx >= 0) {
                            val existingEntry = newDistribution[existingIdx]
                            newDistribution[existingIdx] = existingEntry.copy(quantity = existingEntry.quantity + totalQty)
                        } else {
                            newDistribution.add(StockDistribution(pointId = recvPointId ?: 0L, pointName = skuName, quantity = totalQty))
                        }
                        val updated = existing.copy(
                            totalBalance = existing.totalBalance + totalQty,
                            stockDistribution = newDistribution
                        )
                        materialInventoryRepo.update(updated)
                    } else {
                        // 新建物料库存记录
                        val newMaterial = MaterialInventory(
                            skuId = skuId,
                            skuName = skuName,
                            totalBalance = totalQty.toDouble(),
                            averagePrice = 0.0,
                            stockDistribution = listOf(StockDistribution(pointId = recvPointId ?: 0L, pointName = skuName, quantity = totalQty))
                        )
                        materialInventoryRepo.insert(newMaterial)
                    }
                }
            }

            VCType.MATERIAL_SUPPLY -> {
                // 物料供应：减少 MaterialInventory（按发货点位分仓库扣减）
                val itemsBySku = mutableMapOf<Long, Triple<String, Long?, Int>>() // skuId -> (skuName, shipPointId, totalQty)

                for (order in expressOrders) {
                    val shipPointId = order.addressInfo.shippingPointId
                    val shipPointName = order.addressInfo.shippingPointName ?: "默认仓库"
                    for (item in order.items) {
                        val existing = itemsBySku[item.skuId]
                        if (existing != null) {
                            itemsBySku[item.skuId] = Triple(existing.first, shipPointId, existing.third + item.quantity)
                        } else {
                            itemsBySku[item.skuId] = Triple(item.skuName, shipPointId, item.quantity)
                        }
                    }
                }

                for ((skuId, data) in itemsBySku) {
                    val (skuName, shipPointId, totalQty) = data
                    val existing = materialInventoryRepo.getBySkuId(skuId)
                        ?: throw IllegalStateException("物料 [skuId=$skuId] 不在库存中，无法执行出库")

                    // 按发货点位扣减 stock_distribution
                    val newDistribution = existing.stockDistribution.toMutableList()
                    val existingIdx = newDistribution.indexOfFirst { it.pointId == shipPointId }
                    if (existingIdx >= 0) {
                        val existingEntry = newDistribution[existingIdx]
                        newDistribution[existingIdx] = existingEntry.copy(quantity = (existingEntry.quantity - totalQty).coerceAtLeast(0))
                    } else {
                        // 该仓库没有库存记录，创建负数记录（理论上不应该发生）
                        newDistribution.add(StockDistribution(pointId = shipPointId ?: 0L, pointName = skuName, quantity = -totalQty))
                    }
                    val updated = existing.copy(
                        totalBalance = (existing.totalBalance - totalQty).coerceAtLeast(0.0),
                        stockDistribution = newDistribution
                    )
                    materialInventoryRepo.update(updated)
                }
            }

            VCType.RETURN -> {
                // 退货 VC：处理物料退货
                // 设备退货（按 SN）需要从 VC.elements.return_items 获取 SN，当前 ExpressItem 不含 SN
                // 退货到我方仓库(CUSTOMER_TO_US)：物料增加库存
                // 退货到供应商(US_TO_SUPPLIER)：物料减少库存
                val returnDirection = vc.returnDirection

                for (expressOrder in expressOrders) {
                    val recvPointId = expressOrder.addressInfo.receivingPointId
                    val recvPointName = expressOrder.addressInfo.receivingPointName ?: "默认仓库"
                    val shipPointId = expressOrder.addressInfo.shippingPointId
                    val shipPointName = expressOrder.addressInfo.shippingPointName ?: "默认仓库"

                    for (item in expressOrder.items) {
                        if (item.skuId > 0 && item.quantity > 0) {
                            val existing = materialInventoryRepo.getBySkuId(item.skuId)
                            if (existing != null) {
                                val newDistribution = existing.stockDistribution.toMutableList()
                                if (returnDirection == ReturnDirection.CUSTOMER_TO_US) {
                                    // 退货到我方仓库：收货点位增加库存
                                    val existingIdx = newDistribution.indexOfFirst { it.pointId == recvPointId }
                                    if (existingIdx >= 0) {
                                        val existingEntry = newDistribution[existingIdx]
                                        newDistribution[existingIdx] = existingEntry.copy(quantity = existingEntry.quantity + item.quantity)
                                    } else {
                                        newDistribution.add(StockDistribution(pointId = recvPointId ?: 0L, pointName = recvPointName, quantity = item.quantity))
                                    }
                                    val updated = existing.copy(
                                        totalBalance = existing.totalBalance + item.quantity,
                                        stockDistribution = newDistribution
                                    )
                                    materialInventoryRepo.update(updated)
                                } else if (returnDirection == ReturnDirection.US_TO_SUPPLIER) {
                                    // 退货到供应商：发货点位减少库存
                                    val existingIdx = newDistribution.indexOfFirst { it.pointId == shipPointId }
                                    if (existingIdx >= 0) {
                                        val existingEntry = newDistribution[existingIdx]
                                        newDistribution[existingIdx] = existingEntry.copy(quantity = (existingEntry.quantity - item.quantity).coerceAtLeast(0))
                                    }
                                    val updated = existing.copy(
                                        totalBalance = (existing.totalBalance - item.quantity).coerceAtLeast(0.0),
                                        stockDistribution = newDistribution
                                    )
                                    materialInventoryRepo.update(updated)
                                }
                            }
                        }
                    }
                }
            }

            VCType.INVENTORY_ALLOCATION -> {
                // 库存调拨：暂不处理（需要源仓库和目标仓库信息）
            }
        }
    }
}

// ==================== Bulk Progress Express Orders Use Case ====================

/**
 * 批量推进快递单状态 UseCase
 *
 * 对应 Desktop bulk_progress_express_orders_action()
 *
 * 逻辑：
 * 1. 批量更新所有指定快递单的状态
 * 2. 触发物流状态自动推导（基于所有快递单状态）
 * 3. 联动 VC 状态机
 */
class BulkProgressExpressOrdersUseCase @Inject constructor(
    private val expressOrderRepo: ExpressOrderRepository,
    private val logisticsRepo: LogisticsRepository,
    private val stateMachine: VirtualContractStateMachineUseCase,
    private val processLogisticsFinance: ProcessLogisticsFinanceUseCase
) {
    /**
     * 批量推进快递单状态
     *
     * @param logisticsId 物流单ID
     * @param expressOrderIds 要更新的快递单ID列表
     * @param targetStatus 目标状态
     * @return 更新数量
     */
    suspend operator fun invoke(logisticsId: Long, expressOrderIds: List<Long>, targetStatus: ExpressStatus): Int {
        val logistics = logisticsRepo.getById(logisticsId)
            ?: throw IllegalStateException("Logistics not found")

        // 批量更新快递单状态
        var updatedCount = 0
        for (expressOrderId in expressOrderIds) {
            val expressOrder = expressOrderRepo.getById(expressOrderId) ?: continue
            val updated = expressOrder.copy(status = targetStatus)
            expressOrderRepo.update(updated)
            updatedCount++
        }

        // 自动推导 Logistics 状态（仅当物流未完成时）
        if (logistics.status != LogisticsStatus.COMPLETED && logistics.status != LogisticsStatus.SIGNED) {
            val derivedStatus = deriveLogisticsStatus(logisticsId)
            if (derivedStatus != logistics.status) {
                val updatedLogistics = logistics.copy(status = derivedStatus)
                logisticsRepo.update(updatedLogistics)

                // 联动 VC 状态机
                stateMachine.onLogisticsStatusChanged(logistics.virtualContractId, derivedStatus)

                // SIGNED / COMPLETED 时生成财务凭证
                if (derivedStatus == LogisticsStatus.SIGNED || derivedStatus == LogisticsStatus.COMPLETED) {
                    processLogisticsFinance(logisticsId)
                }
            }
        }

        return updatedCount
    }

    /**
     * 根据所有 ExpressOrder 推导 Logistics 状态
     */
    private suspend fun deriveLogisticsStatus(logisticsId: Long): LogisticsStatus {
        val expressOrders = expressOrderRepo.getByLogisticsIdSuspend(logisticsId)
        if (expressOrders.isEmpty()) return LogisticsStatus.PENDING

        val allSigned = expressOrders.all { it.status == ExpressStatus.SIGNED }
        val anyInTransit = expressOrders.any { it.status == ExpressStatus.IN_TRANSIT }
        val allInTransitOrSigned = expressOrders.all {
            it.status == ExpressStatus.IN_TRANSIT || it.status == ExpressStatus.SIGNED
        }

        return when {
            allSigned -> LogisticsStatus.SIGNED
            anyInTransit || allInTransitOrSigned -> LogisticsStatus.IN_TRANSIT
            else -> LogisticsStatus.PENDING
        }
    }
}
