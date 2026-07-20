package com.shanyin.erp.ui.screens.business

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.Business
import com.shanyin.erp.domain.model.BusinessDetails
import com.shanyin.erp.domain.model.BusinessStatus
import com.shanyin.erp.domain.model.ChannelCustomer
import com.shanyin.erp.domain.model.RelatedType
import com.shanyin.erp.domain.model.Sku
import com.shanyin.erp.domain.model.TimeRule
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BusinessListUiState(
    val businesses: List<Business> = emptyList(),
    val customers: List<ChannelCustomer> = emptyList(),
    val skus: List<Sku> = emptyList(),
    val isLoading: Boolean = true,
    val showCreateDialog: Boolean = false,
    val showDetailDialog: Boolean = false,
    val selectedBusiness: Business? = null,
    val selectedBusinessTimeRules: List<TimeRule> = emptyList(),
    val error: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class BusinessListViewModel @Inject constructor(
    private val getAllBusinesses: GetAllBusinessesUseCase,
    private val getAllCustomers: GetAllCustomersUseCase,
    private val getAllSkusUseCase: GetAllSkusUseCase,
    private val createBusinessUseCase: CreateBusinessUseCase,
    private val deleteBusiness: DeleteBusinessUseCase,
    private val advanceBusinessStage: AdvanceBusinessStageUseCase,
    private val suspendBusiness: SuspendBusinessUseCase,
    private val terminateBusiness: TerminateBusinessUseCase,
    private val reactivateBusiness: ReactivateBusinessUseCase,
    private val getTimeRulesByRelated: GetTimeRulesByRelatedUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(BusinessListUiState())
    val uiState: StateFlow<BusinessListUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        viewModelScope.launch {
            combine(
                getAllBusinesses(),
                getAllCustomers(),
                getAllSkusUseCase()
            ) { businesses, customers, skus ->
                _uiState.update {
                    it.copy(
                        businesses = businesses,
                        customers = customers,
                        skus = skus,
                        isLoading = false
                    )
                }
            }.collect()
        }
    }

    fun showCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = true) }
    }

    fun dismissCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = false) }
    }

    fun showDetailDialog(business: Business) {
        _uiState.update { it.copy(showDetailDialog = true, selectedBusiness = business, selectedBusinessTimeRules = emptyList()) }
        // Load time rules for this business
        viewModelScope.launch {
            getTimeRulesByRelated(business.id, RelatedType.BUSINESS).collect { rules ->
                _uiState.update { it.copy(selectedBusinessTimeRules = rules) }
            }
        }
    }

    fun dismissDetailDialog() {
        _uiState.update { it.copy(showDetailDialog = false, selectedBusiness = null) }
    }

    fun createBusiness(customerId: Long?, notes: String?) {
        viewModelScope.launch {
            try {
                val business = Business(
                    customerId = customerId,
                    status = BusinessStatus.INITIAL_CONTACT,
                    details = BusinessDetails(notes = notes)
                )
                createBusinessUseCase(business)
                dismissCreateDialog()
                _uiState.update { it.copy(successMessage = "业务创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun advanceStage(businessId: Long, reason: String? = null) {
        viewModelScope.launch {
            advanceBusinessStage(businessId, reason)
                .onSuccess {
                    _uiState.update { state ->
                        state.copy(
                            selectedBusiness = state.businesses.find { it.id == businessId },
                            successMessage = "阶段推进成功"
                        )
                    }
                }
                .onFailure {
                    _uiState.update { it.copy(error = it.error ?: it.error) }
                }
        }
    }

    fun suspend(businessId: Long, reason: String? = null) {
        viewModelScope.launch {
            suspendBusiness(businessId, reason)
                .onSuccess { updatedBusiness ->
                    _uiState.update { state ->
                        state.copy(
                            selectedBusiness = updatedBusiness,
                            successMessage = "业务已暂停"
                        )
                    }
                }
                .onFailure {
                    _uiState.update { it.copy(error = it.error) }
                }
        }
    }

    fun terminate(businessId: Long, reason: String? = null) {
        viewModelScope.launch {
            terminateBusiness(businessId, reason)
                .onSuccess { updatedBusiness ->
                    _uiState.update { state ->
                        state.copy(
                            selectedBusiness = updatedBusiness,
                            successMessage = "业务已终止"
                        )
                    }
                }
                .onFailure {
                    _uiState.update { it.copy(error = it.error) }
                }
        }
    }

    fun reactivate(businessId: Long, reason: String? = null) {
        viewModelScope.launch {
            reactivateBusiness(businessId, reason)
                .onSuccess { updatedBusiness ->
                    _uiState.update { state ->
                        state.copy(
                            selectedBusiness = updatedBusiness,
                            successMessage = "业务已重新激活"
                        )
                    }
                }
                .onFailure {
                    _uiState.update { it.copy(error = it.error) }
                }
        }
    }

    fun delete(business: Business) {
        viewModelScope.launch {
            try {
                deleteBusiness(business)
                _uiState.update { it.copy(successMessage = "业务已删除") }
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
