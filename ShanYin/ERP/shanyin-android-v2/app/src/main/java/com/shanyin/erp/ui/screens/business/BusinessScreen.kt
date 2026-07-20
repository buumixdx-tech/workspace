package com.shanyin.erp.ui.screens.business

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.shanyin.erp.domain.model.Business
import com.shanyin.erp.domain.model.BusinessDetails
import com.shanyin.erp.domain.model.BusinessPaymentTerms
import com.shanyin.erp.domain.model.BusinessStatus
import com.shanyin.erp.domain.model.ChannelCustomer
import com.shanyin.erp.domain.model.Sku
import com.shanyin.erp.domain.model.SkuPriceItem
import com.shanyin.erp.domain.model.TimeRule

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BusinessScreen(
    viewModel: BusinessListViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var selectedStatuses by remember { mutableStateOf(emptySet<BusinessStatus>()) }

    val filteredBusinesses = if (selectedStatuses.isEmpty()) {
        uiState.businesses
    } else {
        uiState.businesses.filter { it.status in selectedStatuses }
    }

    fun toggleStatus(status: BusinessStatus) {
        selectedStatuses = if (status in selectedStatuses) {
            selectedStatuses - status
        } else {
            selectedStatuses + status
        }
    }

    fun toggleGroup(group: Set<BusinessStatus>) {
        selectedStatuses = if (group.all { it in selectedStatuses }) {
            selectedStatuses - group
        } else {
            selectedStatuses + group
        }
    }

    fun clearSelection() {
        selectedStatuses = emptySet()
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
            FloatingActionButton(
                onClick = { viewModel.showCreateDialog() }
            ) {
                Icon(Icons.Default.Add, contentDescription = "新建业务")
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
                text = "业务管理",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.padding(vertical = 16.dp)
            )

            // Status filter chips
            StatusFilterChips(
                selectedStatuses = selectedStatuses,
                onToggle = { toggleStatus(it) },
                onToggleGroup = { toggleGroup(it) },
                onClear = { clearSelection() }
            )

            Spacer(modifier = Modifier.height(8.dp))

            when {
                uiState.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                filteredBusinesses.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.Business,
                                contentDescription = null,
                                modifier = Modifier.size(64.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("暂无业务，点击 + 新建", style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
                else -> {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = PaddingValues(bottom = 80.dp)
                    ) {
                        items(filteredBusinesses, key = { it.id }) { business ->
                            BusinessCard(
                                business = business,
                                customerName = uiState.customers.find { it.id == business.customerId }?.name,
                                onClick = { viewModel.showDetailDialog(business) }
                            )
                        }
                    }
                }
            }
        }
    }

    if (uiState.showCreateDialog) {
        CreateBusinessDialog(
            customers = uiState.customers,
            onDismiss = { viewModel.dismissCreateDialog() },
            onConfirm = { customerId, notes ->
                viewModel.createBusiness(customerId, notes)
            }
        )
    }

    if (uiState.showDetailDialog && uiState.selectedBusiness != null) {
        BusinessDetailDialog(
            business = uiState.selectedBusiness!!,
            customerName = uiState.customers.find { it.id == uiState.selectedBusiness!!.customerId }?.name,
            timeRules = uiState.selectedBusinessTimeRules,
            skus = uiState.skus,
            onDismiss = { viewModel.dismissDetailDialog() },
            onAdvance = { reason -> viewModel.advanceStage(uiState.selectedBusiness!!.id, reason) },
            onSuspend = { viewModel.suspend(uiState.selectedBusiness!!.id) },
            onTerminate = { viewModel.terminate(uiState.selectedBusiness!!.id) },
            onReactivate = { viewModel.reactivate(uiState.selectedBusiness!!.id) }
        )
    }
}

private val DEV_STATUSES = setOf(
    BusinessStatus.INITIAL_CONTACT,
    BusinessStatus.EVALUATION,
    BusinessStatus.CUSTOMER_FEEDBACK,
    BusinessStatus.COOPERATION_START
)
private val STOP_STATUSES = setOf(
    BusinessStatus.SUSPENDED,
    BusinessStatus.COMPLETED,
    BusinessStatus.TERMINATED
)

// 展示顺序
private val CHIP_ORDER = listOf(
    null, // 全部
    BusinessStatus.BUSINESS_PROGRESS,
    "DEV_GROUP", // 业务开发
    "STOP_GROUP", // 业务停止
    BusinessStatus.INITIAL_CONTACT,
    BusinessStatus.EVALUATION,
    BusinessStatus.CUSTOMER_FEEDBACK,
    BusinessStatus.COOPERATION_START,
    BusinessStatus.SUSPENDED,
    BusinessStatus.COMPLETED,
    BusinessStatus.TERMINATED
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StatusFilterChips(
    selectedStatuses: Set<BusinessStatus>,
    onToggle: (BusinessStatus) -> Unit,
    onToggleGroup: (Set<BusinessStatus>) -> Unit,
    onClear: () -> Unit
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(CHIP_ORDER) { item ->
            when (item) {
                null -> {
                    FilterChip(
                        selected = selectedStatuses.isEmpty(),
                        onClick = { onClear() },
                        label = { Text("全部") }
                    )
                }
                "DEV_GROUP" -> {
                    val allSelected = DEV_STATUSES.all { it in selectedStatuses }
                    FilterChip(
                        selected = allSelected && selectedStatuses.containsAll(DEV_STATUSES),
                        onClick = {
                            if (allSelected) {
                                onToggleGroup(DEV_STATUSES) // toggle off all
                            } else {
                                onToggleGroup(DEV_STATUSES) // toggle on all
                            }
                        },
                        label = { Text("业务开发") }
                    )
                }
                "STOP_GROUP" -> {
                    val allSelected = STOP_STATUSES.all { it in selectedStatuses }
                    FilterChip(
                        selected = allSelected && selectedStatuses.containsAll(STOP_STATUSES),
                        onClick = {
                            if (allSelected) {
                                onToggleGroup(STOP_STATUSES)
                            } else {
                                onToggleGroup(STOP_STATUSES)
                            }
                        },
                        label = { Text("业务停止") }
                    )
                }
                else -> {
                    @Suppress("UNCHECKED_CAST")
                    val status = item as BusinessStatus
                    FilterChip(
                        selected = status in selectedStatuses,
                        onClick = { onToggle(status) },
                        label = { Text(status.displayName) }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BusinessCard(
    business: Business,
    customerName: String?,
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
                        text = "业务 #${business.id}",
                        style = MaterialTheme.typography.titleMedium
                    )
                    customerName?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                StatusBadge(status = business.status ?: BusinessStatus.INITIAL_CONTACT)
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Stage progress indicator
            StageProgressIndicator(currentStatus = business.status ?: BusinessStatus.INITIAL_CONTACT)

            business.details.notes?.let { notes ->
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = notes,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun StatusBadge(status: BusinessStatus) {
    val (backgroundColor, contentColor) = when (status) {
        BusinessStatus.INITIAL_CONTACT -> Color(0xFFE3F2FD) to Color(0xFF1976D2)
        BusinessStatus.EVALUATION -> Color(0xFFFFF3E0) to Color(0xFFEF6C00)
        BusinessStatus.CUSTOMER_FEEDBACK -> Color(0xFFF3E5F5) to Color(0xFF7B1FA2)
        BusinessStatus.COOPERATION_START -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
        BusinessStatus.BUSINESS_PROGRESS -> Color(0xFF4CAF50) to Color.White
        BusinessStatus.SUSPENDED -> Color(0xFFFFEBEE) to Color(0xFFD32F2F)
        BusinessStatus.COMPLETED -> Color(0xFFB2DFDB) to Color(0xFF00796B)
        BusinessStatus.TERMINATED -> Color(0xFFECEFF1) to Color(0xFF607D8B)
    }

    Surface(
        color = backgroundColor,
        shape = MaterialTheme.shapes.small
    ) {
        Text(
            text = status.displayName,
            style = MaterialTheme.typography.labelMedium,
            color = contentColor,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

@Composable
private fun StageProgressIndicator(currentStatus: BusinessStatus) {
    val stages = listOf(
        BusinessStatus.INITIAL_CONTACT,
        BusinessStatus.EVALUATION,
        BusinessStatus.CUSTOMER_FEEDBACK,
        BusinessStatus.COOPERATION_START,
        BusinessStatus.BUSINESS_PROGRESS
    )

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        stages.forEachIndexed { index, stage ->
            val isActive = currentStatus.order >= stage.order
            val isCurrent = currentStatus == stage

            Column(
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Box(
                    modifier = Modifier
                        .size(if (isCurrent) 12.dp else 8.dp)
                        .background(
                            color = when {
                                isCurrent -> MaterialTheme.colorScheme.primary
                                isActive -> MaterialTheme.colorScheme.primary.copy(alpha = 0.5f)
                                else -> MaterialTheme.colorScheme.outline
                            },
                            shape = MaterialTheme.shapes.extraSmall
                        )
                )
                if (index < stages.size - 1) {
                    Box(
                        modifier = Modifier
                            .width(24.dp)
                            .height(2.dp)
                            .background(
                                if (currentStatus.order > stage.order)
                                    MaterialTheme.colorScheme.primary
                                else
                                    MaterialTheme.colorScheme.outline
                            )
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreateBusinessDialog(
    customers: List<ChannelCustomer>,
    onDismiss: () -> Unit,
    onConfirm: (Long?, String?) -> Unit
) {
    var selectedCustomer by remember { mutableStateOf<ChannelCustomer?>(null) }
    var notes by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建业务") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ExposedDropdownMenuBox(
                    expanded = expanded,
                    onExpandedChange = { expanded = !expanded }
                ) {
                    OutlinedTextField(
                        value = selectedCustomer?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("客户") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = expanded,
                        onDismissRequest = { expanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无客户") },
                            onClick = {
                                selectedCustomer = null
                                expanded = false
                            }
                        )
                        customers.forEach { customer ->
                            DropdownMenuItem(
                                text = { Text(customer.name) },
                                onClick = {
                                    selectedCustomer = customer
                                    expanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("备注") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 2,
                    maxLines = 4
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(selectedCustomer?.id, notes.ifBlank { null }) }) {
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

@Composable
private fun BusinessDetailDialog(
    business: Business,
    customerName: String?,
    timeRules: List<TimeRule>,
    skus: List<Sku>,
    onDismiss: () -> Unit,
    onAdvance: (String?) -> Unit,
    onSuspend: () -> Unit,
    onTerminate: () -> Unit,
    onReactivate: () -> Unit
) {
    var showSuspendConfirm by remember { mutableStateOf(false) }
    var showTerminateConfirm by remember { mutableStateOf(false) }
    var showReactivateConfirm by remember { mutableStateOf(false) }
    var showAdvanceConfirm by remember { mutableStateOf(false) }
    var advanceReason by remember { mutableStateOf("") }
    var showFullTimeline by remember { mutableStateOf(false) }
    var showFullRules by remember { mutableStateOf(false) }
    var showFullSku by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(
            when {
                showFullTimeline -> "完整时间线"
                showFullRules -> "完整规则"
                showFullSku -> "完整SKU定价"
                else -> "业务详情 #${business.id}"
            }
        ) },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (showFullTimeline) {
                    // ===== 完整时间线视图 =====
                    if (business.details.history.isEmpty()) {
                        Text("暂无时间线记录", style = MaterialTheme.typography.bodyMedium)
                    } else {
                        business.details.history.forEach { transition ->
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
                                    if (transition != business.details.history.last()) {
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
                                        text = "${transition.from?.displayName ?: "启动"} → ${transition.to?.displayName ?: "?"}",
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    Text(
                                        text = formatTimestamp(transition.time),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    transition.comment?.takeIf { it.isNotBlank() }?.let {
                                        Text(
                                            text = it,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
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
                } else if (showFullRules) {
                    // ===== 完整规则视图（仅时间规则） =====
                    if (timeRules.isEmpty()) {
                        Text("暂无规则信息", style = MaterialTheme.typography.bodyMedium)
                    } else {
                        timeRules.forEach { rule ->
                            Text(
                                text = buildRuleExpression(rule),
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = { showFullRules = false },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("返回详情")
                    }
                } else if (showFullSku) {
                    // ===== 完整SKU定价视图 =====
                    if (business.details.pricing.isEmpty()) {
                        Text("暂无SKU定价", style = MaterialTheme.typography.bodyMedium)
                    } else {
                        val equipmentItems = business.details.pricing.filter { (name, _) ->
                            skus.find { it.name == name }?.typeLevel1?.displayName == "设备"
                        }
                        val materialItems = business.details.pricing.filter { (name, _) ->
                            skus.find { it.name == name }?.typeLevel1?.displayName == "物料"
                        }

                        LazyColumn(
                            modifier = Modifier.heightIn(max = 320.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            if (equipmentItems.isNotEmpty()) {
                                item {
                                    Text("设备类", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                                }
                                items(equipmentItems.toList()) { (name, item) ->
                                    SkuPriceRow(name, item)
                                }
                                if (materialItems.isNotEmpty()) {
                                    item { HorizontalDivider() }
                                }
                            }
                            if (materialItems.isNotEmpty()) {
                                item {
                                    Text("物料类", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                                }
                                items(materialItems.toList()) { (name, item) ->
                                    SkuPriceRow(name, item)
                                }
                            }
                        }
                    }

                    OutlinedButton(
                        onClick = { showFullSku = false },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("返回详情")
                    }
                } else {
                    // ===== 详情视图 =====
                    // 4-row fixed header
                    DetailRow("客户名称", customerName ?: "未指定")
                    DetailRow("创建时间", formatDate(business.timestamp))
                    if (business.details.history.isNotEmpty()) {
                        val latest = business.details.history.last()
                        DetailRow("业务状态", business.status?.displayName ?: "未知")
                        DetailRow("更新时间", formatDate(latest.time))
                    } else {
                        DetailRow("业务状态", business.status?.displayName ?: "未知")
                    }

                    // Notes
                    business.details.notes?.let {
                        DetailRow("备注", it)
                    }

                    // 查看完整时间线 button
                    if (business.details.history.isNotEmpty()) {
                        TextButton(
                            onClick = { showFullTimeline = true },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("查看完整时间线", style = MaterialTheme.typography.bodyMedium)
                        }
                    }

                    // Payment terms
                    business.details.paymentTerms?.let { pt ->
                        HorizontalDivider()
                        Text(
                            text = "商务条款",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary
                        )
                        DetailRow("预付比例", "${(pt.prepaymentRatio * 100).toInt()}%")
                        DetailRow("账期", "${pt.balancePeriod}天")
                        pt.dayRule?.let { DetailRow("日期规则", it) }
                        pt.startTrigger?.let { DetailRow("起算触发", it) }
                        TextButton(
                            onClick = { showFullRules = true },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("查看完整规则", style = MaterialTheme.typography.bodyMedium)
                        }
                    }

                    // SKU pricing
                    if (business.details.pricing.isNotEmpty()) {
                        HorizontalDivider()
                        Text(
                            text = "SKU定价",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary
                        )
                        val equipmentCount = business.details.pricing.count { (name, _) ->
                            skus.find { it.name == name }?.typeLevel1?.displayName == "设备"
                        }
                        val materialCount = business.details.pricing.count { (name, _) ->
                            skus.find { it.name == name }?.typeLevel1?.displayName == "物料"
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            if (equipmentCount > 0) {
                                Text("设备 sku $equipmentCount 条", style = MaterialTheme.typography.bodySmall)
                            }
                            if (materialCount > 0) {
                                Text("物料 sku $materialCount 条", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        TextButton(
                            onClick = { showFullSku = true },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("查看详情", style = MaterialTheme.typography.bodyMedium)
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Action buttons
                    if (business.status?.let {
                        it != BusinessStatus.BUSINESS_PROGRESS && BusinessStatus.getNext(it) != null
                    } == true) {
                        Button(
                            onClick = { showAdvanceConfirm = true },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(48.dp)
                        ) {
                            Text("推进")
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        if (business.status?.let { BusinessStatus.canSuspend(it) } == true) {
                            OutlinedButton(
                                onClick = { showSuspendConfirm = true },
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("暂停")
                            }
                        }

                        if (business.status?.let { BusinessStatus.canTerminate(it) } == true) {
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

                        if (business.status?.let { BusinessStatus.canReactivate(it) } == true) {
                            Button(
                                onClick = { showReactivateConfirm = true },
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("激活")
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

    if (showSuspendConfirm) {
        AlertDialog(
            onDismissRequest = { showSuspendConfirm = false },
            title = { Text("确认暂停") },
            text = { Text("确定要暂停此业务吗？暂停后可重新激活。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showSuspendConfirm = false
                        onSuspend()
                        onDismiss()
                    }
                ) {
                    Text("暂停")
                }
            },
            dismissButton = {
                TextButton(onClick = { showSuspendConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }

    if (showTerminateConfirm) {
        AlertDialog(
            onDismissRequest = { showTerminateConfirm = false },
            title = { Text("确认终止") },
            text = { Text("确定要终止此业务吗？终止后不可恢复，请谨慎操作。") },
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
                    Text("终止")
                }
            },
            dismissButton = {
                TextButton(onClick = { showTerminateConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }

    if (showReactivateConfirm) {
        AlertDialog(
            onDismissRequest = { showReactivateConfirm = false },
            title = { Text("确认激活") },
            text = { Text("确定要重新激活此业务吗？业务将回到暂停前的状态。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showReactivateConfirm = false
                        onReactivate()
                        onDismiss()
                    }
                ) {
                    Text("激活")
                }
            },
            dismissButton = {
                TextButton(onClick = { showReactivateConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }

    if (showAdvanceConfirm) {
        AlertDialog(
            onDismissRequest = {
                showAdvanceConfirm = false
                advanceReason = ""
            },
            title = { Text("确认推进") },
            text = {
                Column {
                    val nextStatus = business.status?.let { BusinessStatus.getNext(it) }
                    Text("确定要将业务推进到「${nextStatus?.displayName ?: "下一阶段"}」吗？")
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedTextField(
                        value = advanceReason,
                        onValueChange = { advanceReason = it },
                        label = { Text("备注（选填）") },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 3
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showAdvanceConfirm = false
                        onAdvance(advanceReason.takeIf { it.isNotBlank() })
                        advanceReason = ""
                        onDismiss()
                    }
                ) {
                    Text("确认推进")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showAdvanceConfirm = false
                        advanceReason = ""
                    }
                ) {
                    Text("取消")
                }
            }
        )
    }

}



private fun buildRuleExpression(rule: TimeRule): String {
    val trigger = rule.triggerEvent?.displayName ?: "触发"
    val target = rule.targetEvent.displayName
    val tge = rule.tgeParam1?.takeIf { it.isNotBlank() } ?: ""
    val tae = rule.taeParam1?.takeIf { it.isNotBlank() } ?: ""
    val offset = rule.offset
    val unit = rule.unit?.displayName ?: ""
    val direction = rule.direction

    val triggerFull = if (tge.isNotBlank()) "${tge}${trigger}" else trigger
    val targetFull = if (tae.isNotBlank()) "${tae}${target}" else target

    return if (direction?.name == "BEFORE") {
        // 前X天：目标在前，触发在后
        if (offset != null && offset > 0) {
            "${targetFull}前${offset}${unit}，${triggerFull}"
        } else {
            "${targetFull}，${triggerFull}"
        }
    } else {
        // 后X天：触发在前，目标在后
        if (offset != null && offset > 0) {
            "${triggerFull}后${offset}${unit}，${targetFull}"
        } else {
            "${triggerFull}，${targetFull}"
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
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

private fun formatTimestamp(timestamp: Long): String {
    val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault())
    return sdf.format(java.util.Date(timestamp))
}

private fun formatDate(timestamp: Long): String {
    val sdf = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault())
    return sdf.format(java.util.Date(timestamp))
}

@Composable
private fun SkuPriceRow(name: String, item: SkuPriceItem) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text = name, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        Text(
            text = buildString {
                if (item.price > 0) append("¥${item.price}")
                if (item.deposit > 0) append(" | 押金¥${item.deposit}")
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
