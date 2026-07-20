package com.shanyin.erp.ui.screens.timerules

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TimeRulesUiState(
    val timeRules: List<TimeRule> = emptyList(),
    val systemEvents: List<SystemEvent> = emptyList(),
    val selectedTab: Int = 0, // 0=规则, 1=事件
    val selectedFilter: String = "全部",
    val isLoading: Boolean = true,
    val showCreateRuleDialog: Boolean = false,
    val showDetailDialog: Boolean = false,
    val selectedRule: TimeRule? = null,
    val error: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class TimeRulesViewModel @Inject constructor(
    private val getAllTimeRules: GetAllTimeRulesUseCase,
    private val getAllSystemEvents: GetAllSystemEventsUseCase,
    private val getTimeRulesByType: GetTimeRulesByTypeUseCase,
    private val saveTimeRule: SaveTimeRuleUseCase,
    private val deleteTimeRule: DeleteTimeRuleUseCase,
    private val updateTimeRuleStatus: UpdateTimeRuleStatusUseCase,
    private val recordSystemEvent: RecordSystemEventUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(TimeRulesUiState())
    val uiState: StateFlow<TimeRulesUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        viewModelScope.launch {
            combine(
                getAllTimeRules(),
                getAllSystemEvents()
            ) { rules, events ->
                _uiState.update {
                    it.copy(
                        timeRules = rules,
                        systemEvents = events,
                        isLoading = false
                    )
                }
            }.collect()
        }
    }

    fun setSelectedTab(tab: Int) {
        _uiState.update { it.copy(selectedTab = tab) }
    }

    fun setFilter(filter: String) {
        _uiState.update { it.copy(selectedFilter = filter) }
    }

    fun getFilteredRules(): List<TimeRule> {
        val rules = _uiState.value.timeRules
        return when (_uiState.value.selectedFilter) {
            "生效" -> rules.filter { it.status == RuleStatus.ACTIVE }
            "失效" -> rules.filter { it.status == RuleStatus.INACTIVE }
            "有结果" -> rules.filter { it.status == RuleStatus.HAS_RESULT }
            "预警" -> rules.filter { it.warning != null }
            "逾期" -> rules.filter { it.isOverdue() }
            else -> rules
        }
    }

    fun showCreateRuleDialog() {
        _uiState.update { it.copy(showCreateRuleDialog = true) }
    }

    fun dismissCreateRuleDialog() {
        _uiState.update { it.copy(showCreateRuleDialog = false) }
    }

    fun showDetailDialog(rule: TimeRule) {
        _uiState.update { it.copy(showDetailDialog = true, selectedRule = rule) }
    }

    fun dismissDetailDialog() {
        _uiState.update { it.copy(showDetailDialog = false, selectedRule = null) }
    }

    fun createTimeRule(
        relatedId: Long,
        relatedType: RelatedType,
        triggerEvent: RuleEvent?,
        targetEvent: RuleEvent,
        offsetDays: Int?,
        unit: TimeUnit?,
        direction: Direction?,
        party: Party?,
        tgeParam1: String? = null,
        tgeParam2: String? = null,
        taeParam1: String? = null,
        taeParam2: String? = null,
        inherit: InheritLevel = InheritLevel.SELF
    ) {
        viewModelScope.launch {
            try {
                // 状态根据继承级别自动确定：自身定制→生效，近/远继承→模板
                val autoStatus = if (inherit == InheritLevel.SELF) RuleStatus.ACTIVE else RuleStatus.TEMPLATE
                val rule = TimeRule(
                    relatedId = relatedId,
                    relatedType = relatedType,
                    triggerEvent = triggerEvent,
                    tgeParam1 = tgeParam1,
                    tgeParam2 = tgeParam2,
                    targetEvent = targetEvent,
                    taeParam1 = taeParam1,
                    taeParam2 = taeParam2,
                    offset = offsetDays,
                    unit = unit,
                    direction = direction,
                    party = party,
                    inherit = inherit,
                    status = autoStatus
                )
                saveTimeRule(rule)
                dismissCreateRuleDialog()
                _uiState.update { it.copy(successMessage = "时间规则创建成功") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateRuleStatus(ruleId: Long, status: RuleStatus, result: RuleResult? = null) {
        viewModelScope.launch {
            try {
                updateTimeRuleStatus(ruleId, status, result)
                _uiState.update { it.copy(successMessage = "规则状态已更新") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteRule(rule: TimeRule) {
        viewModelScope.launch {
            try {
                deleteTimeRule(rule)
                dismissDetailDialog()
                _uiState.update { it.copy(successMessage = "规则已删除") }
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun recordEvent(
        eventType: SystemEventType,
        relatedId: Long?,
        relatedType: String?,
        description: String?
    ) {
        viewModelScope.launch {
            try {
                recordSystemEvent(eventType, relatedId, relatedType, description)
                _uiState.update { it.copy(successMessage = "事件已记录") }
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
