package com.shanyin.erp.ui.screens.inventory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class InventoryUiState(
    val equipmentList: List<EquipmentInventory> = emptyList(),
    val materialList: List<MaterialInventory> = emptyList(),
    val skus: List<Sku> = emptyList(),
    val virtualContracts: List<VirtualContract> = emptyList(),
    val points: List<Point> = emptyList(),
    val isLoading: Boolean = true,
    val selectedTab: Int = 0, // 0=设备, 1=物料
    val showEquipmentDialog: Boolean = false,
    val showMaterialDialog: Boolean = false,
    val showDetailDialog: Boolean = false,
    val showTransferDialog: Boolean = false,
    val selectedEquipment: EquipmentInventory? = null,
    val selectedMaterial: MaterialInventory? = null,
    val error: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class InventoryViewModel @Inject constructor(
    private val getAllEquipmentInventory: GetAllEquipmentInventoryUseCase,
    private val getAllMaterialInventory: GetAllMaterialInventoryUseCase,
    private val getAllSkus: GetAllSkusUseCase,
    private val getAllVirtualContracts: GetAllVirtualContractsUseCase,
    private val getAllPoints: GetAllPointsUseCase,
    private val saveEquipmentInventory: SaveEquipmentInventoryUseCase,
    private val deleteEquipmentInventory: DeleteEquipmentInventoryUseCase,
    private val updateEquipmentStatus: UpdateEquipmentStatusUseCase,
    private val saveMaterialInventory: SaveMaterialInventoryUseCase,
    private val deleteMaterialInventory: DeleteMaterialInventoryUseCase,
    private val updateStockDistribution: UpdateStockDistributionUseCase,
    private val transferInventory: TransferInventoryUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(InventoryUiState())
    val uiState: StateFlow<InventoryUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        viewModelScope.launch {
            combine(
                getAllEquipmentInventory(),
                getAllMaterialInventory(),
                getAllSkus(),
                getAllVirtualContracts(),
                getAllPoints()
            ) { equipment, material, skus, vcs, points ->
                _uiState.update {
                    it.copy(
                        equipmentList = equipment,
                        materialList = material,
                        skus = skus,
                        virtualContracts = vcs,
                        points = points,
                        isLoading = false
                    )
                }
            }.collect()
        }
    }

    fun setSelectedTab(tab: Int) {
        _uiState.update { it.copy(selectedTab = tab) }
    }

    fun showEquipmentDialog() {
        _uiState.update { it.copy(showEquipmentDialog = true) }
    }

    fun dismissEquipmentDialog() {
        _uiState.update { it.copy(showEquipmentDialog = false) }
    }

    fun showMaterialDialog() {
        _uiState.update { it.copy(showMaterialDialog = true) }
    }

    fun dismissMaterialDialog() {
        _uiState.update { it.copy(showMaterialDialog = false) }
    }

    fun showEquipmentDetailDialog(equipment: EquipmentInventory) {
        _uiState.update { it.copy(showDetailDialog = true, selectedEquipment = equipment) }
    }

    fun showMaterialDetailDialog(material: MaterialInventory) {
        _uiState.update { it.copy(showDetailDialog = true, selectedMaterial = material) }
    }

    fun dismissDetailDialog() {
        _uiState.update { it.copy(showDetailDialog = false, selectedEquipment = null, selectedMaterial = null) }
    }

    fun showTransferDialog() {
        _uiState.update { it.copy(showTransferDialog = true) }
    }

    fun dismissTransferDialog() {
        _uiState.update { it.copy(showTransferDialog = false) }
    }

    fun createEquipment(
        skuId: Long?,
        sn: String?,
        operationalStatus: OperationalStatus,
        deviceStatus: DeviceStatus,
        virtualContractId: Long?,
        pointId: Long?,
        depositAmount: Double
    ) {
        viewModelScope.launch {
            try {
                val sku = skuId?.let { _uiState.value.skus.find { s -> s.id == it } }
                val vc = virtualContractId?.let { _uiState.value.virtualContracts.find { v -> v.id == it } }
                val point = pointId?.let { _uiState.value.points.find { p -> p.id == it } }

                val equipment = EquipmentInventory(
                    skuId = skuId,
                    skuName = sku?.name,
                    sn = sn,
                    operationalStatus = operationalStatus,
                    deviceStatus = deviceStatus,
                    virtualContractId = virtualContractId,
                    vcTypeName = vc?.type?.displayName,
                    pointId = pointId,
                    pointName = point?.name,
                    depositAmount = depositAmount,
                    depositTimestamp = if (depositAmount > 0) System.currentTimeMillis() else null
                )
                saveEquipmentInventory(equipment)
                dismissEquipmentDialog()
                _uiState.update { it.copy(successMessage = "设备库存创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateEquipmentStatus(
        equipmentId: Long,
        operationalStatus: OperationalStatus? = null,
        deviceStatus: DeviceStatus? = null
    ) {
        viewModelScope.launch {
            try {
                updateEquipmentStatus(equipmentId, operationalStatus, deviceStatus)
                _uiState.update { it.copy(successMessage = "设备状态已更新") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteEquipment(equipment: EquipmentInventory) {
        viewModelScope.launch {
            try {
                deleteEquipmentInventory(equipment)
                dismissDetailDialog()
                _uiState.update { it.copy(successMessage = "设备库存已删除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun createMaterial(
        skuId: Long,
        pointId: Long,
        pointName: String,
        quantity: Int,
        averagePrice: Double
    ) {
        viewModelScope.launch {
            try {
                updateStockDistribution(skuId, pointId, pointName, quantity, averagePrice)
                dismissMaterialDialog()
                _uiState.update { it.copy(successMessage = "物料库存创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateMaterialStock(
        skuId: Long,
        pointId: Long,
        pointName: String,
        quantity: Int,
        averagePrice: Double
    ) {
        viewModelScope.launch {
            try {
                updateStockDistribution(skuId, pointId, pointName, quantity, averagePrice)
                _uiState.update { it.copy(successMessage = "库存已更新") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun transferMaterial(
        skuId: Long,
        fromPointId: Long,
        fromPointName: String,
        toPointId: Long,
        toPointName: String,
        quantity: Int
    ) {
        viewModelScope.launch {
            try {
                transferInventory(skuId, fromPointId, fromPointName, toPointId, toPointName, quantity)
                dismissTransferDialog()
                _uiState.update { it.copy(successMessage = "库存调拨成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteMaterial(material: MaterialInventory) {
        viewModelScope.launch {
            try {
                deleteMaterialInventory(material)
                dismissDetailDialog()
                _uiState.update { it.copy(successMessage = "物料库存已删除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    fun clearSuccessMessage() {
        _uiState.update { it.copy(successMessage = null) }
    }
}
