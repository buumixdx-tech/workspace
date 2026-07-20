package com.shanyin.erp.ui.screens.finance

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*
import com.shanyin.erp.domain.usecase.finance.ApArDetailItem
import com.shanyin.erp.domain.usecase.finance.ExternalFundUseCase
import com.shanyin.erp.domain.usecase.finance.GetAccountPayableDetailUseCase
import com.shanyin.erp.domain.usecase.finance.GetAccountReceivableDetailUseCase
import com.shanyin.erp.domain.usecase.finance.GetApBalanceUseCase
import com.shanyin.erp.domain.usecase.finance.GetArBalanceUseCase
import com.shanyin.erp.domain.usecase.GetVcPaymentProgressUseCase
import com.shanyin.erp.domain.usecase.GetSuggestedCashflowPartiesUseCase
import com.shanyin.erp.domain.usecase.GetAvailableCashFlowTypesUseCase
import com.shanyin.erp.domain.usecase.VcPaymentProgress
import com.shanyin.erp.domain.usecase.SuggestedParties
import com.shanyin.erp.domain.usecase.finance.InternalTransferUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FinanceUiState(
    val cashFlows: List<CashFlow> = emptyList(),
    val journalEntries: List<FinancialJournalEntry> = emptyList(),
    val financeAccounts: List<FinanceAccount> = emptyList(),
    val bankAccounts: List<BankAccount> = emptyList(),
    val virtualContracts: List<VirtualContract> = emptyList(),
    val customers: List<ChannelCustomer> = emptyList(),
    val suppliers: List<Supplier> = emptyList(),
    val selectedTab: Int = 0, // 0=资金流水, 1=凭证管理, 2=账户, 3=应付账款, 4=应收账款
    val filterType: CashFlowType? = null,
    val filterAccountId: Long? = null,
    val isLoading: Boolean = true,
    val showCreateCashFlowDialog: Boolean = false,
    val showCreateVoucherDialog: Boolean = false,
    val showAccountDialog: Boolean = false,
    val showInternalTransferDialog: Boolean = false,
    val showExternalFundDialog: Boolean = false,
    val selectedJournalEntries: List<FinancialJournalEntry> = emptyList(),
    // AP/AR data
    val apDetails: List<ApArDetailItem> = emptyList(),
    val arDetails: List<ApArDetailItem> = emptyList(),
    val apBalance: Double = 0.0,
    val arBalance: Double = 0.0,
    val error: String? = null,
    val successMessage: String? = null
)

/**
 * 带方向信息的 CashFlow（enriched for UI display）
 */
data class CashFlowWithDirection(
    val cashFlow: CashFlow,
    val isIncome: Boolean,   // true=流入（我们收款）, false=流出（我们付款）
    val vcTypeName: String?, // VC 类型名称（便于显示）
    val vcReturnDirection: ReturnDirection?, // RETURN VC 的退款方向
    val payerDisplayName: String?, // 付款方显示名称：开户名称+银行信息
    val payeeDisplayName: String?  // 收款方显示名称：开户名称+银行信息
)

@HiltViewModel
class FinanceViewModel @Inject constructor(
    private val getAllCashFlows: GetAllCashFlowsUseCase,
    private val getAllJournalEntries: GetAllJournalEntriesUseCase,
    private val getAllFinanceAccounts: GetAllFinanceAccountsUseCase,
    private val getAllVirtualContracts: GetAllVirtualContractsUseCase,
    private val getAllBankAccounts: GetAllBankAccountsUseCase,
    private val getAllCustomers: GetAllCustomersUseCase,
    private val getAllSuppliers: GetAllSuppliersUseCase,
    private val createCashFlow: CreateCashFlowUseCase,
    private val updateCashFlow: UpdateCashFlowUseCase,
    private val deleteCashFlow: DeleteCashFlowUseCase,
    private val triggerCashFlowFinance: TriggerCashFlowFinanceUseCase,
    private val createDoubleEntryVoucher: CreateDoubleEntryVoucherUseCase,
    private val internalTransfer: InternalTransferUseCase,
    private val externalFund: ExternalFundUseCase,
    private val saveFinanceAccount: SaveFinanceAccountUseCase,
    private val deleteFinanceAccount: DeleteFinanceAccountUseCase,
    private val getMonthlySummary: GetMonthlySummaryUseCase,
    private val getAccountBalance: GetAccountBalanceUseCase,
    private val getApDetail: GetAccountPayableDetailUseCase,
    private val getArDetail: GetAccountReceivableDetailUseCase,
    private val getApBalance: GetApBalanceUseCase,
    private val getArBalance: GetArBalanceUseCase,
    private val getVcPaymentProgress: GetVcPaymentProgressUseCase,
    private val getSuggestedParties: GetSuggestedCashflowPartiesUseCase,
    private val getAvailableCfTypes: GetAvailableCashFlowTypesUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(FinanceUiState())
    val uiState: StateFlow<FinanceUiState> = _uiState.asStateFlow()

    private val _accountBalances = MutableStateFlow<Map<Long, Double>>(emptyMap())
    val accountBalances: StateFlow<Map<Long, Double>> = _accountBalances.asStateFlow()

    private val _currentMonthlyReport = MutableStateFlow<MonthlyReport?>(null)
    val currentMonthlyReport: StateFlow<MonthlyReport?> = _currentMonthlyReport.asStateFlow()

    // Dialog state for CreateCashFlow
    private val _dialogVcProgress = MutableStateFlow<Map<Long, VcPaymentProgress>>(emptyMap())
    val dialogVcProgress: StateFlow<Map<Long, VcPaymentProgress>> = _dialogVcProgress.asStateFlow()

    private val _dialogSuggestedParties = MutableStateFlow<Map<Long, SuggestedParties>>(emptyMap())
    val dialogSuggestedParties: StateFlow<Map<Long, SuggestedParties>> = _dialogSuggestedParties.asStateFlow()

    private val _dialogAvailableCfTypes = MutableStateFlow<Map<Long, List<CashFlowType>>>(emptyMap())
    val dialogAvailableCfTypes: StateFlow<Map<Long, List<CashFlowType>>> = _dialogAvailableCfTypes.asStateFlow()

    // 预加载的银行账户缓存（用于在 getFilteredCashFlows 中补全账户名）
    private var cachedBankAccounts: List<BankAccount> = emptyList()

    init {
        loadData()
    }

    private fun loadData() {
        viewModelScope.launch {
            // 预加载所有银行账户（同步等待，确保 combine 前就有数据）
            val allBankAccounts = try {
                getAllBankAccounts().first()
            } catch (e: Exception) {
                emptyList()
            }
            cachedBankAccounts = allBankAccounts
            // 加载客户和供应商（用于显示账户所属主体）
            val allCustomers = try { getAllCustomers().first() } catch (e: Exception) { emptyList() }
            val allSuppliers = try { getAllSuppliers().first() } catch (e: Exception) { emptyList() }
            val customerMap = allCustomers.associateBy { it.id }
            val supplierMap = allSuppliers.associateBy { it.id }
            Log.d("FinanceDebug", "loadData: allBankAccounts.size=${allBankAccounts.size}")
            allBankAccounts.forEachIndexed { index, ba ->
                Log.d("FinanceDebug", "loadData: bankAccount[$index] id=${ba.id}, accountInfo=${ba.accountInfo}")
            }
            val bankMap = allBankAccounts.associateBy { it.id }

            combine(
                getAllCashFlows(),
                getAllJournalEntries(),
                getAllFinanceAccounts(),
                getAllVirtualContracts()
            ) { cashFlows, journals, accounts, vcs ->
                Log.d("FinanceDebug", "loadData combine: cashFlows.size=${cashFlows.size}")
                // 用预加载的 bankMap 补全 cashFlow 的账户名
                val cashFlowsWithNames = cashFlows.map { cf ->
                    Log.d("FinanceDebug", "loadData: processing cf id=${cf.id}, payerAccountId=${cf.payerAccountId}, payerAccountName(entity)='${cf.payerAccountName}'")
                    val payerName = cf.payerAccountName
                        ?: cf.payerAccountId?.let { id -> bankMap[id]?.accountInfo }
                            ?.let { "${it.bankName ?: ""} ${it.accountNumber ?: ""}".trim().ifEmpty { null } }
                    val payeeName = cf.payeeAccountName
                        ?: cf.payeeAccountId?.let { id -> bankMap[id]?.accountInfo }
                            ?.let { "${it.bankName ?: ""} ${it.accountNumber ?: ""}".trim().ifEmpty { null } }
                    if (payerName != cf.payerAccountName || payeeName != cf.payeeAccountName) {
                        cf.copy(payerAccountName = payerName, payeeAccountName = payeeName)
                    } else cf
                }
                _uiState.update {
                    it.copy(
                        cashFlows = cashFlowsWithNames,
                        journalEntries = journals,
                        financeAccounts = accounts,
                        virtualContracts = vcs,
                        bankAccounts = allBankAccounts,
                        customers = allCustomers,
                        suppliers = allSuppliers,
                        isLoading = false
                    )
                }
                // Load account balances
                loadAccountBalances(accounts)
                // Load AP/AR data
                loadApArData()
            }.collect()
        }
    }

    private suspend fun loadApArData() {
        val apItems = getApDetail()
        val arItems = getArDetail()
        val apBal = getApBalance()
        val arBal = getArBalance()
        _uiState.update {
            it.copy(
                apDetails = apItems,
                arDetails = arItems,
                apBalance = apBal,
                arBalance = arBal
            )
        }
    }

    private suspend fun loadAccountBalances(accounts: List<FinanceAccount>) {
        val balances = mutableMapOf<Long, Double>()
        accounts.forEach { account ->
            if (account.id != 0L) {
                balances[account.id] = getAccountBalance(account.id)
            }
        }
        _accountBalances.value = balances
    }

    fun setSelectedTab(tab: Int) {
        _uiState.update { it.copy(selectedTab = tab) }
    }

    fun setFilterType(type: CashFlowType?) {
        _uiState.update { it.copy(filterType = type) }
    }

    fun setFilterAccount(accountId: Long?) {
        _uiState.update { it.copy(filterAccountId = accountId) }
    }

    /**
     * 加载 VC 的对话框相关数据（进度、建议账户、可用资金类型）
     * 在 CreateCashFlowDialog 选择 VC 后调用
     */
    fun loadVcDialogData(vcId: Long) {
        viewModelScope.launch {
            try {
                val progress = getVcPaymentProgress(vcId)
                if (progress != null) {
                    _dialogVcProgress.update { it + (vcId to progress) }
                }
                // 加载所有资金类型的建议（实际建议会因类型而异）
                _dialogSuggestedParties.update { it + (vcId to getSuggestedParties(vcId, CashFlowType.PREPAYMENT)) }
                // 预加载可用类型
                val availableTypes = getAvailableCfTypes(vcId)
                _dialogAvailableCfTypes.update { it + (vcId to availableTypes) }
            } catch (e: Exception) {
                // 忽略，加载失败不影响主流程
            }
        }
    }

    /**
     * 获取 VC 的付款进度（用于 CreateCashFlowDialog 展示）
     */
    fun getVcProgress(vcId: Long): VcPaymentProgress? {
        return _dialogVcProgress.value[vcId]
    }

    /**
     * 获取 VC 的建议付款方/收款方（用于 CreateCashFlowDialog 自动填充）
     */
    fun getSuggestedPartiesForVc(vcId: Long, cfType: CashFlowType): SuggestedParties {
        return _dialogSuggestedParties.value[vcId] ?: run {
            // 如果没有缓存，直接计算
            viewModelScope.launch {
                try {
                    val parties = getSuggestedParties(vcId, cfType)
                    _dialogSuggestedParties.update { it + (vcId to parties) }
                } catch (e: Exception) { /* ignore */ }
            }
            SuggestedParties(null, null, null, null)
        }
    }

    /**
     * 获取 VC 可用的资金流类型（用于 CreateCashFlowDialog 过滤）
     */
    fun getAvailableTypesForVc(vcId: Long): List<CashFlowType> {
        return _dialogAvailableCfTypes.value[vcId] ?: CashFlowType.entries.toList()
    }

    fun getFilteredCashFlows(): List<CashFlowWithDirection> {
        val state = _uiState.value
        val vcMap = state.virtualContracts.associateBy { it.id }
        val bankMap = state.bankAccounts.associateBy { it.id }
        val customerMap = state.customers.associateBy { it.id }
        val supplierMap = state.suppliers.associateBy { it.id }
        var filtered = state.cashFlows

        state.filterType?.let { type ->
            filtered = filtered.filter { it.type == type }
        }

        state.filterAccountId?.let { accountId ->
            filtered = filtered.filter {
                it.payerAccountId == accountId || it.payeeAccountId == accountId
            }
        }

        return filtered.map { cf ->
            // 兜底：用已加载的 bankAccounts 列表补全账户名（toDomain 查询可能失败）
            val payerName = cf.payerAccountName
                ?: cf.payerAccountId?.let { id -> bankMap[id]?.accountInfo }
                    ?.let { "${it.bankName ?: ""} ${it.accountNumber ?: ""}".trim().ifEmpty { null } }
            val payeeName = cf.payeeAccountName
                ?: cf.payeeAccountId?.let { id -> bankMap[id]?.accountInfo }
                    ?.let { "${it.bankName ?: ""} ${it.accountNumber ?: ""}".trim().ifEmpty { null } }

            val cfEnriched = if (payerName != cf.payerAccountName || payeeName != cf.payeeAccountName) {
                cf.copy(payerAccountName = payerName, payeeAccountName = payeeName)
            } else cf

            // 构建账户显示名称：只显示 [主体名称] [账号后四位]
            fun buildAccountDisplayName(bankAccount: BankAccount?): String? {
                if (bankAccount == null) return null
                val info = bankAccount.accountInfo
                val accountNo = info?.resolvedAccountNumber?.trim() ?: ""
                // 获取主体名称
                val ownerName = when (bankAccount.ownerType) {
                    OwnerType.OURSELVES -> "我方"
                    OwnerType.CUSTOMER -> bankAccount.ownerId?.let { customerMap[it]?.name?.trim() } ?: "客户"
                    OwnerType.SUPPLIER -> bankAccount.ownerId?.let { supplierMap[it]?.name?.trim() } ?: "供应商"
                    OwnerType.PARTNER -> "合作伙伴"
                    null -> null
                }
                val parts = mutableListOf<String>()
                if (!ownerName.isNullOrBlank()) parts.add(ownerName)
                if (accountNo.isNotEmpty()) parts.add("[${accountNo.takeLast(4)}]")
                return parts.joinToString(" ").ifEmpty { null }
            }
            val payerDisplayName = cf.payerAccountId?.let { buildAccountDisplayName(bankMap[it]) }
            val payeeDisplayName = cf.payeeAccountId?.let { buildAccountDisplayName(bankMap[it]) }

            val vc = cf.virtualContractId?.let { vcMap[it] }
            CashFlowWithDirection(
                cashFlow = cfEnriched,
                isIncome = determineIsIncome(cf, vc),
                vcTypeName = vc?.type?.displayName,
                vcReturnDirection = vc?.returnDirection,
                payerDisplayName = payerDisplayName,
                payeeDisplayName = payeeDisplayName
            )
        }
    }

    /**
     * 根据 VC 类型和 return_direction 计算 isIncome（资金流入还是流出）
     * 对应 Desktop process_cash_flow_finance 的 isIncome 判断逻辑
     */
    private fun determineIsIncome(cashFlow: CashFlow, vc: VirtualContract?): Boolean {
        if (vc == null) {
            // 无 VC 上下文的 cashFlow，尝试从类型推断（不准确，仅作降级）
            return when (cashFlow.type) {
                CashFlowType.DEPOSIT_REFUND,
                CashFlowType.REFUND,
                CashFlowType.OFFSET_INFLOW -> true
                else -> false
            }
        }
        return when {
            vc.type == VCType.MATERIAL_SUPPLY -> true  // 客户付款给我们
            vc.type == VCType.RETURN -> {
                // RETURN VC：由 return_direction 决定
                vc.returnDirection == ReturnDirection.US_TO_SUPPLIER
            }
            vc.type in listOf(
                VCType.EQUIPMENT_PROCUREMENT,
                VCType.EQUIPMENT_STOCK,
                VCType.MATERIAL_PROCUREMENT
            ) -> false // 我们付款给供应商
            else -> false
        }
    }

    fun getVouchers(): Map<String, List<FinancialJournalEntry>> {
        return _uiState.value.journalEntries
            .filter { it.voucherNo != null }
            .groupBy { it.voucherNo!! }
    }

    fun showCreateCashFlowDialog() {
        _uiState.update { it.copy(showCreateCashFlowDialog = true) }
    }

    fun dismissCreateCashFlowDialog() {
        _uiState.update { it.copy(showCreateCashFlowDialog = false) }
    }

    fun showCreateVoucherDialog() {
        _uiState.update { it.copy(showCreateVoucherDialog = true) }
    }

    fun dismissCreateVoucherDialog() {
        _uiState.update { it.copy(showCreateVoucherDialog = false, selectedJournalEntries = emptyList()) }
    }

    fun showInternalTransferDialog() {
        _uiState.update { it.copy(showInternalTransferDialog = true) }
    }

    fun dismissInternalTransferDialog() {
        _uiState.update { it.copy(showInternalTransferDialog = false) }
    }

    fun showExternalFundDialog() {
        _uiState.update { it.copy(showExternalFundDialog = true) }
    }

    fun dismissExternalFundDialog() {
        _uiState.update { it.copy(showExternalFundDialog = false) }
    }

    fun performExternalFund(
        accountId: Long,
        fundType: String,
        amount: Double,
        externalEntity: String,
        description: String?,
        isInbound: Boolean
    ) {
        viewModelScope.launch {
            try {
                val request = ExternalFundUseCase.ExternalFundRequest(
                    accountId = accountId,
                    fundType = fundType,
                    amount = amount,
                    externalEntity = externalEntity,
                    description = description,
                    isInbound = isInbound
                )
                val voucherNo = externalFund(request)
                dismissExternalFundDialog()
                _uiState.update { it.copy(successMessage = "外部出入金成功 凭证号: $voucherNo") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun performInternalTransfer(
        fromBankAccountId: Long,
        toBankAccountId: Long,
        amount: Double,
        description: String?
    ) {
        viewModelScope.launch {
            try {
                val request = InternalTransferUseCase.TransferRequest(
                    fromBankAccountId = fromBankAccountId,
                    toBankAccountId = toBankAccountId,
                    amount = amount,
                    description = description
                )
                val voucherNo = internalTransfer(request)
                dismissInternalTransferDialog()
                _uiState.update { it.copy(successMessage = "划拨成功 凭证号: $voucherNo") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun showAccountDialog() {
        _uiState.update { it.copy(showAccountDialog = true) }
    }

    fun dismissAccountDialog() {
        _uiState.update { it.copy(showAccountDialog = false) }
    }

    fun createCashFlow(
        virtualContractId: Long?,
        type: CashFlowType,
        amount: Double,
        payerAccountId: Long?,
        payeeAccountId: Long?,
        description: String?,
        transactionDate: Long?
    ) {
        viewModelScope.launch {
            try {
                val bankAccounts = _uiState.value.bankAccounts
                Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: bankAccounts.size=${bankAccounts.size}, payerAccountId=$payerAccountId, payeeAccountId=$payeeAccountId")
                val payerAccount = payerAccountId?.let { id -> bankAccounts.find { it.id == id } }
                val payeeAccount = payeeAccountId?.let { id -> bankAccounts.find { it.id == id } }
                Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: payerAccount=$payerAccount, payeeAccount=$payeeAccount")
                Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: payerAccount.accountInfo=${payerAccount?.accountInfo}, payeeAccount.accountInfo=${payeeAccount?.accountInfo}")
                val payerName = payerAccountId?.let { id ->
                    bankAccounts.find { it.id == id }?.accountInfo
                        ?.let { info ->
                            Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: extracting from accountInfo=$info")
                            "${info.bankName ?: ""} ${info.accountNumber ?: ""}".trim().ifEmpty { null }
                        }
                }
                Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: extracted payerName='$payerName'")
                val payeeName = payeeAccountId?.let { id ->
                    bankAccounts.find { it.id == id }?.accountInfo
                        ?.let { info ->
                            Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: extracting payee from accountInfo=$info")
                            "${info.bankName ?: ""} ${info.accountNumber ?: ""}".trim().ifEmpty { null }
                        }
                }
                Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: extracted payeeName='$payeeName'")
                val cashFlow = CashFlow(
                    virtualContractId = virtualContractId,
                    type = type,
                    amount = amount,
                    payerAccountId = payerAccountId,
                    payerAccountName = payerName,
                    payeeAccountId = payeeAccountId,
                    payeeAccountName = payeeName,
                    description = description,
                    transactionDate = transactionDate ?: System.currentTimeMillis()
                )
                Log.d("FinanceDebug", "FinanceViewModel.createCashFlow: creating cashFlow with payerName='$payerName', payeeName='$payeeName'")
                createCashFlow(cashFlow)
                dismissCreateCashFlowDialog()
                _uiState.update { it.copy(successMessage = "资金流水创建成功") }
            } catch (e: Exception) {
                Log.e("FinanceDebug", "FinanceViewModel.createCashFlow: exception=${e.message}", e)
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateCashFlowFinanceTriggered(cashFlowId: Long) {
        viewModelScope.launch {
            try {
                triggerCashFlowFinance(cashFlowId)
                _uiState.update { it.copy(successMessage = "已触发财务确认") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteCashFlow(cashFlow: CashFlow) {
        viewModelScope.launch {
            try {
                deleteCashFlow(cashFlow)
                _uiState.update { it.copy(successMessage = "资金流水已删除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun createVoucher(entries: List<FinancialJournalEntry>) {
        viewModelScope.launch {
            try {
                val voucherNo = createDoubleEntryVoucher(entries)
                dismissCreateVoucherDialog()
                _uiState.update { it.copy(successMessage = "凭证 $voucherNo 创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun saveFinanceAccount(account: FinanceAccount) {
        viewModelScope.launch {
            try {
                saveFinanceAccount(account)
                dismissAccountDialog()
                _uiState.update { it.copy(successMessage = "财务账户保存成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteFinanceAccount(account: FinanceAccount) {
        viewModelScope.launch {
            try {
                deleteFinanceAccount(account)
                _uiState.update { it.copy(successMessage = "财务账户已删除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun loadMonthlyReport(year: Int, month: Int) {
        viewModelScope.launch {
            try {
                val report = getMonthlySummary(year, month)
                _currentMonthlyReport.value = report
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
