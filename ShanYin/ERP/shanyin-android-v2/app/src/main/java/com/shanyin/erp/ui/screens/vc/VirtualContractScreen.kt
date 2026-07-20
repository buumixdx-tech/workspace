package com.shanyin.erp.ui.screens.vc

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VirtualContractScreen(
    viewModel: VirtualContractListViewModel = hiltViewModel()
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
            FloatingActionButton(onClick = { viewModel.showCreateDialog() }) {
                Icon(Icons.Default.Add, contentDescription = "新建合同")
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
                text = "虚拟合同",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.padding(vertical = 16.dp)
            )

            // Tab row for filtering
            TabRow(
                selectedTabIndex = uiState.selectedTab,
                modifier = Modifier.fillMaxWidth()
            ) {
                Tab(
                    selected = uiState.selectedTab == 0,
                    onClick = { viewModel.setSelectedTab(0) },
                    text = { Text("全部") }
                )
                Tab(
                    selected = uiState.selectedTab == 1,
                    onClick = { viewModel.setSelectedTab(1) },
                    text = { Text("执行中") }
                )
                Tab(
                    selected = uiState.selectedTab == 2,
                    onClick = { viewModel.setSelectedTab(2) },
                    text = { Text("已完成") }
                )
                Tab(
                    selected = uiState.selectedTab == 3,
                    onClick = { viewModel.setSelectedTab(3) },
                    text = { Text("已终止") }
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            when {
                uiState.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                uiState.filteredVCs.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.Receipt,
                                contentDescription = null,
                                modifier = Modifier.size(64.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("暂无合同，点击 + 新建", style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
                else -> {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = PaddingValues(bottom = 80.dp)
                    ) {
                        items(uiState.filteredVCs, key = { it.id }) { vc ->
                            VirtualContractCard(
                                vc = vc,
                                businessName = uiState.businesses.find { it.id == vc.businessId }?.let { b ->
                                    uiState.customers.find { it.id == b.customerId }?.name ?: "客户#${b.customerId}"
                                },
                                onClick = { viewModel.showDetailDialog(vc) }
                            )
                        }
                    }
                }
            }
        }
    }

    if (uiState.showCreateDialog) {
        CreateVCDialog(
            businesses = uiState.businesses,
            skus = uiState.skus,
            onDismiss = { viewModel.dismissCreateDialog() },
            onConfirm = { type, businessId, description, elements, deposit ->
                viewModel.createVC(type, businessId, description, elements, deposit)
            }
        )
    }

    if (uiState.showDetailDialog && uiState.selectedVC != null) {
        VCDetailDialog(
            vc = uiState.selectedVC!!,
            statusLogs = viewModel.statusLogs.collectAsState().value,
            businessName = viewModel.getBusinessNameForVc(uiState.selectedVC!!),
            supplierName = viewModel.getSupplierNameForVc(uiState.selectedVC!!),
            logisticsList = viewModel.selectedVcLogistics.collectAsState().value,
            equipmentList = viewModel.selectedVcEquipment.collectAsState().value,
            onDismiss = { viewModel.dismissDetailDialog() },
            onTerminate = { viewModel.terminate(uiState.selectedVC!!.id) },
            onInitLogisticsSuggestions = { viewModel.generateLogisticsSuggestions(uiState.selectedVC!!) }
        )
    }

    // 物流方案建议对话框
    if (uiState.showLogisticsSuggestionsDialog) {
        LogisticsSuggestionsDialog(
            suggestions = uiState.logisticsSuggestions,
            isGenerating = uiState.isGeneratingSuggestions,
            onDismiss = { viewModel.dismissLogisticsSuggestionsDialog() },
            onConfirm = { viewModel.confirmLogisticsSuggestions() },
            onUpdateTracking = { index, tracking -> viewModel.updateSuggestionTrackingNumber(index, tracking) }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VirtualContractCard(
    vc: VirtualContract,
    businessName: String?,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "#${vc.id} ${vc.type.displayName}",
                        style = MaterialTheme.typography.titleMedium
                    )
                    vc.description?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
                StatusBadge(status = vc.status)
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Three status indicators
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatusIndicator(label = "VC状态", value = vc.status.displayName, color = getUnifiedStatusColor(vc.status))
                StatusIndicator(label = "标的物", value = vc.subjectStatus.displayName, color = getUnifiedStatusColor(vc.subjectStatus))
                StatusIndicator(label = "资金", value = vc.cashStatus.displayName, color = getUnifiedStatusColor(vc.cashStatus))
            }

            if (vc.elements.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "标的物: ${vc.elements.size}项 | 总价: ¥${vc.elements.sumOf { it.subtotal }}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun StatusIndicator(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Surface(
            color = color.copy(alpha = 0.2f),
            shape = MaterialTheme.shapes.small
        ) {
            Text(
                text = value,
                style = MaterialTheme.typography.labelSmall,
                color = color,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
            )
        }
    }
}

// ========== 统一状态颜色 ==========
// 规则：相同语义的状态在不同分类中使用相同颜色
// - 执行/进行中 → 蓝色
// - 完成/已结束 → 绿色
// - 终止/取消 → 红色/灰色
// - 中间态（发货/签收/预付）→ 橙色

private fun getUnifiedStatusColor(status: Any): Color = when (status) {
    // VCStatus
    is VCStatus -> when (status) {
        VCStatus.EXECUTING -> Color(0xFF1976D2)
        VCStatus.COMPLETED -> Color(0xFF388E3C)
        VCStatus.TERMINATED -> Color(0xFFD32F2F)
        VCStatus.CANCELLED -> Color(0xFF757575)
    }
    // SubjectStatus
    is SubjectStatus -> when (status) {
        SubjectStatus.EXECUTING -> Color(0xFF1976D2)
        SubjectStatus.SHIPPED -> Color(0xFFFF9800)
        SubjectStatus.SIGNED -> Color(0xFFFF9800)
        SubjectStatus.COMPLETED -> Color(0xFF388E3C)
    }
    // CashStatus
    is CashStatus -> when (status) {
        CashStatus.EXECUTING -> Color(0xFF1976D2)
        CashStatus.PREPAID -> Color(0xFFFF9800)
        CashStatus.COMPLETED -> Color(0xFF388E3C)
    }
    else -> Color(0xFF757575)
}

@Composable
private fun StatusBadge(status: VCStatus) {
    val color = getUnifiedStatusColor(status)
    val bgColor = color.copy(alpha = 0.15f)
    Surface(color = bgColor, shape = MaterialTheme.shapes.small) {
        Text(
            text = status.displayName,
            style = MaterialTheme.typography.labelMedium,
            color = color,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreateVCDialog(
    businesses: List<Business>,
    skus: List<Sku>,
    onDismiss: () -> Unit,
    onConfirm: (VCType, Long?, String, List<VCElement>, Double) -> Unit
) {
    var selectedType by remember { mutableStateOf(VCType.EQUIPMENT_PROCUREMENT) }
    var selectedBusiness by remember { mutableStateOf<Business?>(null) }
    var description by remember { mutableStateOf("") }
    var deposit by remember { mutableStateOf("") }
    var typeExpanded by remember { mutableStateOf(false) }
    var businessExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建虚拟合同") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // VC Type selector
                ExposedDropdownMenuBox(
                    expanded = typeExpanded,
                    onExpandedChange = { typeExpanded = !typeExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedType.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("合同类型 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = typeExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = typeExpanded,
                        onDismissRequest = { typeExpanded = false }
                    ) {
                        VCType.entries.forEach { type ->
                            DropdownMenuItem(
                                text = { Text("${type.displayName} - ${type.description}") },
                                onClick = {
                                    selectedType = type
                                    typeExpanded = false
                                }
                            )
                        }
                    }
                }

                // Business selector
                ExposedDropdownMenuBox(
                    expanded = businessExpanded,
                    onExpandedChange = { businessExpanded = !businessExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedBusiness?.id?.toString() ?: "无关联业务",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("关联业务") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = businessExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = businessExpanded,
                        onDismissRequest = { businessExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无关联业务") },
                            onClick = {
                                selectedBusiness = null
                                businessExpanded = false
                            }
                        )
                        businesses.forEach { business ->
                            DropdownMenuItem(
                                text = { Text("#${business.id} - ${business.status?.displayName ?: "?"}") },
                                onClick = {
                                    selectedBusiness = business
                                    businessExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述 *") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 2,
                    maxLines = 4
                )

                OutlinedTextField(
                    value = deposit,
                    onValueChange = { deposit = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("押金金额") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val depositAmount = deposit.toDoubleOrNull() ?: 0.0
                    onConfirm(
                        selectedType,
                        selectedBusiness?.id,
                        description,
                        emptyList(), // Elements will be added in detail screen
                        depositAmount
                    )
                },
                enabled = description.isNotBlank()
            ) {
                Text("下一步")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}

@Composable
private fun VCDetailDialog(
    vc: VirtualContract,
    statusLogs: List<VCStatusLog>,
    businessName: String?,
    supplierName: String?,
    logisticsList: List<Logistics>,
    equipmentList: List<EquipmentInventory>,
    onDismiss: () -> Unit,
    onTerminate: () -> Unit,
    onInitLogisticsSuggestions: () -> Unit
) {
    var showTerminateConfirm by remember { mutableStateOf(false) }
    var showFullTimeline by remember { mutableStateOf(false) }
    var showFullVcInfo by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                when {
                    showFullTimeline -> "完整时间线"
                    showFullVcInfo -> "VC信息"
                    else -> "#${vc.id} ${vc.type.displayName}"
                }
            )
        },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (showFullTimeline) {
                    // ===== 完整时间线视图（按三种状态分栏） =====
                    val statusLogsByCategory = statusLogs.groupBy { it.category }
                    val vcLogs = statusLogsByCategory[StatusLogCategory.STATUS].orEmpty()
                    val subjectLogs = statusLogsByCategory[StatusLogCategory.SUBJECT].orEmpty()
                    val cashLogs = statusLogsByCategory[StatusLogCategory.CASH].orEmpty()

                    Column(modifier = Modifier.heightIn(max = 400.dp)) {
                        if (statusLogs.isEmpty()) {
                            Text("暂无状态变更记录", style = MaterialTheme.typography.bodyMedium)
                        } else {
                            LazyColumn(
                                modifier = Modifier.weight(1f),
                                verticalArrangement = Arrangement.spacedBy(16.dp)
                            ) {
                                // VC状态
                                item {
                                    Text(
                                        text = "VC状态",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                                if (vcLogs.isEmpty()) {
                                    item {
                                        Text("无变更记录", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                } else {
                                    items(vcLogs) { log ->
                                        TimelineItem(
                                            categoryLabel = log.category.displayName,
                                            statusName = log.statusName,
                                            timestamp = log.timestamp,
                                            isLast = log == vcLogs.last()
                                        )
                                    }
                                }

                                // 标的物状态
                                item {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = "标的物状态",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                                if (subjectLogs.isEmpty()) {
                                    item {
                                        Text("无变更记录", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                } else {
                                    items(subjectLogs) { log ->
                                        TimelineItem(
                                            categoryLabel = log.category.displayName,
                                            statusName = log.statusName,
                                            timestamp = log.timestamp,
                                            isLast = log == subjectLogs.last()
                                        )
                                    }
                                }

                                // 资金状态
                                item {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = "资金状态",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                                if (cashLogs.isEmpty()) {
                                    item {
                                        Text("无变更记录", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                } else {
                                    items(cashLogs) { log ->
                                        TimelineItem(
                                            categoryLabel = log.category.displayName,
                                            statusName = log.statusName,
                                            timestamp = log.timestamp,
                                            isLast = log == cashLogs.last()
                                        )
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = { showFullTimeline = false },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("返回详情")
                        }
                    }
                } else if (showFullVcInfo) {
                    // ===== 完整VC信息视图 =====
                    val totalElementAmount = vc.elements.sumOf { (it as? SkusFormatElement)?.subtotal ?: 0.0 }

                    Column(modifier = Modifier.heightIn(max = 400.dp)) {
                        Column(
                            modifier = Modifier.weight(1f).verticalScroll(rememberScrollState()),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            DetailRow("合同类型", vc.type.displayName)
                            DetailRow("合同描述", vc.description ?: "无")

                            HorizontalDivider()

                            // 交易对手
                            if (vc.type == VCType.EQUIPMENT_PROCUREMENT || vc.type == VCType.MATERIAL_PROCUREMENT) {
                                DetailRow("供应商", supplierName ?: "未知")
                            }
                            if (vc.type != VCType.EQUIPMENT_STOCK) {
                                DetailRow("客户", businessName ?: "未知")
                            }

                            HorizontalDivider()

                            // 标的物明细
                            Text(
                                text = "标的物明细",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.primary
                            )
                            vc.elements.forEach { element ->
                                Column(modifier = Modifier.fillMaxWidth()) {
                                    Text(
                                        text = element.skuName,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        text = "${element.quantity} x ¥${element.unitPrice} = ¥${element.subtotal}",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                    if (element.deposit > 0) {
                                        Text(
                                            text = "押金: ¥${element.deposit}/台",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                            DetailRow("标的物总额", "¥$totalElementAmount")

                            // 资金汇总
                            HorizontalDivider()
                            val amountLabels = getVcAmountLabels(vc)
                            Text(
                                text = "资金汇总",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.primary
                            )
                            DetailRow(amountLabels.totalLabel, "¥${vc.depositInfo.totalAmount}")
                            DetailRow(amountLabels.actualLabel, "¥${vc.depositInfo.actualAmount}")
                            DetailRow(amountLabels.depositShouldLabel, "¥${vc.depositInfo.shouldReceive}")
                            DetailRow(amountLabels.depositActualLabel, "¥${vc.depositInfo.actualDeposit}")

                            // 发货信息（多点位部署时列出所有点位）
                            if (equipmentList.isNotEmpty()) {
                                HorizontalDivider()
                                Text(
                                    text = "部署点位（共${equipmentList.size}个）",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                equipmentList.forEach { eq ->
                                    DetailRow(
                                        eq.pointName ?: "点位#${eq.pointId}",
                                        "${eq.skuName ?: "设备"} | ${eq.operationalStatus.displayName} | 押金¥${eq.depositAmount}"
                                    )
                                }
                            } else if (logisticsList.isNotEmpty()) {
                                HorizontalDivider()
                                Text(
                                    text = "物流信息",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                logisticsList.forEach { log ->
                                    Card(
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Column(modifier = Modifier.padding(12.dp)) {
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Column(modifier = Modifier.weight(1f)) {
                                                    Text(
                                                        text = "物流 #${log.id}",
                                                        style = MaterialTheme.typography.titleSmall
                                                    )
                                                    log.vcTypeName?.let {
                                                        Text(
                                                            text = it,
                                                            style = MaterialTheme.typography.bodySmall,
                                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                                        )
                                                    }
                                                }
                                                LogisticsStatusBadge(status = log.status)
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                                if (log.financeTriggered) {
                                                    InfoChip("已触发财务")
                                                }
                                                if (log.expressOrders.isNotEmpty()) {
                                                    InfoChip("快递单: ${log.expressOrders.size}")
                                                }
                                            }
                                            // 显示快递单明细
                                            log.expressOrders.forEach { order ->
                                                order.trackingNumber?.let {
                                                    DetailRow("运单号", it)
                                                }
                                            }
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(8.dp))
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = { showFullVcInfo = false },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("返回详情")
                        }
                    }
                } else {
                    // ===== 详情视图 =====

                    // Description
                    vc.description?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }

                    HorizontalDivider()

                    // 状态汇总（只读，由物流+资金自动驱动）
                    Text(
                        text = "状态汇总",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )

                    // VC状态
                    DetailRow("VC状态", vc.status.displayName)

                    // 标的物状态
                    DetailRow("标的物状态", vc.subjectStatus.displayName)

                    // 资金状态 + 查看历史按钮
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "资金状态",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = vc.cashStatus.displayName,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    if (statusLogs.isNotEmpty()) {
                        TextButton(
                            onClick = { showFullTimeline = true },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("查看状态变更历史", style = MaterialTheme.typography.bodySmall)
                        }
                    }

                    HorizontalDivider()

                    // 资金汇总
                    val totalElementAmount = vc.elements.sumOf { (it as? SkusFormatElement)?.subtotal ?: 0.0 }
                    val amountLabels = getVcAmountLabels(vc)
                    Text(
                        text = "资金汇总",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    DetailRow(amountLabels.totalLabel, "¥${vc.depositInfo.totalAmount}")
                    DetailRow(amountLabels.actualLabel, "¥${vc.depositInfo.actualAmount}")
                    DetailRow(amountLabels.depositShouldLabel, "¥${vc.depositInfo.shouldReceive}")
                    DetailRow(amountLabels.depositActualLabel, "¥${vc.depositInfo.actualDeposit}")
                    if (vc.elements.isNotEmpty() || businessName != null || supplierName != null) {
                        HorizontalDivider()
                        Text(
                            text = "合同内容",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary
                        )

                        // 简要标的物概览
                        val elementSummary = vc.elements.joinToString("、") { "${it.skuName}x${it.quantity}" }
                        if (elementSummary.isNotEmpty()) {
                            Text(
                                text = "标的: $elementSummary",
                                style = MaterialTheme.typography.bodySmall,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }

                        // 客户/供应商
                        if (vc.type == VCType.EQUIPMENT_PROCUREMENT || vc.type == VCType.MATERIAL_PROCUREMENT) {
                            Text(
                                text = "供应商: ${supplierName ?: "未知"}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        if (vc.type != VCType.EQUIPMENT_STOCK) {
                            Text(
                                text = "客户: ${businessName ?: "未知"}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }

                        // 发货信息概述
                        if (equipmentList.isNotEmpty()) {
                            Text(
                                text = "发货: ${equipmentList.size}个点位待部署",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else if (logisticsList.isNotEmpty()) {
                            val log = logisticsList.first()
                            Text(
                                text = "物流: ${log.status.displayName}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }

                        TextButton(
                            onClick = { showFullVcInfo = true },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("查看VC信息", style = MaterialTheme.typography.bodySmall)
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Action buttons
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // 初始化物流方案建议（仅当 VC 还没有物流单且有标的物时显示）
                        if (vc.elements.isNotEmpty() && logisticsList.isEmpty() && vc.status == VCStatus.EXECUTING) {
                            OutlinedButton(
                                onClick = onInitLogisticsSuggestions,
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(Icons.Default.LocalShipping, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("初始化物流")
                            }
                        }

                        if (vc.status != VCStatus.TERMINATED) {
                            OutlinedButton(
                                onClick = { showTerminateConfirm = true },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    contentColor = MaterialTheme.colorScheme.error
                                )
                            ) {
                                Text("终止")
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭")
            }
        }
    )

    // 终止确认
    if (showTerminateConfirm) {
        AlertDialog(
            onDismissRequest = { showTerminateConfirm = false },
            title = { Text("确认终止合同") },
            text = { Text("确定要终止此合同吗？终止后不可恢复。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showTerminateConfirm = false
                        onTerminate()
                        onDismiss()
                    },
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Text("确认终止")
                }
            },
            dismissButton = {
                TextButton(onClick = { showTerminateConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> StatusControl(
    label: String,
    value: String,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    onSelect: (T) -> Unit,
    options: List<T>,
    displayNameFor: (T) -> String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium
        )
        Box {
            FilterChip(
                selected = false,
                onClick = { onExpandedChange(!expanded) },
                label = { Text(value) },
                trailingIcon = { Icon(Icons.Default.ArrowDropDown, null) }
            )
            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { onExpandedChange(false) }
            ) {
                options.forEach { option ->
                    DropdownMenuItem(
                        text = { Text(displayNameFor(option)) },
                        onClick = { onSelect(option) }
                    )
                }
            }
        }
    }
}

@Composable
private fun TimelineItem(
    categoryLabel: String,
    statusName: String,
    timestamp: Long,
    isLast: Boolean
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.Top
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .background(
                        MaterialTheme.colorScheme.primary,
                        MaterialTheme.shapes.extraSmall
                    )
            )
            if (!isLast) {
                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .height(40.dp)
                        .background(MaterialTheme.colorScheme.outlineVariant)
                )
            }
        }
        Column {
            Text(
                text = "[$categoryLabel] $statusName",
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                text = formatTimestamp(timestamp),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall
        )
    }
}

private fun formatTimestamp(timestamp: Long): String {
    val sdf = java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault())
    return sdf.format(java.util.Date(timestamp))
}

@Composable
private fun LogisticsStatusBadge(status: LogisticsStatus) {
    val (bgColor, textColor) = when (status) {
        LogisticsStatus.PENDING -> Color(0xFFFFF3E0) to Color(0xFFE65100)
        LogisticsStatus.IN_TRANSIT -> Color(0xFFE3F2FD) to Color(0xFF1976D2)
        LogisticsStatus.SIGNED -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
        LogisticsStatus.COMPLETED -> Color(0xFFE8F5E9) to Color(0xFF2E7D32)
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

/** 根据 VC 类型返回正确的资金字段标签 */
private data class VcAmountLabels(
    val totalLabel: String,      // 应收/应付总额
    val actualLabel: String,    // 实收/实付
    val depositShouldLabel: String, // 应收/应付押金
    val depositActualLabel: String  // 实收/实付押金
)

private fun getVcAmountLabels(vc: VirtualContract): VcAmountLabels {
    return when (vc.type) {
        // 我们向供应商付款：应付
        VCType.EQUIPMENT_PROCUREMENT,
        VCType.EQUIPMENT_STOCK,
        VCType.MATERIAL_PROCUREMENT -> VcAmountLabels(
            totalLabel = "应付总额",
            actualLabel = "实付总额",
            depositShouldLabel = "应付押金",
            depositActualLabel = "实付押金"
        )
        // 客户向我们付款：应收
        VCType.MATERIAL_SUPPLY,
        VCType.INVENTORY_ALLOCATION -> VcAmountLabels(
            totalLabel = "应收总额",
            actualLabel = "实收总额",
            depositShouldLabel = "应收押金",
            depositActualLabel = "实收押金"
        )
        // 退货：根据 relatedVcId 判断方向
        // 有 relatedVcId = 客户向我们退货（我们退款给客户）→ 应付
        // 无 relatedVcId = 我们向供应商退货（供应商退款给我们）→ 应收
        VCType.RETURN -> if (vc.relatedVcId != null) {
            VcAmountLabels(
                totalLabel = "应付退款",
                actualLabel = "实付退款",
                depositShouldLabel = "应收押金",
                depositActualLabel = "实退押金"
            )
        } else {
            VcAmountLabels(
                totalLabel = "应收退款",
                actualLabel = "实收退款",
                depositShouldLabel = "应付押金",
                depositActualLabel = "实付押金"
            )
        }
    }
}

// ==================== 物流方案建议对话框 ====================

@Composable
private fun LogisticsSuggestionsDialog(
    suggestions: List<ExpressOrderSuggestion>,
    isGenerating: Boolean,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
    onUpdateTracking: (Int, String) -> Unit
) {
    if (isGenerating) {
        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text("生成物流方案建议") },
            text = {
                Box(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            },
            confirmButton = {}
        )
        return
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("物流方案建议") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 400.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "根据 ${suggestions.size} 个标的物生成快递单建议：",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                HorizontalDivider()

                suggestions.forEachIndexed { index, suggestion ->
                    SuggestionCard(
                        index = index,
                        suggestion = suggestion,
                        onUpdateTracking = { newTracking ->
                            onUpdateTracking(index, newTracking)
                        }
                    )
                }
            }
        },
        confirmButton = {
            Button(onClick = onConfirm) {
                Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("确认生成")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}

@Composable
private fun SuggestionCard(
    index: Int,
    suggestion: ExpressOrderSuggestion,
    onUpdateTracking: (String) -> Unit
) {
    var trackingInput by remember(suggestion.trackingNumber) { mutableStateOf(suggestion.trackingNumber) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // 快递单号
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "快递单 #${index + 1}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }

            OutlinedTextField(
                value = trackingInput,
                onValueChange = {
                    trackingInput = it
                    onUpdateTracking(it)
                },
                label = { Text("快递单号") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            // 地址信息
            if (suggestion.addressInfo.shippingPointName?.isNotBlank() == true ||
                suggestion.addressInfo.receivingPointName?.isNotBlank() == true
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "发货: ${suggestion.addressInfo.shippingPointName ?: "-"}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        suggestion.addressInfo.shippingAddress?.takeIf { it.isNotBlank() }?.let {
                            Text(
                                text = it,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "收货: ${suggestion.addressInfo.receivingPointName ?: "-"}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        suggestion.addressInfo.receivingAddress?.takeIf { it.isNotBlank() }?.let {
                            Text(
                                text = it,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            // 货品明细
            suggestion.items.forEach { item ->
                Text(
                    text = "${item.skuName} x ${item.quantity}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
