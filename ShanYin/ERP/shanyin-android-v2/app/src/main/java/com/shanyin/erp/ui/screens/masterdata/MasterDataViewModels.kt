package com.shanyin.erp.ui.screens.masterdata

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.ChannelCustomer
import com.shanyin.erp.domain.model.Point
import com.shanyin.erp.domain.model.PointType
import com.shanyin.erp.domain.model.Supplier
import com.shanyin.erp.domain.model.SupplierCategory
import com.shanyin.erp.domain.model.Sku
import com.shanyin.erp.domain.model.SkuType
import com.shanyin.erp.domain.model.BankAccount
import com.shanyin.erp.domain.model.OwnerType
import com.shanyin.erp.domain.model.BankAccountInfo
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

// ==================== Customer ViewModel ====================

data class CustomerListUiState(
    val customers: List<ChannelCustomer> = emptyList(),
    val isLoading: Boolean = true,
    val showDialog: Boolean = false,
    val editingCustomer: ChannelCustomer? = null,
    val error: String? = null
)

@HiltViewModel
class CustomerListViewModel @Inject constructor(
    private val getAllCustomers: GetAllCustomersUseCase,
    private val saveCustomer: SaveCustomerUseCase,
    private val deleteCustomer: DeleteCustomerUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(CustomerListUiState())
    val uiState: StateFlow<CustomerListUiState> = _uiState.asStateFlow()

    init {
        loadCustomers()
    }

    private fun loadCustomers() {
        viewModelScope.launch {
            getAllCustomers().collect { customers ->
                _uiState.update { it.copy(customers = customers, isLoading = false) }
            }
        }
    }

    fun showAddDialog() {
        _uiState.update { it.copy(showDialog = true, editingCustomer = null) }
    }

    fun showEditDialog(customer: ChannelCustomer) {
        _uiState.update { it.copy(showDialog = true, editingCustomer = customer) }
    }

    fun dismissDialog() {
        _uiState.update { it.copy(showDialog = false, editingCustomer = null) }
    }

    fun save(name: String, info: String?) {
        viewModelScope.launch {
            try {
                val customer = _uiState.value.editingCustomer?.copy(name = name, info = info)
                    ?: ChannelCustomer(name = name, info = info)
                saveCustomer(customer)
                dismissDialog()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(customer: ChannelCustomer) {
        viewModelScope.launch {
            try {
                deleteCustomer(customer)
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}

// ==================== Point ViewModel ====================

data class PointListUiState(
    val points: List<Point> = emptyList(),
    val isLoading: Boolean = true,
    val showDialog: Boolean = false,
    val editingPoint: Point? = null,
    val error: String? = null
)

@HiltViewModel
class PointListViewModel @Inject constructor(
    private val getAllPoints: GetAllPointsUseCase,
    private val savePoint: SavePointUseCase,
    private val deletePoint: DeletePointUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(PointListUiState())
    val uiState: StateFlow<PointListUiState> = _uiState.asStateFlow()

    init {
        loadPoints()
    }

    private fun loadPoints() {
        viewModelScope.launch {
            getAllPoints().collect { points ->
                _uiState.update { it.copy(points = points, isLoading = false) }
            }
        }
    }

    fun showAddDialog() {
        _uiState.update { it.copy(showDialog = true, editingPoint = null) }
    }

    fun showEditDialog(point: Point) {
        _uiState.update { it.copy(showDialog = true, editingPoint = point) }
    }

    fun dismissDialog() {
        _uiState.update { it.copy(showDialog = false, editingPoint = null) }
    }

    fun save(name: String, address: String?, type: PointType?, receivingAddress: String?) {
        viewModelScope.launch {
            try {
                val point = _uiState.value.editingPoint?.copy(
                    name = name, address = address, type = type, receivingAddress = receivingAddress
                ) ?: Point(name = name, address = address, type = type, receivingAddress = receivingAddress)
                savePoint(point)
                dismissDialog()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(point: Point) {
        viewModelScope.launch {
            try {
                deletePoint(point)
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }
}

// ==================== Supplier ViewModel ====================

data class SupplierListUiState(
    val suppliers: List<Supplier> = emptyList(),
    val isLoading: Boolean = true,
    val showDialog: Boolean = false,
    val editingSupplier: Supplier? = null,
    val error: String? = null
)

@HiltViewModel
class SupplierListViewModel @Inject constructor(
    private val getAllSuppliers: GetAllSuppliersUseCase,
    private val saveSupplier: SaveSupplierUseCase,
    private val deleteSupplier: DeleteSupplierUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(SupplierListUiState())
    val uiState: StateFlow<SupplierListUiState> = _uiState.asStateFlow()

    init {
        loadSuppliers()
    }

    private fun loadSuppliers() {
        viewModelScope.launch {
            getAllSuppliers().collect { suppliers ->
                _uiState.update { it.copy(suppliers = suppliers, isLoading = false) }
            }
        }
    }

    fun showAddDialog() {
        _uiState.update { it.copy(showDialog = true, editingSupplier = null) }
    }

    fun showEditDialog(supplier: Supplier) {
        _uiState.update { it.copy(showDialog = true, editingSupplier = supplier) }
    }

    fun dismissDialog() {
        _uiState.update { it.copy(showDialog = false, editingSupplier = null) }
    }

    fun save(name: String, category: SupplierCategory?, address: String?, qualifications: String?) {
        viewModelScope.launch {
            try {
                val supplier = _uiState.value.editingSupplier?.copy(
                    name = name, category = category, address = address, qualifications = qualifications
                ) ?: Supplier(name = name, category = category, address = address, qualifications = qualifications)
                saveSupplier(supplier)
                dismissDialog()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(supplier: Supplier) {
        viewModelScope.launch {
            try {
                deleteSupplier(supplier)
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }
}

// ==================== SKU ViewModel ====================

data class SkuListUiState(
    val skus: List<Sku> = emptyList(),
    val isLoading: Boolean = true,
    val showDialog: Boolean = false,
    val editingSku: Sku? = null,
    val error: String? = null
)

@HiltViewModel
class SkuListViewModel @Inject constructor(
    private val getAllSkus: GetAllSkusUseCase,
    private val saveSku: SaveSkuUseCase,
    private val deleteSku: DeleteSkuUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(SkuListUiState())
    val uiState: StateFlow<SkuListUiState> = _uiState.asStateFlow()

    init {
        loadSkus()
    }

    private fun loadSkus() {
        viewModelScope.launch {
            getAllSkus().collect { skus ->
                _uiState.update { it.copy(skus = skus, isLoading = false) }
            }
        }
    }

    fun showAddDialog() {
        _uiState.update { it.copy(showDialog = true, editingSku = null) }
    }

    fun showEditDialog(sku: Sku) {
        _uiState.update { it.copy(showDialog = true, editingSku = sku) }
    }

    fun dismissDialog() {
        _uiState.update { it.copy(showDialog = false, editingSku = null) }
    }

    fun save(name: String, typeLevel1: SkuType?, typeLevel2: String?, model: String?, description: String?) {
        viewModelScope.launch {
            try {
                val sku = _uiState.value.editingSku?.copy(
                    name = name, typeLevel1 = typeLevel1, typeLevel2 = typeLevel2, model = model, description = description
                ) ?: Sku(name = name, typeLevel1 = typeLevel1, typeLevel2 = typeLevel2, model = model, description = description)
                saveSku(sku)
                dismissDialog()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(sku: Sku) {
        viewModelScope.launch {
            try {
                deleteSku(sku)
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }
}

// ==================== BankAccount ViewModel ====================

data class BankAccountListUiState(
    val bankAccounts: List<BankAccount> = emptyList(),
    val isLoading: Boolean = true,
    val showDialog: Boolean = false,
    val editingAccount: BankAccount? = null,
    val error: String? = null
)

@HiltViewModel
class BankAccountListViewModel @Inject constructor(
    private val getAllBankAccounts: GetAllBankAccountsUseCase,
    private val saveBankAccount: SaveBankAccountUseCase,
    private val deleteBankAccount: DeleteBankAccountUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(BankAccountListUiState())
    val uiState: StateFlow<BankAccountListUiState> = _uiState.asStateFlow()

    init {
        loadBankAccounts()
    }

    private fun loadBankAccounts() {
        viewModelScope.launch {
            getAllBankAccounts().collect { accounts ->
                _uiState.update { it.copy(bankAccounts = accounts, isLoading = false) }
            }
        }
    }

    fun showAddDialog() {
        _uiState.update { it.copy(showDialog = true, editingAccount = null) }
    }

    fun showEditDialog(account: BankAccount) {
        _uiState.update { it.copy(showDialog = true, editingAccount = account) }
    }

    fun dismissDialog() {
        _uiState.update { it.copy(showDialog = false, editingAccount = null) }
    }

    fun save(ownerType: OwnerType, bankName: String, accountName: String, accountNumber: String, isDefault: Boolean) {
        viewModelScope.launch {
            try {
                val info = BankAccountInfo(bankName = bankName, accountName = accountName, accountNumber = accountNumber)
                val account = _uiState.value.editingAccount?.copy(
                    ownerType = ownerType, accountInfo = info, isDefault = isDefault
                ) ?: BankAccount(ownerType = ownerType, accountInfo = info, isDefault = isDefault)
                saveBankAccount(account)
                dismissDialog()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(account: BankAccount) {
        viewModelScope.launch {
            try {
                deleteBankAccount(account)
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }
}
