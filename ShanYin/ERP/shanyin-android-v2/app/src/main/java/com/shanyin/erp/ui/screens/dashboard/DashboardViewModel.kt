package com.shanyin.erp.ui.screens.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.util.Calendar
import javax.inject.Inject

data class DashboardUiState(
    val isLoading: Boolean = true,
    // KPI counts
    val customerCount: Int = 0,
    val supplierCount: Int = 0,
    val skuCount: Int = 0,
    val businessCount: Int = 0,
    val vcCount: Int = 0,
    val vcExecutingCount: Int = 0,
    val vcCompletedCount: Int = 0,
    val supplyChainCount: Int = 0,
    val logisticsCount: Int = 0,
    val logisticsPendingCount: Int = 0,
    val equipmentInventoryCount: Int = 0,
    val materialInventoryCount: Int = 0,
    val timeRuleCount: Int = 0,
    val warningRuleCount: Int = 0,
    // Additional counts (placeholders for now)
    val pointCount: Int = 0,
    val externalPartnerCount: Int = 0,
    val cashFlowCount: Int = 0,
    // Financial
    val bankAccounts: List<BankAccount> = emptyList(),
    val totalBankBalance: Double = 0.0,
    val recentCashFlows: List<CashFlow> = emptyList(),
    // Monthly report
    val currentYear: Int = Calendar.getInstance().get(Calendar.YEAR),
    val currentMonth: Int = Calendar.getInstance().get(Calendar.MONTH) + 1,
    val monthlyRevenue: Double = 0.0,
    val monthlyExpense: Double = 0.0,
    val monthlyProfit: Double = 0.0,
    // Recent activities
    val recentEvents: List<SystemEvent> = emptyList(),
    // Error
    val error: String? = null
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val getAllCustomers: GetAllCustomersUseCase,
    private val getAllSuppliers: GetAllSuppliersUseCase,
    private val getAllSkus: GetAllSkusUseCase,
    private val getAllBusinesses: GetAllBusinessesUseCase,
    private val getAllVirtualContracts: GetAllVirtualContractsUseCase,
    private val getAllSupplyChains: GetAllSupplyChainsUseCase,
    private val getAllLogistics: GetAllLogisticsUseCase,
    private val getAllEquipmentInventory: GetAllEquipmentInventoryUseCase,
    private val getAllMaterialInventory: GetAllMaterialInventoryUseCase,
    private val getAllTimeRules: GetAllTimeRulesUseCase,
    private val getAllCashFlows: GetAllCashFlowsUseCase,
    private val getAllSystemEvents: GetAllSystemEventsUseCase,
    private val getAllBankAccounts: GetAllBankAccountsUseCase,
    private val getMonthlySummary: GetMonthlySummaryUseCase,
    private val getAllPoints: GetAllPointsUseCase,
    private val getAllPartners: GetAllPartnersUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        loadDashboardData()
    }

    private fun loadDashboardData() {
        viewModelScope.launch {
            // First batch: master data and VC
            val masterVcFlow = combine(
                getAllCustomers(),
                getAllSuppliers(),
                getAllSkus(),
                getAllBusinesses(),
                getAllVirtualContracts()
            ) { customers, suppliers, skus, businesses, vcs ->
                MasterVcData(customers.size, suppliers.size, skus.size, businesses.size, vcs)
            }

            // Second batch: supply chain, logistics, inventory
            val supplyLogisticsInvFlow = combine(
                getAllSupplyChains(),
                getAllLogistics(),
                getAllEquipmentInventory(),
                getAllMaterialInventory(),
                getAllTimeRules()
            ) { supplyChains, logistics, equipmentInv, materialInv, timeRules ->
                SupplyLogisticsInvData(
                    supplyChains.size,
                    logistics.size,
                    logistics.count { it.status == LogisticsStatus.PENDING },
                    equipmentInv.size,
                    materialInv.size,
                    timeRules.size,
                    timeRules.count { it.calculateWarning() != null && it.calculateWarning() != WarningLevel.GREEN }
                )
            }

            // Third batch: finance and events
            val financeEventFlow = combine(
                getAllCashFlows(),
                getAllSystemEvents(),
                getAllBankAccounts()
            ) { cashFlows, events, bankAccounts ->
                val calendar = Calendar.getInstance()
                val year = calendar.get(Calendar.YEAR)
                val month = calendar.get(Calendar.MONTH) + 1
                val startOfMonth = getStartOfMonth(year, month)
                val endOfMonth = getEndOfMonth(year, month)

                val monthCashFlows = cashFlows.filter {
                    (it.transactionDate ?: 0) in startOfMonth..endOfMonth
                }

                val monthlyRevenue = monthCashFlows.sumOf { it.amount }
                val totalBalance = cashFlows.sumOf { it.amount }

                FinanceEventData(
                    cashFlows = cashFlows,
                    events = events,
                    bankAccounts = bankAccounts,
                    monthlyRevenue = monthlyRevenue,
                    totalBalance = totalBalance,
                    cashFlowCount = cashFlows.size
                )
            }

            // Fourth batch: points and external partners
            val masterExtraFlow = combine(
                getAllPoints(),
                getAllPartners()
            ) { points, partners ->
                MasterExtraData(points.size, partners.size)
            }

            // Final combine
            combine(masterVcFlow, supplyLogisticsInvFlow, financeEventFlow, masterExtraFlow) { masterVc, supplyLogistics, financeEvent, masterExtra ->
                val executingVcs = masterVc.vcs.filter { it.status == VCStatus.EXECUTING }
                val completedVcs = masterVc.vcs.filter { it.status == VCStatus.COMPLETED }

                _uiState.update {
                    it.copy(
                        isLoading = false,
                        customerCount = masterVc.customerCount,
                        supplierCount = masterVc.supplierCount,
                        skuCount = masterVc.skuCount,
                        businessCount = masterVc.businessCount,
                        vcCount = masterVc.vcs.size,
                        vcExecutingCount = executingVcs.size,
                        vcCompletedCount = completedVcs.size,
                        supplyChainCount = supplyLogistics.supplyChainCount,
                        logisticsCount = supplyLogistics.logisticsCount,
                        logisticsPendingCount = supplyLogistics.logisticsPendingCount,
                        equipmentInventoryCount = supplyLogistics.equipmentInventoryCount,
                        materialInventoryCount = supplyLogistics.materialInventoryCount,
                        timeRuleCount = supplyLogistics.timeRuleCount,
                        warningRuleCount = supplyLogistics.warningRuleCount,
                        pointCount = masterExtra.pointCount,
                        externalPartnerCount = masterExtra.externalPartnerCount,
                        cashFlowCount = financeEvent.cashFlowCount,
                        bankAccounts = financeEvent.bankAccounts,
                        totalBankBalance = financeEvent.totalBalance,
                        recentCashFlows = financeEvent.cashFlows.take(5),
                        recentEvents = financeEvent.events.take(10),
                        monthlyRevenue = financeEvent.monthlyRevenue,
                        monthlyExpense = 0.0,
                        monthlyProfit = financeEvent.monthlyRevenue
                    )
                }
            }.collect()
        }
    }

    private data class MasterVcData(
        val customerCount: Int,
        val supplierCount: Int,
        val skuCount: Int,
        val businessCount: Int,
        val vcs: List<VirtualContract>
    )

    private data class SupplyLogisticsInvData(
        val supplyChainCount: Int,
        val logisticsCount: Int,
        val logisticsPendingCount: Int,
        val equipmentInventoryCount: Int,
        val materialInventoryCount: Int,
        val timeRuleCount: Int,
        val warningRuleCount: Int
    )

    private data class FinanceEventData(
        val cashFlows: List<CashFlow>,
        val events: List<SystemEvent>,
        val bankAccounts: List<BankAccount>,
        val monthlyRevenue: Double,
        val totalBalance: Double,
        val cashFlowCount: Int
    )

    private data class MasterExtraData(
        val pointCount: Int,
        val externalPartnerCount: Int
    )

    fun loadMonthlyReport(year: Int, month: Int) {
        viewModelScope.launch {
            try {
                val report = getMonthlySummary(year, month)
                _uiState.update {
                    it.copy(
                        currentYear = year,
                        currentMonth = month,
                        monthlyRevenue = report.totalRevenue,
                        monthlyExpense = report.totalExpense,
                        monthlyProfit = report.netProfit
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    private fun getStartOfMonth(year: Int, month: Int): Long {
        val calendar = Calendar.getInstance()
        calendar.set(year, month - 1, 1, 0, 0, 0)
        calendar.set(Calendar.MILLISECOND, 0)
        return calendar.timeInMillis
    }

    private fun getEndOfMonth(year: Int, month: Int): Long {
        val calendar = Calendar.getInstance()
        calendar.set(year, month - 1, 1, 23, 59, 59)
        calendar.set(Calendar.MILLISECOND, 999)
        calendar.set(Calendar.DAY_OF_MONTH, calendar.getActualMaximum(Calendar.DAY_OF_MONTH))
        return calendar.timeInMillis
    }
}
