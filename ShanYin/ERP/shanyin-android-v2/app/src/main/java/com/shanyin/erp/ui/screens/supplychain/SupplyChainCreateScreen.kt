package com.shanyin.erp.ui.screens.supplychain

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.shanyin.erp.domain.model.SkuType
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.usecase.*

/**
 * 供应链创建全屏表单
 * 包含：供应商选择 + 类型 + SKU定价动态表格 + 结算条款
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SupplyChainCreateScreen(
    navController: NavController,
    viewModel: SupplyChainListViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // Form state - local to this screen
    var selectedSupplier by remember { mutableStateOf<Supplier?>(null) }
    var selectedType by remember { mutableStateOf(SupplyChainType.MATERIAL) }
    var prepaymentPercent by remember { mutableStateOf("30") }
    var paymentDays by remember { mutableStateOf("30") }
    var skuItems by remember { mutableStateOf(listOf<SkuPricingDraft>()) }
    var supplierExpanded by remember { mutableStateOf(false) }
    var typeExpanded by remember { mutableStateOf(false) }
    var contractNumber by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }

    // Filter SKUs by selected type
    val filteredSkus = uiState.skus.filter { sku ->
        when (selectedType) {
            SupplyChainType.MATERIAL -> sku.typeLevel1 == SkuType.MATERIAL
            SupplyChainType.EQUIPMENT -> sku.typeLevel1 == SkuType.EQUIPMENT
        }
    }

    // Determine if SKU selector should be enabled
    val canAddSku = selectedSupplier != null && filteredSkus.isNotEmpty()

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
            isSubmitting = false
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("新建供应链") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    TextButton(
                        onClick = {
                            selectedSupplier?.let { supplier ->
                                isSubmitting = true
                                val items = skuItems.mapNotNull { draft ->
                                    if (draft.skuId != null && draft.price > 0) {
                                        SupplyChainItem(
                                            supplyChainId = 0,
                                            skuId = draft.skuId,
                                            skuName = draft.skuName,
                                            price = draft.price,
                                            deposit = 0.0,
                                            isFloating = draft.isFloating
                                        )
                                    } else null
                                }
                                viewModel.create(
                                    supplierId = supplier.id,
                                    supplierName = supplier.name,
                                    type = selectedType,
                                    items = items,
                                    prepaymentPercent = prepaymentPercent.toDoubleOrNull() ?: 30.0,
                                    paymentDays = paymentDays.toIntOrNull() ?: 30
                                )
                                navController.popBackStack()
                            }
                        },
                        enabled = selectedSupplier != null && !isSubmitting
                    ) {
                        Text("保存")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            // Section: Supplier & Type
            item {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "基础信息",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }

            // Supplier selector
            item {
                ExposedDropdownMenuBox(
                    expanded = supplierExpanded,
                    onExpandedChange = { supplierExpanded = !supplierExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedSupplier?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("供应商 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = supplierExpanded) },
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth(),
                        isError = selectedSupplier == null
                    )
                    ExposedDropdownMenu(
                        expanded = supplierExpanded,
                        onDismissRequest = { supplierExpanded = false }
                    ) {
                        if (uiState.suppliers.isEmpty()) {
                            DropdownMenuItem(
                                text = { Text("无可用供应商，请先在主数据中添加") },
                                onClick = { supplierExpanded = false },
                                enabled = false
                            )
                        }
                        uiState.suppliers.forEach { supplier ->
                            DropdownMenuItem(
                                text = { Text(supplier.name) },
                                onClick = {
                                    selectedSupplier = supplier
                                    supplierExpanded = false
                                }
                            )
                        }
                    }
                }
            }

            // Type selector
            item {
                Column {
                    Text(
                        text = "协议类型 *",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .selectableGroup(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        SupplyChainType.entries.forEach { type ->
                            Row(
                                modifier = Modifier
                                    .selectable(
                                        selected = selectedType == type,
                                        onClick = {
                                            selectedType = type
                                            // Clear SKU items when type changes
                                            skuItems = emptyList()
                                        },
                                        role = Role.RadioButton
                                    )
                                    .padding(vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                RadioButton(
                                    selected = selectedType == type,
                                    onClick = null
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(type.displayName)
                            }
                        }
                    }
                }
            }

            // Contract number (optional)
            item {
                OutlinedTextField(
                    value = contractNumber,
                    onValueChange = { contractNumber = it },
                    label = { Text("合同编号（选填）") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }

            // Section: Settlement Terms
            item {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "结算条款",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }

            item {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedTextField(
                        value = prepaymentPercent,
                        onValueChange = { prepaymentPercent = it.filter { c -> c.isDigit() } },
                        label = { Text("预付%") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        suffix = { Text("%") }
                    )
                    OutlinedTextField(
                        value = paymentDays,
                        onValueChange = { paymentDays = it.filter { c -> c.isDigit() } },
                        label = { Text("账期") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        suffix = { Text("天") }
                    )
                }
            }

            // Section: SKU Pricing
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "SKU定价明细",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    TextButton(
                        onClick = {
                            if (canAddSku) {
                                skuItems = skuItems + SkuPricingDraft()
                            }
                        },
                        enabled = canAddSku
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("添加SKU")
                    }
                }
            }

            // Help text when no items
            if (skuItems.isEmpty()) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                        )
                    ) {
                        Text(
                            text = if (selectedSupplier == null) "请先选择供应商" else "点击上方「添加SKU」开始配置协议价格",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
            }

            // SKU Pricing rows
            itemsIndexed(
                items = skuItems,
                key = { index, _ -> "sku_row_$index" }
            ) { index, item ->
                SkuPricingRowEditor(
                    row = item,
                    availableSkus = filteredSkus,
                    existingSkuIds = skuItems.filterIndexed { i, r -> i != index }.mapNotNull { it.skuId }.toSet(),
                    onUpdate = { updated ->
                        skuItems = skuItems.toMutableList().also { it[index] = updated }
                    },
                    onDelete = {
                        skuItems = skuItems.toMutableList().also { it.removeAt(index) }
                    }
                )
            }

            // Footer note
            if (skuItems.isNotEmpty()) {
                item {
                    Text(
                        text = "注：单价填0或留空表示浮动价格（每次执行时需单独录入单价）",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

/**
 * 单行SKU定价编辑器
 * 包含：SKU选择（联动过滤）+ 单价 + 浮动标记 + 删除
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SkuPricingRowEditor(
    row: SkuPricingDraft,
    availableSkus: List<Sku>,
    existingSkuIds: Set<Long>,
    onUpdate: (SkuPricingDraft) -> Unit,
    onDelete: () -> Unit
) {
    var skuExpanded by remember { mutableStateOf(false) }

    // Filter out already-selected SKUs
    val selectableSkus = availableSkus.filter { it.id !in existingSkuIds }

    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // SKU selector
                ExposedDropdownMenuBox(
                    expanded = skuExpanded,
                    onExpandedChange = { if (selectableSkus.isNotEmpty()) skuExpanded = !skuExpanded },
                    modifier = Modifier.weight(1f)
                ) {
                    OutlinedTextField(
                        value = row.skuName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("SKU") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = skuExpanded) },
                        modifier = Modifier.menuAnchor(),
                        enabled = selectableSkus.isNotEmpty()
                    )
                    ExposedDropdownMenu(
                        expanded = skuExpanded,
                        onDismissRequest = { skuExpanded = false }
                    ) {
                        if (selectableSkus.isEmpty()) {
                            DropdownMenuItem(
                                text = { Text("无可用SKU") },
                                onClick = { skuExpanded = false },
                                enabled = false
                            )
                        }
                        selectableSkus.forEach { sku ->
                            DropdownMenuItem(
                                text = {
                                    Column {
                                        Text(sku.name)
                                        sku.model?.let { model ->
                                            Text(
                                                text = model,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                        }
                                    }
                                },
                                onClick = {
                                    onUpdate(row.copy(skuId = sku.id, skuName = sku.name))
                                    skuExpanded = false
                                }
                            )
                        }
                    }
                }

                // Delete button
                IconButton(onClick = onDelete) {
                    Icon(
                        Icons.Default.Delete,
                        contentDescription = "删除此行",
                        tint = MaterialTheme.colorScheme.error
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Price field
                OutlinedTextField(
                    value = if (row.price <= 0) "" else String.format("%.2f", row.price),
                    onValueChange = { newValue ->
                        val price = newValue.toDoubleOrNull() ?: 0.0
                        onUpdate(row.copy(price = price))
                    },
                    label = { Text("单价") },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    prefix = { Text("¥") }
                )

                // Floating toggle
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(start = 8.dp)
                ) {
                    Checkbox(
                        checked = row.isFloating,
                        onCheckedChange = { onUpdate(row.copy(isFloating = it)) }
                    )
                    Text("浮动", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

/**
 * SKU定价行草稿数据类
 */
private data class SkuPricingDraft(
    val skuId: Long? = null,
    val skuName: String = "",
    val price: Double = 0.0,
    val isFloating: Boolean = false
)
