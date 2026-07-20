package com.shanyin.erp.ui.screens.logistics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.ExpressOrderRepository
import com.shanyin.erp.domain.repository.LogisticsRepository
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

data class LogisticsUiState(
    val logisticsList: List<Logistics> = emptyList(),
    val expressOrders: List<ExpressOrder> = emptyList(),
    val virtualContracts: List<VirtualContract> = emptyList(),
    val skus: List<Sku> = emptyList(),
    val points: List<Point> = emptyList(),
    val isLoading: Boolean = true,
    val selectedTab: Int = 0, // 0=全部, 1=待发货, 2=在途, 3=签收, 4=完成
    val showCreateLogisticsDialog: Boolean = false,
    val showLogisticsDetailDialog: Boolean = false,
    val showExpressOrderDialog: Boolean = false,
    val showWarehouseConfirmDialog: Boolean = false,
    val showConfirmInboundDialog: Boolean = false,
    val showVcElementsDialog: Boolean = false,
    val showExpressOrderSuggestionsDialog: Boolean = false,
    val selectedLogistics: Logistics? = null,
    val selectedVc: VirtualContract? = null,
    val expressOrderSuggestions: List<ExpressOrderSuggestion> = emptyList(),
    val error: String? = null,
    val successMessage: String? = null,
    val refreshVersion: Long = 0L // 用于调试刷新
)

@HiltViewModel
class LogisticsViewModel @Inject constructor(
    private val getAllLogistics: GetAllLogisticsUseCase,
    private val getAllExpressOrders: GetAllExpressOrdersUseCase,
    private val getAllVirtualContracts: GetAllVirtualContractsUseCase,
    private val getAllSkus: GetAllSkusUseCase,
    private val getAllPoints: GetAllPointsUseCase,
    private val createLogisticsUseCase: CreateLogisticsUseCase,
    private val deleteLogisticsUseCase: DeleteLogisticsUseCase,
    private val createExpressOrderUseCase: CreateExpressOrderUseCase,
    private val updateExpressOrderStatusUseCase: UpdateExpressOrderStatusUseCase,
    private val updateExpressOrderTrackingUseCase: UpdateExpressOrderTrackingUseCase,
    private val deleteExpressOrderUseCase: DeleteExpressOrderUseCase,
    private val confirmInboundUseCase: ConfirmInboundUseCase,
    private val generateExpressOrderSuggestions: GenerateExpressOrderSuggestionsUseCase,
    private val bulkProgressExpressOrdersUseCase: BulkProgressExpressOrdersUseCase,
    // 直接注入 Repository 用于强制刷新
    private val logisticsRepository: LogisticsRepository,
    private val expressOrderRepository: ExpressOrderRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(LogisticsUiState())
    val uiState: StateFlow<LogisticsUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        // 只加载一次初始数据，不持续监听 Flow
        // 所有后续更新通过 refreshLogisticsInternal() 显式触发
        viewModelScope.launch {
            try {
                val logistics = getAllLogistics().first()
                val expressOrders = getAllExpressOrders().first()
                val vcs = getAllVirtualContracts().first()
                val skus = getAllSkus().first()
                val points = getAllPoints().first()
                _uiState.update {
                    it.copy(
                        logisticsList = logistics,
                        expressOrders = expressOrders,
                        virtualContracts = vcs,
                        skus = skus,
                        points = points,
                        isLoading = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = "加载数据失败: ${e.message}", isLoading = false) }
            }
        }
    }

    fun setSelectedTab(tab: Int) {
        _uiState.update { it.copy(selectedTab = tab) }
    }

    /**
     * 刷新物流列表数据 - 使用直接数据库查询强制获取最新数据
     * 改为 suspend 函数，确保刷新完成后再返回
     */
    private suspend fun refreshLogisticsInternal() {
        withContext(Dispatchers.IO) {
            try {
                val logistics = logisticsRepository.getAllDirect()
                val expressOrders = expressOrderRepository.getAllDirect()
                val vcs = getAllVirtualContracts().first()
                val skus = getAllSkus().first()
                val points = getAllPoints().first()
                withContext(Dispatchers.Main) {
                    _uiState.update {
                        it.copy(
                            logisticsList = logistics,
                            expressOrders = expressOrders,
                            virtualContracts = vcs,
                            skus = skus,
                            points = points,
                            isLoading = false,
                            refreshVersion = it.refreshVersion + 1
                        )
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    _uiState.update { it.copy(error = "刷新失败: ${e.message}") }
                }
            }
        }
    }

    fun getFilteredLogistics(): List<Logistics> {
        val list = _uiState.value.logisticsList
        return when (_uiState.value.selectedTab) {
            1 -> list.filter { it.status == LogisticsStatus.PENDING }
            2 -> list.filter { it.status == LogisticsStatus.IN_TRANSIT }
            3 -> list.filter { it.status == LogisticsStatus.SIGNED }
            4 -> list.filter { it.status == LogisticsStatus.COMPLETED }
            else -> list
        }
    }

    fun showCreateLogisticsDialog() {
        _uiState.update { it.copy(showCreateLogisticsDialog = true) }
    }

    fun dismissCreateLogisticsDialog() {
        _uiState.update { it.copy(showCreateLogisticsDialog = false) }
    }

    fun showLogisticsDetailDialog(logistics: Logistics) {
        _uiState.update { it.copy(showLogisticsDetailDialog = true, selectedLogistics = logistics) }
    }

    fun dismissLogisticsDetailDialog() {
        _uiState.update { it.copy(showLogisticsDetailDialog = false, selectedLogistics = null) }
    }

    fun showExpressOrderDialog(logisticsId: Long) {
        _uiState.update { it.copy(showExpressOrderDialog = true) }
    }

    fun dismissExpressOrderDialog() {
        _uiState.update { it.copy(showExpressOrderDialog = false) }
    }

    fun showWarehouseConfirmDialog() {
        _uiState.update { it.copy(showWarehouseConfirmDialog = true) }
    }

    fun dismissWarehouseConfirmDialog() {
        _uiState.update { it.copy(showWarehouseConfirmDialog = false) }
    }

    fun showConfirmInboundDialog() {
        _uiState.update { it.copy(showConfirmInboundDialog = true) }
    }

    fun dismissConfirmInboundDialog() {
        _uiState.update { it.copy(showConfirmInboundDialog = false) }
    }

    fun showVcElementsDialog(vcId: Long) {
        val vc = _uiState.value.virtualContracts.find { it.id == vcId }
        _uiState.update { it.copy(showVcElementsDialog = true, selectedVc = vc) }
    }

    fun dismissVcElementsDialog() {
        _uiState.update { it.copy(showVcElementsDialog = false, selectedVc = null) }
    }

    /**
     * 生成快递单建议
     */
    fun generateExpressOrderSuggestions(vc: VirtualContract) {
        viewModelScope.launch {
            try {
                val suggestions = this@LogisticsViewModel.generateExpressOrderSuggestions.invoke(vc)
                _uiState.update {
                    it.copy(
                        showExpressOrderSuggestionsDialog = true,
                        expressOrderSuggestions = suggestions
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun dismissExpressOrderSuggestionsDialog() {
        _uiState.update {
            it.copy(
                showExpressOrderSuggestionsDialog = false,
                expressOrderSuggestions = emptyList()
            )
        }
    }

    fun updateSuggestionTrackingNumber(index: Int, trackingNumber: String) {
        _uiState.update { state ->
            val updated = state.expressOrderSuggestions.toMutableList()
            if (index in updated.indices) {
                updated[index] = updated[index].copy(trackingNumber = trackingNumber)
            }
            state.copy(expressOrderSuggestions = updated)
        }
    }

    /**
     * 确认生成快递单（批量创建）
     *
     * 直接调用 UseCase 而非 ViewModel 方法，避免嵌套 coroutine 导致 OOM
     */
    fun confirmExpressOrderSuggestions(logisticsId: Long) {
        viewModelScope.launch {
            try {
                val suggestions = _uiState.value.expressOrderSuggestions
                // 直接调用 UseCase，避免嵌套 viewModelScope.launch
                for (suggestion in suggestions) {
                    createExpressOrderUseCase(
                        logisticsId = logisticsId,
                        trackingNumber = suggestion.trackingNumber.takeIf { it.isNotBlank() },
                        items = suggestion.items,
                        addressInfo = suggestion.addressInfo
                    )
                }
                dismissExpressOrderSuggestionsDialog()
                // 同步等待刷新完成
                refreshLogisticsInternal()
                _uiState.update { it.copy(successMessage = "已生成 ${suggestions.size} 个快递单") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun confirmInbound(logisticsId: Long, snList: List<String>) {
        viewModelScope.launch {
            try {
                confirmInboundUseCase(logisticsId, snList)
                dismissConfirmInboundDialog()
                _uiState.update { it.copy(successMessage = "入库确认成功，库存已创建") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun createLogisticsRecord(virtualContractId: Long) {
        viewModelScope.launch {
            try {
                val logisticsId = createLogisticsUseCase(virtualContractId)
                dismissCreateLogisticsDialog()
                // 重新从数据库加载所有数据
                val allLogistics = withContext(Dispatchers.IO) {
                    getAllLogistics().first()
                }
                _uiState.value = _uiState.value.copy(
                    logisticsList = allLogistics,
                    refreshVersion = _uiState.value.refreshVersion + 1,
                    successMessage = "物流记录创建成功"
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message)
            }
        }
    }

    fun deleteLogisticsRecord(logistics: Logistics) {
        viewModelScope.launch {
            try {
                deleteLogisticsUseCase(logistics)
                dismissLogisticsDetailDialog()
                // 重新从数据库加载所有数据
                val allLogistics = withContext(Dispatchers.IO) {
                    getAllLogistics().first()
                }
                val allExpressOrders = withContext(Dispatchers.IO) {
                    getAllExpressOrders().first()
                }
                _uiState.value = _uiState.value.copy(
                    logisticsList = allLogistics,
                    expressOrders = allExpressOrders,
                    refreshVersion = _uiState.value.refreshVersion + 1,
                    successMessage = "物流记录已删除"
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message)
            }
        }
    }

    /**
     * 创建快递单（UI 入口包装）
     *
     * 包含刷新逻辑，供单个快递单创建时调用
     */
    fun createExpressOrderRecord(
        logisticsId: Long,
        trackingNumber: String?,
        items: List<ExpressItem>,
        addressInfo: AddressInfo
    ) {
        viewModelScope.launch {
            try {
                createExpressOrderUseCase(logisticsId, trackingNumber, items, addressInfo)
                dismissExpressOrderDialog()
                // 同步等待刷新完成
                refreshLogisticsInternal()
                _uiState.update { it.copy(successMessage = "快递单创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateExpressOrderStatusAction(expressOrderId: Long, status: ExpressStatus) {
        viewModelScope.launch {
            try {
                updateExpressOrderStatusUseCase(expressOrderId, status)
                _uiState.update { it.copy(successMessage = "快递状态已更新") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateExpressOrderTrackingAction(expressOrderId: Long, trackingNumber: String) {
        viewModelScope.launch {
            try {
                updateExpressOrderTrackingUseCase(expressOrderId, trackingNumber)
                _uiState.update { it.copy(successMessage = "运单号已更新") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteExpressOrderAction(expressOrder: ExpressOrder) {
        viewModelScope.launch {
            try {
                deleteExpressOrderUseCase(expressOrder)
                // 同步等待刷新完成，避免 Flow 覆盖状态
                refreshLogisticsInternal()
                _uiState.update { it.copy(successMessage = "快递单已删除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    /**
     * 批量推进快递单状态
     *
     * @param logisticsId 物流单ID
     * @param expressOrderIds 要更新的快递单ID列表
     * @param targetStatus 目标状态
     */
    fun bulkProgressExpressOrdersAction(logisticsId: Long, expressOrderIds: List<Long>, targetStatus: ExpressStatus) {
        viewModelScope.launch {
            try {
                val count = bulkProgressExpressOrdersUseCase(logisticsId, expressOrderIds, targetStatus)
                // 同步等待刷新完成
                refreshLogisticsInternal()
                _uiState.update { it.copy(successMessage = "已批量推进 $count 个快递单至 ${targetStatus.displayName}") }
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
