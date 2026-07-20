package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.CashFlowRepository
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.VCStatusLogRepository
import com.shanyin.erp.domain.repository.VirtualContractRepository
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 虚拟合同状态自动机 — 对应 Desktop virtual_contract_state_machine()
 *
 * 驱动逻辑：
 * - 物流状态变更 → VC subjectStatus 镜像更新
 * - 资金流变更 → VC cashStatus 重算 + actualDeposit 更新
 * - subjectStatus==COMPLETED AND cashStatus==COMPLETED → VC status==COMPLETED
 * - 退货 VC 完成 → 原 VC 押金重算
 *
 * 调用方：
 * - UpdateLogisticsStatusUseCase → onLogisticsStatusChanged()
 * - CreateCashFlowUseCase / UpdateCashFlowUseCase → onCashFlowChanged()
 */
@Singleton
class VirtualContractStateMachineUseCase @Inject constructor(
    private val vcRepo: VirtualContractRepository,
    private val cashFlowRepo: CashFlowRepository,
    private val inventoryRepo: EquipmentInventoryRepository,
    private val logRepo: VCStatusLogRepository
) {
    companion object {
        // threshold for floating point comparison
        private const val EPSILON = 0.01
    }

    // ==================== 物流状态变更入口 ====================

    /**
     * 物流状态变更 → 镜像到 VC subjectStatus
     *
     * 映射规则：
     * - IN_TRANSIT → SHIPPED
     * - SIGNED → SIGNED
     * - COMPLETED → COMPLETED
     * - 其他 → EXECUTING
     *
     * 退货 VC 的物流 COMPLETED 还会触发原合同押金重算
     */
    suspend fun onLogisticsStatusChanged(vcId: Long, logisticsStatus: LogisticsStatus) {
        val vc = vcRepo.getById(vcId) ?: return

        val newSubjectStatus = when (logisticsStatus) {
            LogisticsStatus.IN_TRANSIT -> SubjectStatus.SHIPPED
            LogisticsStatus.SIGNED -> SubjectStatus.SIGNED
            LogisticsStatus.COMPLETED -> SubjectStatus.COMPLETED
            else -> SubjectStatus.EXECUTING
        }

        if (vc.subjectStatus == newSubjectStatus) return

        val updated = vc.copy(
            subjectStatus = newSubjectStatus,
            subjectStatusTimestamp = System.currentTimeMillis()
        )
        vcRepo.update(updated)
        logSubjectStatus(vcId, newSubjectStatus)

        // 重新加载 VC（因 update 后 getById 返回的是原对象）
        val reloaded = vcRepo.getById(vcId) ?: return
        recalculateOverallStatus(reloaded)

        // 退货 VC 物流 COMPLETED → 触发原合同押金重算（对标 Desktop deposit_module）
        if (vc.type == VCType.RETURN && newSubjectStatus == SubjectStatus.COMPLETED && vc.relatedVcId != null) {
            val originalVc = vcRepo.getById(vc.relatedVcId!!)
            if (originalVc != null && originalVc.type in listOf(VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK)) {
                processVcDeposit(originalVc)
            }
        }
    }

    // ==================== 资金流变更入口 ====================

    /**
     * 资金流变更 → 触发押金处理 + 资金状态重算
     *
     * @param vcId VC ID
     * @param cf 变更的资金流（可为 null，表示整体重算）
     */
    suspend fun onCashFlowChanged(vcId: Long, cf: CashFlow?) {
        val vc = vcRepo.getById(vcId) ?: return

        // 处理押金流水（DEPOSIT / DEPOSIT_REFUND）— 仅当有实际押金流水时处理
        val updatedVc = if (cf != null && (cf.type == CashFlowType.DEPOSIT || cf.type == CashFlowType.DEPOSIT_REFUND)) {
            processCfDeposit(vc, cf)
        } else {
            vc
        }

        // 重算 shouldReceive（仅当有押金流水变更时）
        if (cf != null && cf.type in listOf(CashFlowType.DEPOSIT, CashFlowType.DEPOSIT_REFUND)) {
            if (updatedVc.type in listOf(VCType.EQUIPMENT_PROCUREMENT, VCType.EQUIPMENT_STOCK)) {
                processVcDeposit(updatedVc)
            }
        }

        if (updatedVc.type == VCType.RETURN) {
            // RETURN VC: 由 processReturnVcAutoComplete 单独处理完成判断
            val cashFlows = cashFlowRepo.getByVcId(updatedVc.id).first()
            processReturnVcAutoComplete(updatedVc, cashFlows)
        } else {
            // 非 RETURN VC: 重算资金状态 + 整体状态
            val vcAfterCashStatus = recalculateCashStatus(updatedVc)
            recalculateOverallStatus(vcAfterCashStatus)
        }
    }

    // ==================== 押金流水处理 ====================

    /**
     * 处理单笔押金流水（DEPOSIT 增加 / DEPOSIT_REFUND 减少）
     *
     * 退货 VC 的押金流水重定向到原合同
     * @return 更新后的 VC（包含 actualDeposit 变更）
     */
    private suspend fun processCfDeposit(vc: VirtualContract, cf: CashFlow): VirtualContract {
        val targetVcId = if (vc.type == VCType.RETURN && vc.relatedVcId != null) {
            // 退货 VC：押金流水重定向到原合同
            vc.relatedVcId!!
        } else {
            vc.id
        }

        val targetVc = if (targetVcId != vc.id) {
            vcRepo.getById(targetVcId) ?: return vc
        } else {
            vc
        }

        val delta = when (cf.type) {
            CashFlowType.DEPOSIT -> cf.amount
            CashFlowType.DEPOSIT_REFUND -> -cf.amount
            else -> return targetVc
        }

        val newActualDeposit = (targetVc.depositInfo.actualDeposit + delta).coerceAtLeast(0.0)
        val updated = targetVc.copy(
            depositInfo = targetVc.depositInfo.copy(actualDeposit = newActualDeposit)
        )
        vcRepo.update(updated)

        // 返回更新后的 VC（供后续方法使用）
        // 若 targetVcId == vc.id，targetVc 就是 vc，需要重新加载以获取更新后的数据
        return if (targetVcId != vc.id) {
            updated
        } else {
            vcRepo.getById(vc.id) ?: updated
        }
    }

    // ==================== shouldReceive 重算 ====================

    /**
     * 重算 shouldReceive 并分配押金到运营中设备
     *
     * 规则（对应 Desktop calculate_should_receive）：
     * - 无运营中设备 → 基于 VC.elements 合同计划计算
     * - 有运营中设备 → 基于运营中设备的约定押金计算
     */
    private suspend fun processVcDeposit(vc: VirtualContract) {
        val inventories = inventoryRepo.getByVcId(vc.id).first()
        val operatingEquipments = inventories.filter { it.operationalStatus == OperationalStatus.IN_OPERATION }

        val newShouldReceive = calculateShouldReceive(vc, operatingEquipments)

        val updated: VirtualContract
        val shouldUpdateVc = newShouldReceive != vc.depositInfo.shouldReceive

        if (shouldUpdateVc) {
            updated = vc.copy(
                depositInfo = vc.depositInfo.copy(shouldReceive = newShouldReceive)
            )
            vcRepo.update(updated)
        } else {
            updated = vc
        }

        // 分摊押金到运营中设备（actualDeposit 可能已被 processCfDeposit 更新，即使 shouldReceive 不变也要执行）
        if (operatingEquipments.isNotEmpty()) {
            distributeDepositToInventory(updated, operatingEquipments)
        }
    }

    /**
     * 计算 shouldReceive
     *
     * 有运营设备：= Σ(运营中设备的 depositAmount)
     * 无运营设备：= Σ(VC.elements 中各 SKU 的 deposit × 数量)
     *
     * 注意：退货 VC 的 shouldReceive 基于退货元素的 depositAmount 字段
     */
    private fun calculateShouldReceive(
        vc: VirtualContract,
        operatingEquipments: List<EquipmentInventory>
    ): Double {
        if (operatingEquipments.isNotEmpty()) {
            // 基于运营中设备
            return operatingEquipments.sumOf { it.depositAmount }
        }

        // 基于合同计划（VC.elements）
        if (vc.elements.isEmpty()) return 0.0

        return when (vc.type) {
            VCType.RETURN -> {
                // 退货VC：shouldReceive基于元素的depositAmount字段
                // ReturnElement.depositAmount是独立字段（可空），deposit固定为0.0
                vc.elements.sumOf { elem ->
                    val re = elem as? ReturnElement
                    // 优先使用depositAmount，若为null则使用0.0
                    (re?.depositAmount ?: 0.0)
                }
            }
            else -> {
                // 其他VC：使用统一的deposit字段
                vc.elements.sumOf { it.deposit * it.quantity }
            }
        }
    }

    /**
     * 将 actualDeposit 按比例分摊到运营中设备
     *
     * ratio = actualDeposit / shouldReceive（若 shouldReceive > EPSILON）
     * 若 shouldReceive=0，则 ratio=1.0（所有设备获得全额押金）
     * 设备 deposit = 约定 depositAmount × ratio
     */
    private suspend fun distributeDepositToInventory(
        vc: VirtualContract,
        operatingEquipments: List<EquipmentInventory>
    ) {
        val shouldReceive = vc.depositInfo.shouldReceive

        val ratio = if (shouldReceive > EPSILON) {
            vc.depositInfo.actualDeposit / shouldReceive
        } else {
            // shouldReceive=0 时，所有设备获得全额押金
            1.0
        }

        for (inv in operatingEquipments) {
            val newDeposit = inv.depositAmount * ratio
            val updated = inv.copy(depositAmount = newDeposit)
            inventoryRepo.update(updated)
        }
    }

    // ==================== 资金状态重算 ====================

    /**
     * 重算 VC cashStatus
     *
     * 规则（对应 Desktop recalculate_cash_status）：
     * - paidGoods >= totalAmount AND actualNetDeposit >= depDue → COMPLETED
     * - paidGoods >= totalAmount AND ratio >= prepaymentRatio → PREPAID
     * - 否则 → EXECUTING
     *
     * paidGoods = Σ(PERFORMANCE) + Σ(PREPAYMENT) + Σ(REFUND)
     * actualNetDeposit = actualDeposit - totalReturnDeposit
     * ratio = maxOf(prepaymentRatio, expectedDeposit / totalAmount)（预付比例取 explicit 或 implicit）
     *
     * 注意：RETURN VC 的 COMPLETED 由 processReturnVcAutoComplete 单独处理，不在此判断
     * @return 更新后的 VC（包含新的 cashStatus）
     */
    private suspend fun recalculateCashStatus(vc: VirtualContract): VirtualContract {
        // RETURN VC 的 cashStatus 不在此管理（由 processReturnVcAutoComplete 处理）
        if (vc.type == VCType.RETURN) return vc

        val cashFlows = cashFlowRepo.getByVcId(vc.id).first()
        val returnVcs = vcRepo.getByRelatedVcId(vc.id).first()

        // 计算 paidGoods
        val paidGoods = cashFlows
            .filter { it.type in listOf(CashFlowType.PERFORMANCE, CashFlowType.PREPAYMENT, CashFlowType.REFUND, CashFlowType.OFFSET_OUTFLOW) }
            .sumOf { it.amount }

        // 计算 actualNetDeposit（从 cash flows 直接计算，而非依赖 depositInfo.actualDeposit）
        val paidDeposit = cashFlows
            .filter { it.type == CashFlowType.DEPOSIT }
            .sumOf { it.amount }
        val totalReturnDeposit = returnVcs
            .filter { it.status == VCStatus.EXECUTING || it.status == VCStatus.COMPLETED }
            .sumOf { rc ->
                cashFlowRepo.getByVcId(rc.id).first()
                    .filter { it.type == CashFlowType.DEPOSIT_REFUND }
                    .sumOf { it.amount }
            }
        val actualNetDeposit = paidDeposit - totalReturnDeposit

        val totalAmount = vc.depositInfo.totalAmount
        val depDue = vc.depositInfo.shouldReceive
        val expectedDeposit = vc.depositInfo.expectedDeposit
        val prepaymentRatio = vc.depositInfo.prepaymentRatio

        // ratio = explicit prepaymentRatio 或 implicit (expectedDeposit / totalAmount)
        val ratio = if (totalAmount > EPSILON) {
            maxOf(prepaymentRatio, expectedDeposit / totalAmount)
        } else {
            prepaymentRatio
        }

        val newCashStatus = when {
            // 货款结清且押金结清 → COMPLETED
            paidGoods >= totalAmount - EPSILON && actualNetDeposit >= depDue - EPSILON -> {
                CashStatus.COMPLETED
            }
            // 货款结清或预付比例达标 → PREPAID
            // ratio > EPSILON 确保在 explicit prepaymentRatio=0 且 expectedDeposit=0 时不误触发
            totalAmount > EPSILON && ratio > EPSILON && paidGoods >= (totalAmount * ratio) - EPSILON -> {
                CashStatus.PREPAID
            }
            else -> CashStatus.EXECUTING
        }

        if (newCashStatus != vc.cashStatus) {
            val updated = vc.copy(
                cashStatus = newCashStatus,
                cashStatusTimestamp = System.currentTimeMillis()
            )
            vcRepo.update(updated)
            return updated
        }

        return vc
    }

    /**
     * 退货 VC 自动完成
     *
     * 条件：depDue 充足（原合同 actualNetDeposit >= 原合同 depDue）
     * 且退货 VC 无资金流水 → status → COMPLETED
     */
    private suspend fun processReturnVcAutoComplete(vc: VirtualContract, cashFlows: List<CashFlow>) {
        if (vc.status == VCStatus.COMPLETED) return
        if (vc.subjectStatus != SubjectStatus.COMPLETED) return
        if (vc.cashStatus != CashStatus.EXECUTING) return
        if (cashFlows.isNotEmpty()) return

        val originalVc = vc.relatedVcId?.let { vcRepo.getById(it) } ?: return

        // 计算原合同 actualNetDeposit
        val returnVcs = vcRepo.getByRelatedVcId(originalVc.id).first()
        val totalReturnDeposit = returnVcs
            .filter { it.id != vc.id }
            .sumOf { rc ->
                cashFlowRepo.getByVcId(rc.id).first()
                    .filter { it.type == CashFlowType.DEPOSIT_REFUND }
                    .sumOf { it.amount }
            }
        val actualNetDeposit = originalVc.depositInfo.actualDeposit - totalReturnDeposit
        val depDue = originalVc.depositInfo.shouldReceive

        if (actualNetDeposit >= depDue - EPSILON) {
            val updated = vc.copy(
                status = VCStatus.COMPLETED,
                statusTimestamp = System.currentTimeMillis()
            )
            vcRepo.update(updated)
        }
    }

    // ==================== 整体状态重算 ====================

    /**
     * 重新计算 VC 主状态
     *
     * subjectStatus==COMPLETED AND cashStatus==COMPLETED → status==COMPLETED
     */
    private suspend fun recalculateOverallStatus(vc: VirtualContract) {
        if (vc.status == VCStatus.COMPLETED) return

        if (vc.subjectStatus == SubjectStatus.COMPLETED && vc.cashStatus == CashStatus.COMPLETED) {
            val updated = vc.copy(
                status = VCStatus.COMPLETED,
                statusTimestamp = System.currentTimeMillis()
            )
            vcRepo.update(updated)
        }
    }

    // ==================== 日志 ====================

    private suspend fun logSubjectStatus(vcId: Long, status: SubjectStatus) {
        try {
            val log = VCStatusLog(
                vcId = vcId,
                category = StatusLogCategory.SUBJECT,
                statusName = status.name
            )
            logRepo.insert(log)
        } catch (e: Exception) {
            // 日志失败不影响主流程
        }
    }

    private suspend fun logCashStatus(vcId: Long, status: CashStatus) {
        try {
            val log = VCStatusLog(
                vcId = vcId,
                category = StatusLogCategory.CASH,
                statusName = status.name
            )
            logRepo.insert(log)
        } catch (e: Exception) {
            // 日志失败不影响主流程
        }
    }
}
