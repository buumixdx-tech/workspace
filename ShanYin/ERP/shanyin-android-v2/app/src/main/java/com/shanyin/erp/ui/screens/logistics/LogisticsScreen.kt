package com.shanyin.erp.ui.screens.logistics

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import com.shanyin.erp.domain.usecase.ExpressOrderSuggestion

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LogisticsScreen(
    viewModel: LogisticsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // 使用 snapshotFlow 强制触发 recompose，确保状态变化被 UI 观察到
    LaunchedEffect(uiState.logisticsList, uiState.refreshVersion) {
        // 当 logisticsList 或 refreshVersion 变化时，强制 recompose
    }

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
            FloatingActionButton(onClick = { viewModel.showCreateLogisticsDialog() }) {
                Icon(Icons.Default.Add, contentDescription = "新建物流")
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
                text = "物流管理",
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
                    text = { Text("全部") }
                )
                Tab(
                    selected = uiState.selectedTab == 1,
                    onClick = { viewModel.setSelectedTab(1) },
                    text = { Text("待发货") }
                )
                Tab(
                    selected = uiState.selectedTab == 2,
                    onClick = { viewModel.setSelectedTab(2) },
                    text = { Text("在途") }
                )
                Tab(
                    selected = uiState.selectedTab == 3,
                    onClick = { viewModel.setSelectedTab(3) },
                    text = { Text("签收") }
                )
                Tab(
                    selected = uiState.selectedTab == 4,
                    onClick = { viewModel.setSelectedTab(4) },
                    text = { Text("完成") }
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            when {
                uiState.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                viewModel.getFilteredLogistics().isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.LocalShipping,
                                contentDescription = null,
                                modifier = Modifier.size(64.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("暂无物流记录，点击 + 新建", style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
                else -> {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = PaddingValues(bottom = 80.dp)
                    ) {
                        items(uiState.logisticsList, key = { it.id }) { logistics ->
                            LogisticsCard(
                                logistics = logistics,
                                onClick = { viewModel.showLogisticsDetailDialog(logistics) }
                            )
                        }
                    }
                }
            }
        }
    }

    // Create Logistics Dialog
    if (uiState.showCreateLogisticsDialog) {
        CreateLogisticsDialog(
            virtualContracts = uiState.virtualContracts,
            existingLogistics = uiState.logisticsList,
            onDismiss = { viewModel.dismissCreateLogisticsDialog() },
            onConfirm = { vcId ->
                viewModel.createLogisticsRecord(vcId)
            }
        )
    }

    // Logistics Detail Dialog
    if (uiState.showLogisticsDetailDialog && uiState.selectedLogistics != null) {
        LogisticsDetailDialog(
            logistics = uiState.selectedLogistics!!,
            expressOrders = uiState.expressOrders.filter { it.logisticsId == uiState.selectedLogistics!!.id },
            skus = uiState.skus,
            points = uiState.points,
            onDismiss = { viewModel.dismissLogisticsDetailDialog() },
            onAddExpressOrder = { viewModel.showExpressOrderDialog(uiState.selectedLogistics!!.id) },
            onUpdateExpressStatus = { expressId, status ->
                viewModel.updateExpressOrderStatusAction(expressId, status)
            },
            onUpdateExpressTracking = { expressId, tracking ->
                viewModel.updateExpressOrderTrackingAction(expressId, tracking)
            },
            onDeleteExpress = { viewModel.deleteExpressOrderAction(it) },
            onDelete = { viewModel.deleteLogisticsRecord(uiState.selectedLogistics!!) },
            onConfirmInbound = { viewModel.showConfirmInboundDialog() },
            onViewVcDetails = { vcId ->
                viewModel.showVcElementsDialog(vcId)
            },
            onGenerateExpressOrders = { vcId ->
                val vc = uiState.virtualContracts.find { it.id == vcId }
                vc?.let { viewModel.generateExpressOrderSuggestions(it) }
            },
            onBulkProgressExpressOrders = { logisticsId, expressOrderIds, targetStatus ->
                viewModel.bulkProgressExpressOrdersAction(logisticsId, expressOrderIds, targetStatus)
            }
        )
    }

    // Confirm Inbound Dialog
    if (uiState.showConfirmInboundDialog && uiState.selectedLogistics != null) {
        ConfirmInboundDialog(
            logistics = uiState.selectedLogistics!!,
            onDismiss = { viewModel.dismissConfirmInboundDialog() },
            onConfirm = { snList ->
                viewModel.confirmInbound(uiState.selectedLogistics!!.id, snList)
                viewModel.dismissLogisticsDetailDialog()
            }
        )
    }

    // VC Elements Dialog
    if (uiState.showVcElementsDialog && uiState.selectedVc != null) {
        VCElementsDialog(
            vc = uiState.selectedVc!!,
            skus = uiState.skus,
            points = uiState.points,
            onDismiss = { viewModel.dismissVcElementsDialog() }
        )
    }

    // Express Order Suggestions Dialog
    if (uiState.showExpressOrderSuggestionsDialog) {
        ExpressOrderSuggestionsDialog(
            suggestions = uiState.expressOrderSuggestions,
            onDismiss = { viewModel.dismissExpressOrderSuggestionsDialog() },
            onUpdateTracking = { index, tracking ->
                viewModel.updateSuggestionTrackingNumber(index, tracking)
            },
            onConfirm = {
                uiState.selectedLogistics?.let { log ->
                    viewModel.confirmExpressOrderSuggestions(log.id)
                }
            }
        )
    }

    // Express Order Dialog
    if (uiState.showExpressOrderDialog && uiState.selectedLogistics != null) {
        CreateExpressOrderDialog(
            logisticsId = uiState.selectedLogistics!!.id,
            skus = uiState.skus,
            points = uiState.points,
            onDismiss = { viewModel.dismissExpressOrderDialog() },
            onConfirm = { trackingNumber, items, addressInfo ->
                viewModel.createExpressOrderRecord(
                    uiState.selectedLogistics!!.id,
                    trackingNumber,
                    items,
                    addressInfo
                )
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LogisticsCard(
    logistics: Logistics,
    onClick: () -> Unit
) {
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
                        text = "VC #${logistics.virtualContractId}",
                        style = MaterialTheme.typography.titleMedium
                    )
                    logistics.vcTypeName?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                LogisticsStatusBadge(status = logistics.status)
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                InfoChip(if (logistics.financeTriggered) "已触发财务" else "待触发财务")
                InfoChip(
                    if (logistics.expressOrders.isNotEmpty())
                        "快递单: ${logistics.expressOrders.size}"
                    else
                        "快递单: 0"
                )
            }
        }
    }
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreateLogisticsDialog(
    virtualContracts: List<VirtualContract>,
    existingLogistics: List<Logistics>,
    onDismiss: () -> Unit,
    onConfirm: (Long) -> Unit
) {
    var selectedVc by remember { mutableStateOf<VirtualContract?>(null) }
    var vcExpanded by remember { mutableStateOf(false) }

    // 检查选择的 VC 是否已有物流单
    val existingForVc = selectedVc?.let { vc ->
        existingLogistics.find { it.virtualContractId == vc.id }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建物流记录") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth().heightIn(max = 400.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // 如果已有物流单，显示警告
                if (existingForVc != null) {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = MaterialTheme.shapes.small
                    ) {
                        Text(
                            text = "该 VC 已存在物流单 #${existingForVc.id}（${existingForVc.status.displayName}），可直接在详情中添加快递单",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            modifier = Modifier.padding(12.dp)
                        )
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = vcExpanded,
                    onExpandedChange = { vcExpanded = !vcExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedVc?.let { "${it.type?.displayName} #${it.id}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("虚拟合同 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = vcExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = vcExpanded,
                        onDismissRequest = { vcExpanded = false }
                    ) {
                        virtualContracts.forEach { vc ->
                            // 标记已有物流单的 VC
                            val hasExisting = existingLogistics.any { it.virtualContractId == vc.id }
                            DropdownMenuItem(
                                text = {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text("${vc.type?.displayName} #${vc.id}")
                                        if (hasExisting) {
                                            Text(
                                                "已有物流",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = MaterialTheme.colorScheme.error
                                            )
                                        }
                                    }
                                },
                                onClick = {
                                    selectedVc = vc
                                    vcExpanded = false
                                }
                            )
                        }
                    }
                }

                Text(
                    text = "选择虚拟合同后，将创建对应的物流记录",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { selectedVc?.let { onConfirm(it.id) } },
                enabled = selectedVc != null && existingForVc == null
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
private fun LogisticsDetailDialog(
    logistics: Logistics,
    expressOrders: List<ExpressOrder>,
    skus: List<Sku>,
    points: List<Point>,
    onDismiss: () -> Unit,
    onAddExpressOrder: () -> Unit,
    onUpdateExpressStatus: (Long, ExpressStatus) -> Unit,
    onUpdateExpressTracking: (Long, String) -> Unit,
    onDeleteExpress: (ExpressOrder) -> Unit,
    onDelete: () -> Unit,
    onConfirmInbound: () -> Unit,
    onViewVcDetails: (Long) -> Unit,
    onGenerateExpressOrders: (Long) -> Unit,  // 传入 vcId 生成快递单建议
    onBulkProgressExpressOrders: (Long, List<Long>, ExpressStatus) -> Unit  // 传入 logisticsId, expressOrderIds, targetStatus
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var expressExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("物流 #${logistics.id}") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 500.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // VC 链接
                TextButton(
                    onClick = { onViewVcDetails(logistics.virtualContractId) },
                    contentPadding = PaddingValues(0.dp)
                ) {
                    Icon(Icons.Default.Link, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("查看标的详情 VC#${logistics.virtualContractId}", style = MaterialTheme.typography.bodySmall)
                }

                logistics.vcTypeName?.let { DetailRow("合同类型", it) }

                // Status display (read-only, auto-derived from ExpressOrders)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("物流状态", style = MaterialTheme.typography.bodyMedium)
                    LogisticsStatusBadge(status = logistics.status)
                }

                if (logistics.financeTriggered) {
                    DetailRow("财务", "已触发")
                }

                // Action buttons
                if (logistics.status == LogisticsStatus.SIGNED) {
                    Button(
                        onClick = onConfirmInbound,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("确认入库")
                    }
                }

                HorizontalDivider()

                // Express Orders section
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "快递单",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Row {
                        // 仅在物流未完成且没有快递单时显示"生成"按钮
                        if (expressOrders.isEmpty() && logistics.status != LogisticsStatus.COMPLETED && logistics.status != LogisticsStatus.SIGNED) {
                            TextButton(onClick = { onGenerateExpressOrders(logistics.virtualContractId) }) {
                                Icon(Icons.Default.AutoAwesome, contentDescription = null, modifier = Modifier.size(16.dp))
                                Text("生成")
                            }
                        }
                        TextButton(onClick = onAddExpressOrder) {
                            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                            Text("添加")
                        }
                    }
                }

                // 批量推进按钮 - 仅在物流未完成且所有快递单状态一致时显示
                if (expressOrders.isNotEmpty() && logistics.status != LogisticsStatus.COMPLETED) {
                    val statuses = expressOrders.map { it.status }.toSet()
                    if (statuses.size == 1) {
                        val currentStatus = statuses.first()
                        val targetStatus: ExpressStatus? = when (currentStatus) {
                            ExpressStatus.PENDING -> ExpressStatus.IN_TRANSIT
                            ExpressStatus.IN_TRANSIT -> ExpressStatus.SIGNED
                            ExpressStatus.SIGNED -> null  // 已签收，不能再推进
                            else -> null
                        }
                        targetStatus?.let { target ->
                            Button(
                                onClick = {
                                    onBulkProgressExpressOrders(
                                        logistics.id,
                                        expressOrders.map { it.id },
                                        target
                                    )
                                },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Icon(Icons.Default.FastForward, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("批量推进至: ${target.displayName}")
                            }
                        }
                    }
                }

                if (expressOrders.isEmpty()) {
                    Text(
                        "暂无快递单",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    // 最多显示2条，超出用滚动
                    val visibleOrders = if (expressExpanded) expressOrders else expressOrders.take(2)
                    visibleOrders.forEach { express ->
                        ExpressOrderItem(
                            expressOrder = express,
                            onUpdateStatus = { status -> onUpdateExpressStatus(express.id, status) },
                            onUpdateTracking = { tracking -> onUpdateExpressTracking(express.id, tracking) },
                            onDelete = { onDeleteExpress(express) }
                        )
                    }
                    if (expressOrders.size > 2) {
                        TextButton(
                            onClick = { expressExpanded = !expressExpanded },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(
                                if (expressExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                if (expressExpanded) "收起" else "展开全部 ${expressOrders.size} 个快递单",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }

                HorizontalDivider()

                OutlinedButton(
                    onClick = { showDeleteConfirm = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("删除物流")
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭")
            }
        },
        dismissButton = {}
    )

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("确认删除") },
            text = { Text("确定要删除此物流记录吗？所有关联的快递单也将被删除。") },
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
private fun ConfirmInboundDialog(
    logistics: Logistics,
    onDismiss: () -> Unit,
    onConfirm: (List<String>) -> Unit
) {
    var snInput by remember { mutableStateOf("") }
    val isEquipment = logistics.vcTypeName?.contains("设备") == true

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("确认入库") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth().heightIn(max = 300.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "物流 #${logistics.id}（${logistics.vcTypeName ?: ""}）",
                    style = MaterialTheme.typography.bodyMedium
                )

                if (isEquipment) {
                    Text(
                        text = "请输入设备序列号，每行一个：",
                        style = MaterialTheme.typography.bodySmall
                    )
                    OutlinedTextField(
                        value = snInput,
                        onValueChange = { snInput = it },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        maxLines = 10,
                        label = { Text("序列号（每行一个）") },
                        placeholder = { Text("SN001\nSN002\nSN003") }
                    )
                } else {
                    Text(
                        text = "物料入库无需序列号，确认后将直接更新库存。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val snList = if (isEquipment) {
                        snInput.lines().map { it.trim() }.filter { it.isNotBlank() }
                    } else {
                        emptyList()
                    }
                    onConfirm(snList)
                }
            ) {
                Text("确认入库")
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
private fun ExpressOrderItem(
    expressOrder: ExpressOrder,
    onUpdateStatus: (ExpressStatus) -> Unit,
    onUpdateTracking: (String) -> Unit,
    onDelete: () -> Unit
) {
    var statusExpanded by remember { mutableStateOf(false) }
    var editingTracking by remember { mutableStateOf(false) }
    var trackingInput by remember { mutableStateOf(expressOrder.trackingNumber ?: "") }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            // Row 1: 运单号 + 状态
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    if (editingTracking) {
                        OutlinedTextField(
                            value = trackingInput,
                            onValueChange = { trackingInput = it },
                            label = { Text("快递单号") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            textStyle = MaterialTheme.typography.bodySmall
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End
                        ) {
                            TextButton(onClick = { editingTracking = false }) {
                                Text("取消")
                            }
                            TextButton(onClick = {
                                onUpdateTracking(trackingInput)
                                editingTracking = false
                            }) {
                                Text("保存")
                            }
                        }
                    } else {
                        Row(
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = expressOrder.trackingNumber?.takeIf { it.isNotBlank() } ?: "— 无运单号 —",
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (expressOrder.trackingNumber.isNullOrBlank())
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                else MaterialTheme.colorScheme.onSurface
                            )
                            IconButton(
                                onClick = {
                                    trackingInput = expressOrder.trackingNumber ?: ""
                                    editingTracking = true
                                },
                                modifier = Modifier.size(24.dp)
                            ) {
                                Icon(
                                    Icons.Default.Edit,
                                    contentDescription = "修改快递单号",
                                    modifier = Modifier.size(16.dp),
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                    // Row 2: 联系人 + 电话
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        val contactName = expressOrder.addressInfo.receivingContact
                        val phone = expressOrder.addressInfo.receivingPhone
                        if (!contactName.isNullOrBlank()) {
                            Text(
                                text = contactName,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                        if (!phone.isNullOrBlank()) {
                            Text(
                                text = phone,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
                ExposedDropdownMenuBox(
                    expanded = statusExpanded,
                    onExpandedChange = { statusExpanded = !statusExpanded },
                    modifier = Modifier.width(120.dp)
                ) {
                    OutlinedTextField(
                        value = expressOrder.status.displayName,
                        onValueChange = {},
                        readOnly = true,
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = statusExpanded) },
                        modifier = Modifier.menuAnchor(),
                        singleLine = true,
                        textStyle = MaterialTheme.typography.labelSmall
                    )
                    ExposedDropdownMenu(
                        expanded = statusExpanded,
                        onDismissRequest = { statusExpanded = false }
                    ) {
                        ExpressStatus.entries.forEach { status ->
                            DropdownMenuItem(
                                text = { Text(status.displayName) },
                                onClick = {
                                    onUpdateStatus(status)
                                    statusExpanded = false
                                }
                            )
                        }
                    }
                }
            }

            // Row 3: 完整地址（省市区+详细地址）
            val addrInfo = expressOrder.addressInfo
            val fullAddress = listOfNotNull(
                addrInfo.receivingProvince,
                addrInfo.receivingCity,
                addrInfo.receivingDistrict,
                addrInfo.receivingAddress
            ).joinToString("")
            if (fullAddress.isNotBlank()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = fullAddress,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2
                )
            }

            // Row 4: 物品明细
            if (expressOrder.items.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Spacer(modifier = Modifier.height(6.dp))
                expressOrder.items.forEach { item ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = item.skuName?.ifBlank { "商品" } ?: "商品",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "×${item.quantity}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            // Row 5: 时间戳 + 删除
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = formatTimestamp(expressOrder.timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline
                )
                IconButton(onClick = onDelete) {
                    Icon(
                        Icons.Default.Delete,
                        contentDescription = "删除",
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }
    }
}

private fun formatTimestamp(ts: Long): String {
    val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault())
    return sdf.format(java.util.Date(ts))
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreateExpressOrderDialog(
    logisticsId: Long,
    skus: List<Sku>,
    points: List<Point>,
    onDismiss: () -> Unit,
    onConfirm: (String?, List<ExpressItem>, AddressInfo) -> Unit
) {
    var trackingNumber by remember { mutableStateOf("") }

    // 收货方状态
    var receivingPoint by remember { mutableStateOf<Point?>(null) }
    var receivingPointExpanded by remember { mutableStateOf(false) }

    // 发货方状态
    var shippingPoint by remember { mutableStateOf<Point?>(null) }
    var shippingPointExpanded by remember { mutableStateOf(false) }

    var selectedSkus by remember { mutableStateOf(listOf<Pair<Sku, Int>>()) }
    var showSkuSelector by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加快递单") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 500.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = trackingNumber,
                    onValueChange = { trackingNumber = it },
                    label = { Text("运单号") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // ========== 收货方信息 ==========
                Text(
                    "收货方信息",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )

                // 收货点位选择
                ExposedDropdownMenuBox(
                    expanded = receivingPointExpanded,
                    onExpandedChange = { receivingPointExpanded = !receivingPointExpanded }
                ) {
                    OutlinedTextField(
                        value = receivingPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("收货点位") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = receivingPointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = receivingPointExpanded,
                        onDismissRequest = { receivingPointExpanded = false }
                    ) {
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text("${point.name} (${point.type?.displayName ?: "点位"})") },
                                onClick = {
                                    receivingPoint = point
                                    receivingPointExpanded = false
                                }
                            )
                        }
                    }
                }

                // 收货地址显示
                if (receivingPoint != null) {
                    val receivingAddr = receivingPoint?.receivingAddress ?: receivingPoint?.address
                    if (!receivingAddr.isNullOrBlank()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Start
                        ) {
                            Text(
                                text = "收货地址: ",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = receivingAddr,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }

                HorizontalDivider()

                // ========== 发货方信息 ==========
                Text(
                    "发货方信息",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )

                // 发货点位选择
                ExposedDropdownMenuBox(
                    expanded = shippingPointExpanded,
                    onExpandedChange = { shippingPointExpanded = !shippingPointExpanded }
                ) {
                    OutlinedTextField(
                        value = shippingPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("发货点位") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = shippingPointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = shippingPointExpanded,
                        onDismissRequest = { shippingPointExpanded = false }
                    ) {
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text("${point.name} (${point.type?.displayName ?: "点位"})") },
                                onClick = {
                                    shippingPoint = point
                                    shippingPointExpanded = false
                                }
                            )
                        }
                    }
                }

                // 发货地址显示
                if (shippingPoint != null) {
                    val shippingAddr = shippingPoint?.receivingAddress ?: shippingPoint?.address
                    if (!shippingAddr.isNullOrBlank()) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Start
                        ) {
                            Text(
                                text = "发货地址: ",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = shippingAddr,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }

                HorizontalDivider()

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "SKU物品",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    TextButton(onClick = { showSkuSelector = true }) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                        Text("添加")
                    }
                }

                selectedSkus.forEachIndexed { index, (sku, qty) ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("${sku.name}: $qty 件", style = MaterialTheme.typography.bodySmall)
                        IconButton(onClick = {
                            selectedSkus = selectedSkus.toMutableList().also { it.removeAt(index) }
                        }) {
                            Icon(Icons.Default.Close, contentDescription = "移除", modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val items = selectedSkus.map { (sku, qty) ->
                        ExpressItem(skuId = sku.id, skuName = sku.name, quantity = qty)
                    }
                    val addressInfo = AddressInfo(
                        // 收货方信息
                        receivingPointId = receivingPoint?.id,
                        receivingPointName = receivingPoint?.name,
                        receivingAddress = receivingPoint?.receivingAddress ?: receivingPoint?.address,
                        // 发货方信息
                        shippingPointId = shippingPoint?.id,
                        shippingPointName = shippingPoint?.name,
                        shippingAddress = shippingPoint?.receivingAddress ?: shippingPoint?.address
                    )
                    onConfirm(trackingNumber.takeIf { it.isNotBlank() }, items, addressInfo)
                }
            ) {
                Text("添加")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )

    if (showSkuSelector) {
        SkuSelectorDialog(
            skus = skus,
            onDismiss = { showSkuSelector = false },
            onSelect = { sku, qty ->
                selectedSkus = selectedSkus + (sku to qty)
                showSkuSelector = false
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SkuSelectorDialog(
    skus: List<Sku>,
    onDismiss: () -> Unit,
    onSelect: (Sku, Int) -> Unit
) {
    var selectedSku by remember { mutableStateOf<Sku?>(null) }
    var quantity by remember { mutableStateOf("1") }
    var skuExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("选择SKU") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                ExposedDropdownMenuBox(
                    expanded = skuExpanded,
                    onExpandedChange = { skuExpanded = !skuExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedSku?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("SKU") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = skuExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = skuExpanded,
                        onDismissRequest = { skuExpanded = false }
                    ) {
                        skus.forEach { sku ->
                            DropdownMenuItem(
                                text = { Text("${sku.name} - ${sku.model ?: ""}") },
                                onClick = {
                                    selectedSku = sku
                                    skuExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = quantity,
                    onValueChange = { quantity = it.filter { c -> c.isDigit() } },
                    label = { Text("数量") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    selectedSku?.let {
                        onSelect(it, quantity.toIntOrNull() ?: 1)
                    }
                },
                enabled = selectedSku != null && quantity.isNotBlank()
            ) {
                Text("添加")
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
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun VCElementsDialog(
    vc: VirtualContract,
    skus: List<Sku>,
    points: List<Point>,
    onDismiss: () -> Unit
) {
    // 通过 ID 查找名称的辅助函数
    fun findSkuName(skuId: Long): String {
        return skus.find { it.id == skuId }?.name ?: ""
    }

    fun findPointName(pointId: Long?): String? {
        return pointId?.let { id -> points.find { it.id == id }?.name }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("标的详情") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 500.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // VC描述
                vc.description?.let {
                    Text(it, style = MaterialTheme.typography.bodyMedium)
                }

                HorizontalDivider()

                // 标的物状态
                Text("标的物状态", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                DetailRow("状态", vc.subjectStatus.displayName)

                HorizontalDivider()

                // 标的物明细
                Text("标的物明细", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                vc.elements.forEach { element ->
                    // 补全名称
                    val displaySkuName = element.skuName.ifBlank { findSkuName(element.skuId) }
                    val shippingPointName = findPointName(element.shippingPointId)
                    val receivingPointName = findPointName(element.receivingPointId)

                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(8.dp)) {
                            Text(displaySkuName.ifBlank { "SKU#${element.skuId}" }, style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "${element.quantity} x ¥${element.unitPrice} = ¥${element.subtotal}",
                                style = MaterialTheme.typography.bodySmall
                            )
                            // 显示发货/收货点位
                            if (shippingPointName != null) {
                                Text(
                                    "发货点: $shippingPointName",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.secondary
                                )
                            }
                            if (receivingPointName != null) {
                                Text(
                                    "收货点: $receivingPointName",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                            // 根据元素类型显示不同信息
                            when (element) {
                                is MaterialSupplyElement -> {
                                    element.sourceWarehouse?.let {
                                        Text(
                                            "发货仓库: $it",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.secondary
                                        )
                                    }
                                }
                                is ReturnElement -> {
                                    element.receivingWarehouse?.let {
                                        Text(
                                            "收货仓库: $it",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                    }
                                }
                                is AllocationElement -> {
                                    element.equipmentSn?.let {
                                        Text(
                                            "设备SN: $it",
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                    }
                                }
                                is SkusFormatElement -> {
                                    // 设备采购/库存采购/物料采购：显示押金
                                    if (element.deposit > 0) {
                                        Text(
                                            "押金: ¥${element.deposit}/台",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.tertiary
                                        )
                                    }
                                }
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
}

// ==================== 快递单建议对话框 ====================

@Composable
private fun ExpressOrderSuggestionsDialog(
    suggestions: List<ExpressOrderSuggestion>,
    onDismiss: () -> Unit,
    onUpdateTracking: (Int, String) -> Unit,
    onConfirm: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("生成快递单") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 500.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "根据标的物生成 ${suggestions.size} 个快递单建议：",
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
    val addressInfo = suggestion.addressInfo

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

            // 收货信息
            if (addressInfo.receivingPointName != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "收货点:",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = addressInfo.receivingPointName,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            val receivingAddr = addressInfo.receivingAddress
            if (!receivingAddr.isNullOrBlank()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "收货地址:",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = receivingAddr,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f).padding(start = 8.dp)
                    )
                }
            }

            // 发货信息
            if (addressInfo.shippingPointName != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "发货点:",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = addressInfo.shippingPointName,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }

            // 物品明细
            if (suggestion.items.isNotEmpty()) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Text(
                    text = "物品:",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                suggestion.items.forEach { item ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = item.skuName,
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            text = "×${item.quantity}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }
        }
    }
}
