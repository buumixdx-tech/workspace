package com.shanyin.erp.ui.screens.timerules

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.shanyin.erp.domain.model.*
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TimeRulesScreen(
    viewModel: TimeRulesViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    LaunchedEffect(uiState.successMessage) {
        uiState.successMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSuccessMessage()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        floatingActionButton = {
            if (uiState.selectedTab == 0) {
                FloatingActionButton(onClick = { viewModel.showCreateRuleDialog() }) {
                    Icon(Icons.Default.Add, contentDescription = "新建规则")
                }
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
        ) {
            Text(
                text = "时间规则",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.padding(vertical = 16.dp)
            )

            TabRow(
                selectedTabIndex = uiState.selectedTab,
                modifier = Modifier.fillMaxWidth()
            ) {
                Tab(
                    selected = uiState.selectedTab == 0,
                    onClick = { viewModel.setSelectedTab(0) },
                    text = { Text("时间规则") },
                    icon = { Icon(Icons.Default.Schedule, contentDescription = null) }
                )
                Tab(
                    selected = uiState.selectedTab == 1,
                    onClick = { viewModel.setSelectedTab(1) },
                    text = { Text("系统事件") },
                    icon = { Icon(Icons.Default.Event, contentDescription = null) }
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            when {
                uiState.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                uiState.selectedTab == 0 -> {
                    RuleList(
                        rules = viewModel.getFilteredRules(),
                        onRuleClick = { viewModel.showDetailDialog(it) }
                    )
                }
                else -> {
                    EventList(
                        events = uiState.systemEvents
                    )
                }
            }
        }
    }

    // Create Rule Dialog
    if (uiState.showCreateRuleDialog) {
        CreateRuleDialog(
            onDismiss = { viewModel.dismissCreateRuleDialog() },
            onConfirm = { relatedId, relatedType, trigger, target, offset, unit, direction, party, tgeParam1, tgeParam2, taeParam1, taeParam2, inherit ->
                viewModel.createTimeRule(relatedId, relatedType, trigger, target, offset, unit, direction, party, tgeParam1, tgeParam2, taeParam1, taeParam2, inherit)
            }
        )
    }

    // Detail Dialog
    if (uiState.showDetailDialog && uiState.selectedRule != null) {
        RuleDetailDialog(
            rule = uiState.selectedRule!!,
            onDismiss = { viewModel.dismissDetailDialog() },
            onUpdateStatus = { status, result ->
                viewModel.updateRuleStatus(uiState.selectedRule!!.id, status, result)
            },
            onDelete = { viewModel.deleteRule(uiState.selectedRule!!) }
        )
    }
}

@Composable
private fun RuleList(
    rules: List<TimeRule>,
    onRuleClick: (TimeRule) -> Unit
) {
    if (rules.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Schedule,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无时间规则", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            items(rules, key = { it.id }) { rule ->
                RuleCard(rule = rule, onClick = { onRuleClick(rule) })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RuleCard(
    rule: TimeRule,
    onClick: () -> Unit
) {
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()) }
    val currentWarning = rule.calculateWarning()

    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = rule.targetEvent.displayName,
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = rule.getRelatedDisplayName(),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    StatusBadge(status = rule.status)
                    currentWarning?.let {
                        Spacer(modifier = Modifier.height(4.dp))
                        WarningBadge(warning = it)
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                rule.party?.let {
                    InfoChip(it.displayName)
                }
                rule.triggerEvent?.let {
                    InfoChip("触发: ${it.displayName}")
                }
                rule.offset?.let { offset ->
                    rule.unit?.let { unit ->
                        rule.direction?.let { dir ->
                            InfoChip("${offset}${unit.displayName}${dir.uiName}")
                        }
                    }
                }
            }

            rule.targetTime?.let { time ->
                Text(
                    text = "目标: ${dateFormat.format(Date(time))}",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (rule.isOverdue()) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun EventList(
    events: List<SystemEvent>
) {
    if (events.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Event,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无系统事件", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            items(events, key = { it.id }) { event ->
                EventCard(event = event)
            }
        }
    }
}

@Composable
private fun EventCard(
    event: SystemEvent
) {
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()) }

    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = event.eventType.displayName,
                    style = MaterialTheme.typography.titleMedium
                )
                event.description?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Text(
                text = dateFormat.format(Date(event.timestamp)),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun StatusBadge(status: RuleStatus) {
    val (bgColor, textColor) = when (status) {
        RuleStatus.ACTIVE -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
        RuleStatus.INACTIVE -> Color(0xFFECEFF1) to Color(0xFF546E7A)
        RuleStatus.TEMPLATE -> Color(0xFFF3E5F5) to Color(0xFF7B1FA2)
        RuleStatus.HAS_RESULT -> Color(0xFFE3F2FD) to Color(0xFF1976D2)
        RuleStatus.ENDED -> Color(0xFFFFF3E0) to Color(0xFFE65100)
    }
    Surface(color = bgColor, shape = MaterialTheme.shapes.small) {
        Text(
            text = status.displayName,
            style = MaterialTheme.typography.labelMedium,
            color = textColor,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

@Composable
private fun WarningBadge(warning: WarningLevel) {
    val (bgColor, textColor) = when (warning) {
        WarningLevel.GREEN -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
        WarningLevel.YELLOW -> Color(0xFFFFFDE7) to Color(0xFFF57F17)
        WarningLevel.ORANGE -> Color(0xFFFFF3E0) to Color(0xFFE65100)
        WarningLevel.RED -> Color(0xFFFFEBEE) to Color(0xFFC62828)
    }
    Surface(color = bgColor, shape = MaterialTheme.shapes.small) {
        Text(
            text = warning.displayName,
            style = MaterialTheme.typography.labelSmall,
            color = textColor,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}

@Composable
private fun InfoChip(text: String) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.small
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreateRuleDialog(
    onDismiss: () -> Unit,
    onConfirm: (Long, RelatedType, RuleEvent?, RuleEvent, Int?, TimeUnit?, Direction?, Party?, String?, String?, String?, String?, InheritLevel) -> Unit
) {
    var relatedId by remember { mutableStateOf("") }
    var selectedRelatedType by remember { mutableStateOf(RelatedType.VIRTUAL_CONTRACT) }
    var selectedTrigger by remember { mutableStateOf<RuleEvent?>(null) }
    var selectedTarget by remember { mutableStateOf(RuleEvent.VC_CREATED) }
    var offsetDays by remember { mutableStateOf("") }
    var selectedUnit by remember { mutableStateOf<TimeUnit?>(TimeUnit.CALENDAR_DAY) }
    var selectedDirection by remember { mutableStateOf<Direction?>(Direction.AFTER) }
    var selectedParty by remember { mutableStateOf<Party?>(null) }
    var tgeParam1 by remember { mutableStateOf("") }
    var tgeParam2 by remember { mutableStateOf("") }
    var taeParam1 by remember { mutableStateOf("") }
    var taeParam2 by remember { mutableStateOf("") }
    var selectedInherit by remember { mutableStateOf(InheritLevel.SELF) }

    var relatedTypeExpanded by remember { mutableStateOf(false) }
    var triggerExpanded by remember { mutableStateOf(false) }
    var targetExpanded by remember { mutableStateOf(false) }
    var unitExpanded by remember { mutableStateOf(false) }
    var directionExpanded by remember { mutableStateOf(false) }
    var partyExpanded by remember { mutableStateOf(false) }
    var inheritExpanded by remember { mutableStateOf(false) }

    // 根据 selectedRelatedType 获取可选的继承级别
    fun getAvailableInheritLevels(relatedType: RelatedType): List<InheritLevel> = when (relatedType) {
        RelatedType.BUSINESS, RelatedType.SUPPLY_CHAIN -> InheritLevel.entries.toList()
        RelatedType.VIRTUAL_CONTRACT -> listOf(InheritLevel.SELF, InheritLevel.NEAR)
        RelatedType.LOGISTICS -> listOf(InheritLevel.SELF)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建时间规则") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = relatedId,
                    onValueChange = { relatedId = it.filter { c -> c.isDigit() } },
                    label = { Text("关联ID *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                ExposedDropdownMenuBox(
                    expanded = relatedTypeExpanded,
                    onExpandedChange = { relatedTypeExpanded = !relatedTypeExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedRelatedType.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("关联类型") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = relatedTypeExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = relatedTypeExpanded,
                        onDismissRequest = { relatedTypeExpanded = false }
                    ) {
                        RelatedType.entries.forEach { type ->
                            DropdownMenuItem(
                                text = { Text(type.displayName) },
                                onClick = {
                                    selectedRelatedType = type
                                    // 重置继承级别为新类型的第一选项
                                    val available = getAvailableInheritLevels(type)
                                    if (selectedInherit !in available) {
                                        selectedInherit = available.first()
                                    }
                                    relatedTypeExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = triggerExpanded,
                    onExpandedChange = { triggerExpanded = !triggerExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedTrigger?.displayName ?: "无",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("触发事件") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = triggerExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = triggerExpanded,
                        onDismissRequest = { triggerExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无 (绝对日期)") },
                            onClick = {
                                selectedTrigger = null
                                triggerExpanded = false
                            }
                        )
                        RuleEvent.entries.forEach { event ->
                            DropdownMenuItem(
                                text = { Text(event.displayName) },
                                onClick = {
                                    selectedTrigger = event
                                    triggerExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = tgeParam1,
                    onValueChange = { tgeParam1 = it },
                    label = { Text("触发参数1 (tgeParam1)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = tgeParam2,
                    onValueChange = { tgeParam2 = it },
                    label = { Text("触发参数2 (tgeParam2)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                ExposedDropdownMenuBox(
                    expanded = targetExpanded,
                    onExpandedChange = { targetExpanded = !targetExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedTarget.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("目标事件 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = targetExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = targetExpanded,
                        onDismissRequest = { targetExpanded = false }
                    ) {
                        RuleEvent.entries.forEach { event ->
                            DropdownMenuItem(
                                text = { Text(event.displayName) },
                                onClick = {
                                    selectedTarget = event
                                    targetExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = taeParam1,
                    onValueChange = { taeParam1 = it },
                    label = { Text("目标参数1 (taeParam1)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = taeParam2,
                    onValueChange = { taeParam2 = it },
                    label = { Text("目标参数2 (taeParam2)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = offsetDays,
                    onValueChange = { offsetDays = it.filter { c -> c.isDigit() } },
                    label = { Text("偏移天数") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                ExposedDropdownMenuBox(
                    expanded = unitExpanded,
                    onExpandedChange = { unitExpanded = !unitExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedUnit?.displayName ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("时间单位") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = unitExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = unitExpanded,
                        onDismissRequest = { unitExpanded = false }
                    ) {
                        TimeUnit.entries.forEach { unit ->
                            DropdownMenuItem(
                                text = { Text(unit.displayName) },
                                onClick = {
                                    selectedUnit = unit
                                    unitExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = directionExpanded,
                    onExpandedChange = { directionExpanded = !directionExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedDirection?.uiName ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("方向") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = directionExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = directionExpanded,
                        onDismissRequest = { directionExpanded = false }
                    ) {
                        Direction.entries.forEach { dir ->
                            DropdownMenuItem(
                                text = { Text(dir.uiName) },
                                onClick = {
                                    selectedDirection = dir
                                    directionExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = partyExpanded,
                    onExpandedChange = { partyExpanded = !partyExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedParty?.displayName ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("责任方") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = partyExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = partyExpanded,
                        onDismissRequest = { partyExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无") },
                            onClick = {
                                selectedParty = null
                                partyExpanded = false
                            }
                        )
                        Party.entries.forEach { party ->
                            DropdownMenuItem(
                                text = { Text(party.displayName) },
                                onClick = {
                                    selectedParty = party
                                    partyExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = inheritExpanded,
                    onExpandedChange = { inheritExpanded = !inheritExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedInherit.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("作用范围") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = inheritExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = inheritExpanded,
                        onDismissRequest = { inheritExpanded = false }
                    ) {
                        getAvailableInheritLevels(selectedRelatedType).forEach { level ->
                            DropdownMenuItem(
                                text = { Text(level.displayName) },
                                onClick = {
                                    selectedInherit = level
                                    inheritExpanded = false
                                }
                            )
                        }
                    }
                }

                // 状态根据继承级别自动确定，不可手动选择
                val statusHint = if (selectedInherit == InheritLevel.SELF) "将自动设为'生效'" else "将自动设为'模板'"
                OutlinedTextField(
                    value = statusHint,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("规则状态") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    relatedId.toLongOrNull()?.let { id ->
                        onConfirm(
                            id,
                            selectedRelatedType,
                            selectedTrigger,
                            selectedTarget,
                            offsetDays.toIntOrNull(),
                            selectedUnit,
                            selectedDirection,
                            selectedParty,
                            tgeParam1.takeIf { it.isNotBlank() },
                            tgeParam2.takeIf { it.isNotBlank() },
                            taeParam1.takeIf { it.isNotBlank() },
                            taeParam2.takeIf { it.isNotBlank() },
                            selectedInherit
                        )
                    }
                },
                enabled = relatedId.isNotBlank()
            ) {
                Text("创建")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RuleDetailDialog(
    rule: TimeRule,
    onDismiss: () -> Unit,
    onUpdateStatus: (RuleStatus, RuleResult?) -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var statusExpanded by remember { mutableStateOf(false) }
    var selectedStatus by remember { mutableStateOf(rule.status) }
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()) }
    val currentWarning = rule.calculateWarning()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("规则 #${rule.id}") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                DetailRow("关联", rule.getRelatedDisplayName())
                DetailRow("目标事件", rule.targetEvent.displayName)
                rule.party?.let { DetailRow("责任方", it.displayName) }
                rule.triggerEvent?.let { DetailRow("触发事件", it.displayName) }
                rule.offset?.let { offset ->
                    rule.unit?.let { unit ->
                        rule.direction?.let { dir ->
                            DetailRow("时间约束", "${offset}${unit.displayName}${dir.uiName}")
                        }
                    }
                }
                rule.targetTime?.let { DetailRow("目标时间", dateFormat.format(Date(it))) }
                rule.flagTime?.let { DetailRow("标杆时间", dateFormat.format(Date(it))) }

                HorizontalDivider()

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("状态", style = MaterialTheme.typography.bodyMedium)
                    ExposedDropdownMenuBox(
                        expanded = statusExpanded,
                        onExpandedChange = { statusExpanded = !statusExpanded },
                        modifier = Modifier.width(150.dp)
                    ) {
                        OutlinedTextField(
                            value = selectedStatus.displayName,
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = statusExpanded) },
                            modifier = Modifier.menuAnchor(),
                            singleLine = true
                        )
                        ExposedDropdownMenu(
                            expanded = statusExpanded,
                            onDismissRequest = { statusExpanded = false }
                        ) {
                            RuleStatus.entries.forEach { status ->
                                DropdownMenuItem(
                                    text = { Text(status.displayName) },
                                    onClick = {
                                        selectedStatus = status
                                        statusExpanded = false
                                    }
                                )
                            }
                        }
                    }
                }

                currentWarning?.let {
                    DetailRow("预警级别", it.displayName)
                }

                rule.result?.let {
                    DetailRow("结果", it.displayName)
                }

                HorizontalDivider()

                OutlinedButton(
                    onClick = { showDeleteConfirm = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("删除规则")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    if (selectedStatus != rule.status) {
                        val result = if (selectedStatus == RuleStatus.HAS_RESULT) RuleResult.COMPLIANT else null
                        onUpdateStatus(selectedStatus, result)
                    }
                    onDismiss()
                }
            ) {
                Text("保存")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭")
            }
        }
    )

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("确认删除") },
            text = { Text("确定要删除此时间规则吗？") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDeleteConfirm = false
                        onDelete()
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("删除")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
