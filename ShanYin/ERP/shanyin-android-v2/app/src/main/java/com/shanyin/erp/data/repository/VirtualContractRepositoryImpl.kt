package com.shanyin.erp.data.repository

import com.google.gson.Gson
import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName
import com.shanyin.erp.data.local.dao.SupplyChainDao
import com.shanyin.erp.data.local.dao.SupplyChainItemDao
import com.shanyin.erp.data.local.dao.VirtualContractDao
import com.shanyin.erp.data.local.dao.VirtualContractHistoryDao
import com.shanyin.erp.data.local.dao.VirtualContractStatusLogDao
import com.shanyin.erp.data.local.entity.VirtualContractEntity
import com.shanyin.erp.data.local.entity.VirtualContractHistoryEntity
import com.shanyin.erp.data.local.entity.VirtualContractStatusLogEntity
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.VCStatusLogRepository
import com.shanyin.erp.domain.repository.VCHistoryRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class VirtualContractRepositoryImpl @Inject constructor(
    private val dao: VirtualContractDao,
    private val gson: Gson,
    private val cashFlowRepo: CashFlowRepository,
    private val supplyChainDao: SupplyChainDao,
    private val supplyChainItemDao: SupplyChainItemDao
) : VirtualContractRepository {

    override fun getAll(): Flow<List<VirtualContract>> =
        dao.getAll().map { entities -> entities.mapSuspend { it.toDomainSuspend() } }

    override suspend fun getById(id: Long): VirtualContract? =
        dao.getById(id)?.toDomainSuspend()

    override fun getByIdFlow(id: Long): Flow<VirtualContract?> =
        dao.getByIdFlow(id).map { it?.toDomainSuspend() }

    override fun getByBusinessId(businessId: Long): Flow<List<VirtualContract>> =
        dao.getByBusinessId(businessId).map { entities -> entities.mapSuspend { it.toDomainSuspend() } }

    override fun getBySupplyChainId(supplyChainId: Long): Flow<List<VirtualContract>> =
        dao.getBySupplyChainId(supplyChainId).map { entities -> entities.mapSuspend { it.toDomainSuspend() } }

    override fun getByRelatedVcId(relatedVcId: Long): Flow<List<VirtualContract>> =
        dao.getByRelatedVcId(relatedVcId).map { entities -> entities.mapSuspend { it.toDomainSuspend() } }

    override fun getByStatus(status: VCStatus): Flow<List<VirtualContract>> =
        dao.getByStatus(status.name).map { entities -> entities.mapSuspend { it.toDomainSuspend() } }

    override fun getByType(type: VCType): Flow<List<VirtualContract>> =
        dao.getByType(type.name).map { entities -> entities.mapSuspend { it.toDomainSuspend() } }

    override suspend fun insert(vc: VirtualContract): Long =
        dao.insert(vc.toEntity())

    override suspend fun update(vc: VirtualContract) =
        dao.update(vc.toEntity())

    override suspend fun delete(vc: VirtualContract) =
        dao.delete(vc.toEntity())

    override fun getCount(): Flow<Int> =
        dao.getCount()

    /**
     * 解析 VC elements
     *
     * 支持Desktop新版统一格式：{"elements": [...], "total_amount": N}
     * elements 是 VCElementSchema 数组
     */
    private suspend fun VirtualContractEntity.toDomainSuspend(): VirtualContract {
        val vcType = VCType.fromDbName(type) ?: VCType.EQUIPMENT_PROCUREMENT

        // DEBUG: 输出数据库原始 elements JSON
        android.util.Log.d("VCRepo", "toDomainSuspend: vcId=$id, vcType=$vcType, elements原始=${elements?.take(500)}")

        // 解析 elements（新版本统一格式）
        val elementsList: List<VCElement> = if (elements.isNullOrBlank()) {
            emptyList()
        } else {
            parseElements(elements, vcType)
        }

        // 解析 depositInfo
        val depositInfoResolved = parseDepositInfo(depositInfo, elements)

        // 计算 actualAmount（从 cash_flows 按 VC 类型规则计算）
        val cashFlows = try { cashFlowRepo.getByVcId(id).first() } catch (e: Exception) { emptyList() }
        val actualAmount = calculateActualAmount(vcType, cashFlows, elements)

        // 解析退货元数据
        val (resolvedReturnDirection, resolvedGoodsAmount, resolvedLogisticsCost, resolvedLogisticsBearer) =
            parseReturnMetadata(type, elements)

        // 更新 totalAmount 和 actualAmount
        val finalDepositInfo = depositInfoResolved.copy(
            totalAmount = depositInfoResolved.totalAmount.takeIf { it > 0 } ?: actualAmount,
            actualAmount = actualAmount
        )

        return VirtualContract(
            id = id,
            description = description,
            businessId = businessId,
            supplyChainId = supplyChainId,
            relatedVcId = relatedVcId,
            type = vcType,
            summary = summary,
            elements = elementsList,
            depositInfo = finalDepositInfo,
            status = VCStatus.fromDbName(status) ?: VCStatus.EXECUTING,
            subjectStatus = SubjectStatus.fromDbName(subjectStatus) ?: SubjectStatus.EXECUTING,
            cashStatus = CashStatus.fromDbName(cashStatus) ?: CashStatus.EXECUTING,
            statusTimestamp = statusTimestamp,
            subjectStatusTimestamp = subjectStatusTimestamp,
            cashStatusTimestamp = cashStatusTimestamp,
            returnDirection = resolvedReturnDirection ?: this.returnDirection?.let { rd ->
                when (rd) {
                    "US_TO_SUPPLIER" -> ReturnDirection.US_TO_SUPPLIER
                    "CUSTOMER_TO_US" -> ReturnDirection.CUSTOMER_TO_US
                    else -> null
                }
            },
            goodsAmount = resolvedGoodsAmount,
            logisticsCost = resolvedLogisticsCost,
            logisticsBearer = resolvedLogisticsBearer
        )
    }

    /**
     * 解析 elements JSON
     *
     * Desktop新版格式：{"elements": [...], "total_amount": N, ...}
     */
    private fun parseElements(elementsJson: String, vcType: VCType): List<VCElement> {
        if (elementsJson.isNullOrBlank()) {
            android.util.Log.w("VCRepo", "parseElements: elementsJson is blank, vcType=$vcType")
            return emptyList()
        }

        // 尝试解析新格式
        try {
            val wrapper = gson.fromJson(elementsJson, DesktopVCElementWrapper::class.java)
            if (wrapper?.elements.isNullOrEmpty()) {
                android.util.Log.d("VCRepo", "parseElements: wrapper.elements is null/empty, vcType=$vcType, elementsJson=${elementsJson.take(200)}")
                return emptyList()
            }
            android.util.Log.d("VCRepo", "parseElements: SUCCESS, vcType=$vcType, elementsCount=${wrapper!!.elements!!.size}")
            return wrapper.elements!!.mapIndexedNotNull { index, elem ->
                try {
                    when (vcType) {
                        VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK, VCType.MATERIAL_PROCUREMENT -> {
                            SkusFormatElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.receivingPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = elem.qtyValue.toInt(),
                                unitPrice = elem.priceValue,
                                deposit = elem.deposit ?: 0.0,
                                subtotal = elem.subtotal ?: (elem.qtyValue * elem.priceValue),
                                snList = elem.snList ?: emptyList()
                            )
                        }
                        VCType.MATERIAL_SUPPLY -> {
                            MaterialSupplyElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.receivingPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = elem.qtyValue.toInt(),
                                unitPrice = elem.priceValue,
                                deposit = elem.deposit ?: 0.0,
                                subtotal = elem.subtotal ?: (elem.qtyValue * elem.priceValue),
                                snList = elem.snList ?: emptyList(),
                                sourceWarehouse = elem.sourceWarehouse
                            )
                        }
                        VCType.RETURN -> {
                            ReturnElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.receivingPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = (elem.qty ?: 0.0).toInt(),
                                unitPrice = 0.0,
                                deposit = 0.0,
                                subtotal = 0.0,
                                snList = elem.snList ?: emptyList(),
                                receivingWarehouse = elem.receivingWarehouse,
                                goodsAmount = elem.goodsAmount ?: wrapper.goodsAmount,
                                depositAmount = elem.depositAmount ?: wrapper.depositAmount,
                                totalRefund = elem.totalRefund ?: wrapper.totalRefund,
                                reason = elem.reason ?: wrapper.reason
                            )
                        }
                        VCType.INVENTORY_ALLOCATION -> {
                            AllocationElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.targetPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = 1,
                                unitPrice = 0.0,
                                deposit = elem.deposit ?: 0.0,
                                subtotal = 0.0,
                                snList = elem.snList ?: emptyList(),
                                equipmentId = elem.equipmentId,
                                equipmentSn = elem.sn,
                                targetPointId = elem.targetPointId?.toLong()
                            )
                        }
                    }
                } catch (e: Exception) {
                    android.util.Log.e("VCRepo", "parseElements: elem[$index] mapping failed: ${e.message}")
                    null
                }
            }
        } catch (e: Exception) {
            android.util.Log.e("VCRepo", "parseElements: FAILED to parse wrapper, vcType=$vcType, elementsJson=${elementsJson.take(300)}, error=${e.message}")
            // 尝试直接解析 elements 数组格式
            return tryParseDirectArrayFormat(elementsJson, vcType)
        }
    }

    /**
     * 尝试直接解析 elements 数组格式（某些旧格式或简化格式）
     */
    private fun tryParseDirectArrayFormat(elementsJson: String, vcType: VCType): List<VCElement> {
        try {
            val type = object : com.google.gson.reflect.TypeToken<List<DesktopVCElement>>() {}.type
            val list: List<DesktopVCElement> = gson.fromJson(elementsJson, type)
            if (list.isNullOrEmpty()) {
                android.util.Log.d("VCRepo", "tryParseDirectArrayFormat: list is null/empty")
                return emptyList()
            }
            android.util.Log.d("VCRepo", "tryParseDirectArrayFormat: SUCCESS, count=${list.size}")
            // DEBUG: 输出第一个 element 的解析值
            if (list.isNotEmpty()) {
                val first = list[0]
                android.util.Log.d("VCRepo", "  first elem: qty=${first.qtyValue}, price=${first.priceValue}, shippingPointId=${first.shippingPointId}, receivingPointId=${first.receivingPointId}, skuId=${first.skuId}")
            }
            // 复用上面的映射逻辑
            return list.mapIndexedNotNull { index, elem ->
                try {
                    when (vcType) {
                        VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK, VCType.MATERIAL_PROCUREMENT -> {
                            SkusFormatElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.receivingPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = elem.qtyValue.toInt(),
                                unitPrice = elem.priceValue,
                                deposit = elem.deposit ?: 0.0,
                                subtotal = elem.subtotal ?: (elem.qtyValue * elem.priceValue),
                                snList = elem.snList ?: emptyList()
                            )
                        }
                        VCType.MATERIAL_SUPPLY -> {
                            MaterialSupplyElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.receivingPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = elem.qtyValue.toInt(),
                                unitPrice = elem.priceValue,
                                deposit = elem.deposit ?: 0.0,
                                subtotal = elem.subtotal ?: (elem.qtyValue * elem.priceValue),
                                snList = elem.snList ?: emptyList(),
                                sourceWarehouse = elem.sourceWarehouse
                            )
                        }
                        VCType.RETURN -> {
                            ReturnElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.receivingPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = (elem.qty ?: 0.0).toInt(),
                                unitPrice = 0.0,
                                deposit = 0.0,
                                subtotal = 0.0,
                                snList = elem.snList ?: emptyList(),
                                receivingWarehouse = elem.receivingWarehouse,
                                goodsAmount = elem.goodsAmount,
                                depositAmount = elem.depositAmount,
                                totalRefund = elem.totalRefund,
                                reason = elem.reason
                            )
                        }
                        VCType.INVENTORY_ALLOCATION -> {
                            AllocationElement(
                                id = elem.id ?: generateElementId(elem),
                                shippingPointId = elem.shippingPointId?.toLong(),
                                receivingPointId = elem.targetPointId?.toLong(),
                                skuId = elem.skuId ?: 0L,
                                skuName = elem.skuName ?: "",
                                quantity = 1,
                                unitPrice = 0.0,
                                deposit = elem.deposit ?: 0.0,
                                subtotal = 0.0,
                                snList = elem.snList ?: emptyList(),
                                equipmentId = elem.equipmentId,
                                equipmentSn = elem.sn,
                                targetPointId = elem.targetPointId?.toLong()
                            )
                        }
                    }
                } catch (e: Exception) {
                    android.util.Log.e("VCRepo", "tryParseDirectArrayFormat: elem[$index] failed: ${e.message}")
                    null
                }
            }
        } catch (e: Exception) {
            android.util.Log.e("VCRepo", "tryParseDirectArrayFormat: FAILED, error=${e.message}")
            return emptyList()
        }
    }

    /**
     * 解析 depositInfo JSON
     */
    private fun parseDepositInfo(depositInfoJson: String?, elementsJson: String?): DepositInfo {
        if (depositInfoJson.isNullOrBlank()) {
            // 从 elements JSON 提取 total_amount
            val totalAmount = try {
                val obj = gson.fromJson(elementsJson, Map::class.java)
                (obj["total_amount"] as? Number)?.toDouble()
                    ?: (obj["total_refund"] as? Number)?.toDouble()
                    ?: 0.0
            } catch (e: Exception) { 0.0 }
            return DepositInfo(totalAmount = totalAmount)
        }

        return try {
            val raw = gson.fromJson(depositInfoJson, DesktopDepositInfo::class.java)
            DepositInfo(
                // Desktop's should_receive -> Mobile's expectedDeposit
                expectedDeposit = raw.expectedDeposit ?: raw.shouldReceive ?: 0.0,
                // Desktop's total_deposit -> Mobile's actualDeposit
                actualDeposit = raw.totalDeposit ?: raw.actualDeposit ?: 0.0,
                totalAmount = raw.totalAmount ?: 0.0,
                // Desktop's should_receive -> Mobile's shouldReceive (same field, different name)
                shouldReceive = raw.shouldReceive ?: raw.expectedDeposit ?: 0.0,
                actualAmount = 0.0, // 由调用方计算后填充
                lastCashFlowId = raw.lastCashFlowId,
                adjustmentReason = raw.adjustmentReason,
                prepaymentRatio = raw.prepaymentRatio ?: 0.0
            )
        } catch (e: Exception) {
            DepositInfo()
        }
    }

    /**
     * 解析退货元数据
     */
    private fun parseReturnMetadata(type: String?, elementsJson: String?): Tuple4<ReturnDirection?, Double, Double, LogisticsBearer?> {
        if (type != VCType.RETURN.name) {
            return Tuple4(null, 0.0, 0.0, null)
        }

        return try {
            val obj = gson.fromJson(elementsJson, Map::class.java)
            val dir = obj["return_direction"] as? String
            val direction = when (dir) {
                "US_TO_SUPPLIER" -> ReturnDirection.US_TO_SUPPLIER
                "CUSTOMER_TO_US" -> ReturnDirection.CUSTOMER_TO_US
                else -> null
            }
            val goodsAmount = (obj["goods_amount"] as? Number)?.toDouble() ?: 0.0
            val logisticsCost = (obj["logistics_cost"] as? Number)?.toDouble() ?: 0.0
            val bearer = when (obj["logistics_bearer"] as? String) {
                "SENDER" -> LogisticsBearer.SENDER
                "RECEIVER" -> LogisticsBearer.RECEIVER
                else -> null
            }
            Tuple4(direction, goodsAmount, logisticsCost, bearer)
        } catch (e: Exception) {
            Tuple4(null, 0.0, 0.0, null)
        }
    }

    /**
     * 根据 VC 类型计算 actualAmount
     */
    private fun calculateActualAmount(vcType: VCType, cashFlows: List<CashFlow>, elements: String?): Double {
        return when (vcType) {
            VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK, VCType.MATERIAL_PROCUREMENT -> {
                cashFlows.filter {
                    it.type == CashFlowType.PREPAYMENT ||
                    it.type == CashFlowType.PERFORMANCE ||
                    it.type == CashFlowType.REFUND ||
                    it.type == CashFlowType.OFFSET_OUTFLOW
                }.sumOf { it.amount }
            }
            VCType.MATERIAL_SUPPLY -> {
                cashFlows.filter {
                    it.type == CashFlowType.PREPAYMENT || it.type == CashFlowType.PERFORMANCE
                }.sumOf { it.amount }
            }
            VCType.RETURN -> {
                // 退货：actualAmount 基于退款金额
                val returnDirection = try {
                    val obj = gson.fromJson(elements, Map::class.java)
                    obj["return_direction"] as? String
                } catch (e: Exception) { null }
                val refundSum = cashFlows.filter { it.type == CashFlowType.REFUND }.sumOf { it.amount }
                if (returnDirection == "US_TO_SUPPLIER") refundSum else -refundSum
            }
            VCType.INVENTORY_ALLOCATION -> 0.0
        }
    }

    private fun generateElementId(elem: DesktopVCElement): String {
        return "sp${elem.shippingPointId}_rp${elem.receivingPointId}_sku${elem.skuId}"
    }

    private fun VirtualContract.toEntity() = VirtualContractEntity(
        id = id,
        description = description,
        businessId = businessId,
        supplyChainId = supplyChainId,
        relatedVcId = relatedVcId,
        type = type.name,
        summary = summary,
        elements = gson.toJson(elements),
        depositInfo = depositInfo.toJson(),
        status = status.name,
        subjectStatus = subjectStatus.name,
        cashStatus = cashStatus.name,
        statusTimestamp = statusTimestamp,
        subjectStatusTimestamp = subjectStatusTimestamp,
        cashStatusTimestamp = cashStatusTimestamp,
        returnDirection = returnDirection?.name
    )
}

/**
 * 简单的4元组
 */
private data class Tuple4<A, B, C, D>(val first: A, val second: B, val third: C, val fourth: D)

// Desktop 新版统一格式
private data class DesktopVCElementWrapper(
    val elements: List<DesktopVCElement>? = null,
    val totalAmount: Double? = null,
    val paymentTerms: Map<String, Any>? = null,
    val goodsAmount: Double? = null,
    val depositAmount: Double? = null,
    val totalRefund: Double? = null,
    val reason: String? = null,
    val returnDirection: String? = null
)

/**
 * 自定义反序列化器，兼容 snake_case (Desktop) 和 camelCase 两种 JSON 格式
 */
class DesktopVCElementDeserializer : JsonDeserializer<DesktopVCElement> {
    override fun deserialize(json: JsonElement?, typeOfT: java.lang.reflect.Type?, context: JsonDeserializationContext?): DesktopVCElement {
        val jsonObj = json?.asJsonObject ?: return DesktopVCElement()

        // 尝试从 JSON 中提取值，支持 snake_case 和 camelCase 两种命名
        fun getString(key: String, altKey: String): String? {
            return jsonObj.get(key)?.asString ?: jsonObj.get(altKey)?.asString
        }
        fun getInt(key: String, altKey: String): Int? {
            return jsonObj.get(key)?.asInt ?: jsonObj.get(altKey)?.asInt
        }
        fun getLong(key: String, altKey: String): Long? {
            return jsonObj.get(key)?.asLong ?: jsonObj.get(altKey)?.asLong
        }
        fun getDouble(key: String, altKey: String): Double? {
            return jsonObj.get(key)?.asDouble ?: jsonObj.get(altKey)?.asDouble
        }
        fun getStringList(key: String, altKey: String): List<String>? {
            return jsonObj.get(key)?.asJsonArray?.map { it.asString }
                ?: jsonObj.get(altKey)?.asJsonArray?.map { it.asString }
        }

        return DesktopVCElement(
            id = getString("id", "id"),
            // shipping_point_id 或 shippingPointId
            shippingPointId = getInt("shipping_point_id", "shippingPointId"),
            // receiving_point_id 或 receivingPointId
            receivingPointId = getInt("receiving_point_id", "receivingPointId"),
            // sku_id 或 skuId
            skuId = getLong("sku_id", "skuId"),
            // sku_name 或 skuName
            skuName = getString("sku_name", "skuName"),
            // qty 或 quantity
            qty = getDouble("qty", "quantity"),
            quantityJson = null, // 由 qtyValue 计算属性处理
            // price 或 unitPrice
            price = getDouble("price", "unitPrice"),
            unitPriceJson = null, // 由 priceValue 计算属性处理
            deposit = getDouble("deposit", "deposit"),
            subtotal = getDouble("subtotal", "subtotal"),
            // sn_list 或 snList
            snList = getStringList("sn_list", "snList"),
            sourceWarehouse = getString("source_warehouse", "sourceWarehouse"),
            receivingWarehouse = getString("receiving_warehouse", "receivingWarehouse"),
            goodsAmount = getDouble("goods_amount", "goodsAmount"),
            depositAmount = getDouble("deposit_amount", "depositAmount"),
            totalRefund = getDouble("total_refund", "totalRefund"),
            reason = getString("reason", "reason"),
            equipmentId = getLong("equipment_id", "equipmentId"),
            sn = getString("sn", "sn"),
            targetPointId = getInt("target_point_id", "targetPointId"),
            targetPointName = getString("target_point_name", "targetPointName")
        )
    }
}

data class DesktopVCElement(
    val id: String? = null,
    val shippingPointId: Int? = null,
    val receivingPointId: Int? = null,
    val skuId: Long? = null,
    val skuName: String? = null,
    val qty: Double? = null,
    val quantityJson: Double? = null,
    val price: Double? = null,
    val unitPriceJson: Double? = null,
    val deposit: Double? = null,
    val subtotal: Double? = null,
    val snList: List<String>? = null,
    val sourceWarehouse: String? = null,
    val receivingWarehouse: String? = null,
    val goodsAmount: Double? = null,
    val depositAmount: Double? = null,
    val totalRefund: Double? = null,
    val reason: String? = null,
    val equipmentId: Long? = null,
    val sn: String? = null,
    val targetPointId: Int? = null,
    val targetPointName: String? = null
) {
    /** 兼容两种字段名：qty 或 quantity */
    val qtyValue: Double get() = qty ?: quantityJson ?: 0.0
    /** 兼容两种字段名：price 或 unitPrice */
    val priceValue: Double get() = price ?: unitPriceJson ?: 0.0
}

private data class DesktopDepositInfo(
    @SerializedName("should_receive") val shouldReceive: Double? = null,
    @SerializedName("total_deposit") val totalDeposit: Double? = null,
    @SerializedName("total_amount") val totalAmount: Double? = null,
    @SerializedName("actual_net_deposit") val actualNetDeposit: Double? = null,
    @SerializedName("last_cash_flow_id") val lastCashFlowId: Long? = null,
    @SerializedName("adjustment_reason") val adjustmentReason: String? = null,
    @SerializedName("prepayment_ratio") val prepaymentRatio: Double? = null,
    // Desktop may also use these names
    val expectedDeposit: Double? = null,
    val actualDeposit: Double? = null
)

@Singleton
class VCStatusLogRepositoryImpl @Inject constructor(
    private val dao: VirtualContractStatusLogDao
) : VCStatusLogRepository {

    override fun getByVcId(vcId: Long): Flow<List<VCStatusLog>> =
        dao.getByVcId(vcId).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(log: VCStatusLog): Long =
        dao.insert(log.toEntity())

    override suspend fun deleteByVcId(vcId: Long) =
        dao.deleteByVcId(vcId)

    override suspend fun getEarliestByCategoryAndStatus(vcId: Long, category: StatusLogCategory, statusName: String): VCStatusLog? =
        dao.getEarliestByCategoryAndStatus(vcId, category.toDbName(), statusName)?.toDomain()

    private fun VirtualContractStatusLogEntity.toDomain() = VCStatusLog(
        id = id,
        vcId = vcId,
        category = StatusLogCategory.fromDbName(category) ?: StatusLogCategory.STATUS,
        statusName = statusName,
        timestamp = timestamp
    )

    private fun VCStatusLog.toEntity() = VirtualContractStatusLogEntity(
        id = id,
        vcId = vcId,
        category = category.toDbName(),
        statusName = statusName,
        timestamp = timestamp
    )
}

@Singleton
class VCHistoryRepositoryImpl @Inject constructor(
    private val dao: VirtualContractHistoryDao,
    private val gson: Gson
) : VCHistoryRepository {

    override fun getByVcId(vcId: Long): Flow<List<VCHistory>> =
        dao.getByVcId(vcId).map { entities -> entities.map { it.toDomain() } }

    override suspend fun insert(history: VCHistory): Long =
        dao.insert(history.toEntity())

    private fun VirtualContractHistoryEntity.toDomain() = VCHistory(
        id = id,
        vcId = vcId,
        originalData = originalData ?: "{}",
        changeDate = changeDate,
        changeReason = changeReason
    )

    private fun VCHistory.toEntity() = VirtualContractHistoryEntity(
        id = id,
        vcId = vcId,
        originalData = originalData,
        changeDate = changeDate,
        changeReason = changeReason
    )
}

// 在 List 上执行 suspend map
private suspend fun <T, R> List<T>.mapSuspend(transform: suspend (T) -> R): List<R> {
    val result = mutableListOf<R>()
    for (item in this) {
        result.add(transform(item))
    }
    return result
}
