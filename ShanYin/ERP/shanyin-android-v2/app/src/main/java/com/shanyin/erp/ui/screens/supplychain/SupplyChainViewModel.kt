package com.shanyin.erp.ui.screens.supplychain

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SupplyChainListUiState(
    val supplyChains: List<SupplyChain> = emptyList(),
    val filteredSupplyChains: List<SupplyChain> = emptyList(),
    val suppliers: List<Supplier> = emptyList(),
    val skus: List<Sku> = emptyList(),
    val isLoading: Boolean = true,
    val showCreateDialog: Boolean = false,
    val showDetailDialog: Boolean = false,
    val showPricingDialog: Boolean = false,
    val selectedSupplyChain: SupplyChain? = null,
    val selectedTab: Int = 0, // 0=全部, 1=物料, 2=设备
    val error: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class SupplyChainListViewModel @Inject constructor(
    private val getAllSupplyChains: GetAllSupplyChainsUseCase,
    private val getAllSuppliers: GetAllSuppliersUseCase,
    private val getAllSkus: GetAllSkusUseCase,
    private val saveSupplyChain: SaveSupplyChainUseCase,
    private val deleteSupplyChain: DeleteSupplyChainUseCase,
    private val createSupplyChain: CreateSupplyChainUseCase,
    private val getSupplyChainItems: GetSupplyChainItemsUseCase,
    private val saveSupplyChainItem: SaveSupplyChainItemUseCase,
    private val deleteSupplyChainItem: DeleteSupplyChainItemUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(SupplyChainListUiState())
    val uiState: StateFlow<SupplyChainListUiState> = _uiState.asStateFlow()

    private val _supplyChainItems = MutableStateFlow<List<SupplyChainItem>>(emptyList())
    val supplyChainItems: StateFlow<List<SupplyChainItem>> = _supplyChainItems.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        viewModelScope.launch {
            combine(
                getAllSupplyChains(),
                getAllSuppliers(),
                getAllSkus()
            ) { supplyChains, suppliers, skus ->
                _uiState.update {
                    it.copy(
                        supplyChains = supplyChains,
                        filteredSupplyChains = filterSupplyChains(supplyChains, it.selectedTab),
                        suppliers = suppliers,
                        skus = skus,
                        isLoading = false
                    )
                }
            }.collect()
        }
    }

    fun setSelectedTab(tab: Int) {
        _uiState.update {
            it.copy(
                selectedTab = tab,
                filteredSupplyChains = filterSupplyChains(it.supplyChains, tab)
            )
        }
    }

    private fun filterSupplyChains(chains: List<SupplyChain>, tab: Int): List<SupplyChain> {
        return when (tab) {
            1 -> chains.filter { it.type == SupplyChainType.MATERIAL }
            2 -> chains.filter { it.type == SupplyChainType.EQUIPMENT }
            else -> chains
        }
    }

    fun showCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = true) }
    }

    fun dismissCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = false) }
    }

    fun showDetailDialog(supplyChain: SupplyChain) {
        _uiState.update { it.copy(showDetailDialog = true, selectedSupplyChain = supplyChain) }
        loadSupplyChainItems(supplyChain.id)
    }

    fun dismissDetailDialog() {
        _uiState.update { it.copy(showDetailDialog = false, selectedSupplyChain = null) }
        _supplyChainItems.value = emptyList()
    }

    fun showPricingDialog() {
        _uiState.update { it.copy(showPricingDialog = true) }
    }

    fun dismissPricingDialog() {
        _uiState.update { it.copy(showPricingDialog = false) }
    }

    private fun loadSupplyChainItems(supplyChainId: Long) {
        viewModelScope.launch {
            getSupplyChainItems(supplyChainId).collect { items ->
                _supplyChainItems.value = items
            }
        }
    }

    fun create(
        supplierId: Long,
        supplierName: String,
        type: SupplyChainType,
        items: List<SupplyChainItem>,
        prepaymentPercent: Double,
        paymentDays: Int
    ) {
        viewModelScope.launch {
            try {
                val paymentTerms = PaymentTerms(
                    prepaymentPercent = prepaymentPercent,
                    paymentDays = paymentDays
                )
                createSupplyChain(
                    supplierId = supplierId,
                    supplierName = supplierName,
                    type = type,
                    items = items,
                    paymentTerms = paymentTerms
                )
                dismissCreateDialog()
                _uiState.update { it.copy(successMessage = "供应链创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun addSkuPricing(
        skuId: Long,
        skuName: String,
        price: Double,
        deposit: Double,
        isFloating: Boolean
    ) {
        val supplyChain = _uiState.value.selectedSupplyChain ?: return
        viewModelScope.launch {
            try {
                val item = SupplyChainItem(
                    supplyChainId = supplyChain.id,
                    skuId = skuId,
                    skuName = skuName,
                    price = price,
                    deposit = deposit,
                    isFloating = isFloating
                )
                saveSupplyChainItem(item)
                _uiState.update { it.copy(successMessage = "SKU定价已添加") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun removeSkuPricing(item: SupplyChainItem) {
        viewModelScope.launch {
            try {
                deleteSupplyChainItem(item)
                _uiState.update { it.copy(successMessage = "SKU定价已移除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(supplyChain: SupplyChain) {
        viewModelScope.launch {
            try {
                deleteSupplyChain(supplyChain)
                dismissDetailDialog()
                _uiState.update { it.copy(successMessage = "供应链已删除") }
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
