package com.shanyin.erp.ui.screens.vc

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class VirtualContractListUiState(
    val allVCs: List<VirtualContract> = emptyList(),
    val businesses: List<Business> = emptyList(),
    val skus: List<Sku> = emptyList(),
    val customers: List<ChannelCustomer> = emptyList(),
    val supplyChains: List<SupplyChain> = emptyList(),
    val isLoading: Boolean = true,
    val showCreateDialog: Boolean = false,
    val showDetailDialog: Boolean = false,
    val selectedVC: VirtualContract? = null,
    val selectedTab: Int = 0, // 0=全部, 1=执行中, 2=已完成, 3=已终止
    val error: String? = null,
    val successMessage: String? = null,
    // 物流方案建议
    val showLogisticsSuggestionsDialog: Boolean = false,
    val logisticsSuggestions: List<ExpressOrderSuggestion> = emptyList(),
    val isGeneratingSuggestions: Boolean = false,
    val logisticsSuggestionsVc: VirtualContract? = null  // 保存生成建议时用的 VC，避免 selectedVC 被清空后崩溃
) {
    val filteredVCs: List<VirtualContract>
        get() = when (selectedTab) {
            1 -> allVCs.filter { it.status == VCStatus.EXECUTING }
            2 -> allVCs.filter { it.status == VCStatus.COMPLETED }
            3 -> allVCs.filter { it.status == VCStatus.TERMINATED }
            else -> allVCs
        }
}

@HiltViewModel
class VirtualContractListViewModel @Inject constructor(
    private val getAllVCs: GetAllVirtualContractsUseCase,
    private val getAllBusinesses: GetAllBusinessesUseCase,
    private val getAllSkus: GetAllSkusUseCase,
    private val getAllCustomers: GetAllCustomersUseCase,
    private val getAllSupplyChains: GetAllSupplyChainsUseCase,
    private val saveVC: SaveVirtualContractUseCase,
    private val updateVCStatus: UpdateVCStatusUseCase,
    private val updateVCSubjectStatus: UpdateVCSubjectStatusUseCase,
    private val updateVCCashStatus: UpdateVCCashStatusUseCase,
    private val completeVC: CompleteVirtualContractUseCase,
    private val terminateVC: TerminateVirtualContractUseCase,
    private val getVCStatusLogs: GetVCStatusLogsUseCase,
    private val getLogisticsByVc: GetLogisticsByVcUseCase,
    private val getEquipmentByVc: GetEquipmentInventoryByVcUseCase,
    // 物流相关
    private val createLogistics: CreateLogisticsUseCase,
    private val createExpressOrder: CreateExpressOrderUseCase,
    private val generateExpressOrderSuggestions: GenerateExpressOrderSuggestionsUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(VirtualContractListUiState())
    val uiState: StateFlow<VirtualContractListUiState> = _uiState.asStateFlow()

    private val _statusLogs = MutableStateFlow<List<VCStatusLog>>(emptyList())
    val statusLogs: StateFlow<List<VCStatusLog>> = _statusLogs.asStateFlow()

    private val _selectedVcLogistics = MutableStateFlow<List<Logistics>>(emptyList())
    val selectedVcLogistics: StateFlow<List<Logistics>> = _selectedVcLogistics.asStateFlow()

    private val _selectedVcEquipment = MutableStateFlow<List<EquipmentInventory>>(emptyList())
    val selectedVcEquipment: StateFlow<List<EquipmentInventory>> = _selectedVcEquipment.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        viewModelScope.launch {
            combine(
                getAllVCs(),
                getAllBusinesses(),
                getAllSkus(),
                getAllCustomers(),
                getAllSupplyChains()
            ) { vcs, businesses, skus, customers, supplyChains ->
                _uiState.update {
                    it.copy(
                        allVCs = vcs,
                        businesses = businesses,
                        skus = skus,
                        customers = customers,
                        supplyChains = supplyChains,
                        isLoading = false
                    )
                }
            }.collect()
        }
    }

    fun setSelectedTab(tab: Int) {
        _uiState.update { it.copy(selectedTab = tab) }
    }

    fun showCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = true) }
    }

    fun dismissCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = false) }
    }

    fun showDetailDialog(vc: VirtualContract) {
        _uiState.update { it.copy(showDetailDialog = true, selectedVC = vc) }
        loadStatusLogs(vc.id)
        loadLogistics(vc.id)
        loadEquipment(vc.id)
    }

    fun dismissDetailDialog() {
        _uiState.update { it.copy(showDetailDialog = false, selectedVC = null) }
        _statusLogs.value = emptyList()
        _selectedVcLogistics.value = emptyList()
        _selectedVcEquipment.value = emptyList()
    }

    private fun loadStatusLogs(vcId: Long) {
        viewModelScope.launch {
            getVCStatusLogs(vcId).collect { logs ->
                _statusLogs.value = logs
            }
        }
    }

    private fun loadLogistics(vcId: Long) {
        viewModelScope.launch {
            getLogisticsByVc(vcId).collect { logistics ->
                _selectedVcLogistics.value = logistics
            }
        }
    }

    /**
     * 强制刷新物流数据（用于创建/删除快递单后）
     */
    private fun refreshLogistics(vcId: Long) {
        viewModelScope.launch {
            val logistics = getLogisticsByVc(vcId).first()
            _selectedVcLogistics.value = logistics
        }
    }

    private fun loadEquipment(vcId: Long) {
        viewModelScope.launch {
            getEquipmentByVc(vcId).collect { equipment ->
                _selectedVcEquipment.value = equipment
            }
        }
    }

    fun getBusinessNameForVc(vc: VirtualContract): String? {
        val businessId = vc.businessId ?: return null
        val business = _uiState.value.businesses.find { it.id == businessId } ?: return null
        val customerId = business.customerId ?: return null
        return _uiState.value.customers.find { it.id == customerId }?.name
    }

    fun getSupplierNameForVc(vc: VirtualContract): String? {
        val supplyChainId = vc.supplyChainId ?: return null
        return _uiState.value.supplyChains.find { it.id == supplyChainId }?.supplierName
    }

    fun createVC(
        type: VCType,
        businessId: Long?,
        description: String,
        elements: List<VCElement>,
        deposit: Double,
        returnDirection: ReturnDirection? = null,
        goodsAmount: Double = 0.0,
        depositAmount: Double = 0.0,
        totalRefund: Double = 0.0,
        reason: String? = null
    ) {
        viewModelScope.launch {
            try {
                val vc = VirtualContract(
                    businessId = businessId,
                    type = type,
                    description = description,
                    elements = elements,
                    depositInfo = DepositInfo(
                        expectedDeposit = deposit,
                        actualDeposit = deposit
                    ),
                    returnDirection = returnDirection,
                    goodsAmount = goodsAmount,
                    logisticsCost = 0.0,
                    logisticsBearer = null
                )
                saveVC(vc, "创建${type.displayName}合同")
                dismissCreateDialog()
                _uiState.update { it.copy(successMessage = "合同创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateStatus(vcId: Long, newStatus: VCStatus) {
        viewModelScope.launch {
            updateVCStatus(vcId, newStatus)
                .onSuccess { updatedVC ->
                    _uiState.update { state ->
                        state.copy(
                            selectedVC = updatedVC,
                            allVCs = state.allVCs.map { if (it.id == vcId) updatedVC else it }
                        )
                    }
                    _uiState.update { it.copy(successMessage = "状态已更新") }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message) }
                }
        }
    }

    fun updateSubjectStatus(vcId: Long, newStatus: SubjectStatus) {
        viewModelScope.launch {
            updateVCSubjectStatus(vcId, newStatus)
                .onSuccess { updatedVC ->
                    _uiState.update { state ->
                        state.copy(
                            selectedVC = updatedVC,
                            allVCs = state.allVCs.map { if (it.id == vcId) updatedVC else it }
                        )
                    }
                    _uiState.update { it.copy(successMessage = "标的物状态已更新") }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message) }
                }
        }
    }

    fun updateCashStatus(vcId: Long, newStatus: CashStatus) {
        viewModelScope.launch {
            updateVCCashStatus(vcId, newStatus)
                .onSuccess { updatedVC ->
                    _uiState.update { state ->
                        state.copy(
                            selectedVC = updatedVC,
                            allVCs = state.allVCs.map { if (it.id == vcId) updatedVC else it }
                        )
                    }
                    _uiState.update { it.copy(successMessage = "资金状态已更新") }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message) }
                }
        }
    }

    fun complete(vcId: Long) {
        viewModelScope.launch {
            completeVC(vcId)
                .onSuccess { updatedVC ->
                    _uiState.update { state ->
                        state.copy(
                            selectedVC = updatedVC,
                            allVCs = state.allVCs.map { if (it.id == vcId) updatedVC else it }
                        )
                    }
                    _uiState.update { it.copy(successMessage = "合同已完成") }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message) }
                }
        }
    }

    fun terminate(vcId: Long) {
        viewModelScope.launch {
            terminateVC(vcId)
                .onSuccess { updatedVC ->
                    _uiState.update { state ->
                        state.copy(
                            selectedVC = updatedVC,
                            allVCs = state.allVCs.map { if (it.id == vcId) updatedVC else it }
                        )
                    }
                    _uiState.update { it.copy(successMessage = "合同已终止") }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message) }
                }
        }
    }

    fun generateLogisticsSuggestions(vc: VirtualContract) {
        viewModelScope.launch {
            _uiState.update { it.copy(isGeneratingSuggestions = true, logisticsSuggestionsVc = vc) }
            try {
                val suggestions = generateExpressOrderSuggestions(vc)
                _uiState.update {
                    it.copy(
                        showLogisticsSuggestionsDialog = true,
                        logisticsSuggestions = suggestions,
                        isGeneratingSuggestions = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        error = "生成物流建议失败: ${e.message}",
                        isGeneratingSuggestions = false
                    )
                }
            }
        }
    }

    fun confirmLogisticsSuggestions() {
        Log.d("LogisticsDebug", "confirmLogisticsSuggestions: START")
        val vc = _uiState.value.logisticsSuggestionsVc
        if (vc == null || vc.id == 0L) {
            _uiState.update { it.copy(error = if (vc == null) "VC 信息已失效，请重新打开" else "VC 未保存，无法创建物流方案") }
            return
        }
        val suggestions = _uiState.value.logisticsSuggestions
        if (suggestions.isEmpty()) {
            _uiState.update { it.copy(error = "没有快递单建议") }
            return
        }

        // 复制数据到局部变量，避免闭包捕获问题
        val vcId = vc.id
        val suggestionsCount = suggestions.size
        val suggestionItems = suggestions.map { it }  // 深拷贝

        Log.d("LogisticsDebug", "confirmLogisticsSuggestions: vcId=$vcId, suggestionsCount=$suggestionsCount")

        // 先关闭对话框，让 UI 立即响应
        dismissLogisticsSuggestionsDialog()
        Log.d("LogisticsDebug", "confirmLogisticsSuggestions: dialog dismissed")

        viewModelScope.launch {
            try {
                Log.d("LogisticsDebug", "confirmLogisticsSuggestions: creating logistics...")
                // 1. 创建物流主单
                val logisticsId = createLogistics(vcId)
                Log.d("LogisticsDebug", "confirmLogisticsSuggestions: logisticsId=$logisticsId")

                // 2. 为每个建议创建快递单
                for (item in suggestionItems) {
                    Log.d("LogisticsDebug", "confirmLogisticsSuggestions: creating express order for ${item.trackingNumber}")
                    createExpressOrder(
                        logisticsId = logisticsId,
                        trackingNumber = item.trackingNumber,
                        items = item.items,
                        addressInfo = item.addressInfo
                    )
                    Log.d("LogisticsDebug", "confirmLogisticsSuggestions: express order created")
                }

                Log.d("LogisticsDebug", "confirmLogisticsSuggestions: all express orders created, updating UI")
                _uiState.update { it.copy(successMessage = "已生成 $suggestionsCount 个快递单") }
                Log.d("LogisticsDebug", "confirmLogisticsSuggestions: DONE")
            } catch (e: Exception) {
                Log.e("LogisticsDebug", "confirmLogisticsSuggestions: ERROR: ${e.message}", e)
                _uiState.update { it.copy(error = "创建物流方案失败: ${e.message}") }
            }
        }
    }

    fun dismissLogisticsSuggestionsDialog() {
        _uiState.update {
            it.copy(
                showLogisticsSuggestionsDialog = false,
                logisticsSuggestions = emptyList(),
                logisticsSuggestionsVc = null
            )
        }
    }

    fun updateSuggestionTrackingNumber(index: Int, newTrackingNumber: String) {
        _uiState.update { state ->
            val updated = state.logisticsSuggestions.toMutableList()
            if (index in updated.indices) {
                updated[index] = updated[index].copy(trackingNumber = newTrackingNumber)
            }
            state.copy(logisticsSuggestions = updated)
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    fun clearSuccessMessage() {
        _uiState.update { it.copy(successMessage = null) }
    }
}
