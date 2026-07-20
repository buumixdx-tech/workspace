package com.shanyin.erp.ui.screens.supplychain

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.navigation.NavController
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.ui.navigation.Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SupplyChainScreen(
    navController: NavController,
    viewModel: SupplyChainListViewModel = hiltViewModel()
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
            FloatingActionButton(onClick = { navController.navigate(Screen.SupplyChainCreate.route) }) {
                Icon(Icons.Default.Add, contentDescription = "新建供应链")
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
                text = "供应链管理",
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
                    text = { Text("物料") }
                )
                Tab(
                    selected = uiState.selectedTab == 2,
                    onClick = { viewModel.setSelectedTab(2) },
                    text = { Text("设备") }
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            when {
                uiState.isLoading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                uiState.filteredSupplyChains.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.ShoppingCart,
                                contentDescription = null,
                                modifier = Modifier.size(64.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("暂无供应链协议，点击 + 新建", style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
                else -> {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = PaddingValues(bottom = 80.dp)
                    ) {
                        items(uiState.filteredSupplyChains, key = { it.id }) { chain ->
                            SupplyChainCard(
                                supplyChain = chain,
                                onClick = { viewModel.showDetailDialog(chain) }
                            )
                        }
                    }
                }
            }
        }
    }

    if (uiState.showCreateDialog) {
        CreateSupplyChainDialog(
            suppliers = uiState.suppliers,
            skus = uiState.skus,
            onDismiss = { viewModel.dismissCreateDialog() },
            onConfirm = { supplierId, supplierName, type, items, prepaymentPercent, paymentDays ->
                viewModel.create(supplierId, supplierName, type, items, prepaymentPercent, paymentDays)
            }
        )
    }

    if (uiState.showDetailDialog && uiState.selectedSupplyChain != null) {
        SupplyChainDetailDialog(
            supplyChain = uiState.selectedSupplyChain!!,
            items = viewModel.supplyChainItems.collectAsState().value,
            skus = uiState.skus,
            onDismiss = { viewModel.dismissDetailDialog() },
            onAddSku = { skuId, skuName, price, deposit, isFloating ->
                viewModel.addSkuPricing(skuId, skuName, price, deposit, isFloating)
            },
            onRemoveSku = { viewModel.removeSkuPricing(it) },
            onDelete = { viewModel.delete(uiState.selectedSupplyChain!!) }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SupplyChainCard(
    supplyChain: SupplyChain,
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
                        text = supplyChain.supplierName,
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = "#${supplyChain.id}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                TypeBadge(type = supplyChain.type)
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                supplyChain.paymentTerms?.let { terms ->
                    InfoChip("预付 ${terms.prepaymentPercent}%")
                    InfoChip("账期 ${terms.paymentDays}天")
                }
            }
        }
    }
}

@Composable
private fun TypeBadge(type: SupplyChainType) {
    val (bgColor, textColor) = when (type) {
        SupplyChainType.MATERIAL -> Color(0xFFE3F2FD) to Color(0xFF1976D2)
        SupplyChainType.EQUIPMENT -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
    }
    Surface(color = bgColor, shape = MaterialTheme.shapes.small) {
        Text(
            text = type.displayName,
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
private fun CreateSupplyChainDialog(
    suppliers: List<Supplier>,
    skus: List<Sku>,
    onDismiss: () -> Unit,
    onConfirm: (Long, String, SupplyChainType, List<SupplyChainItem>, Double, Int) -> Unit
) {
    var selectedSupplier by remember { mutableStateOf<Supplier?>(null) }
    var selectedType by remember { mutableStateOf(SupplyChainType.MATERIAL) }
    var prepaymentPercent by remember { mutableStateOf("30") }
    var paymentDays by remember { mutableStateOf("30") }
    var selectedItems by remember { mutableStateOf(listOf<SupplyChainItem>()) }
    var supplierExpanded by remember { mutableStateOf(false) }
    var typeExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建供应链") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Supplier selector
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
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = supplierExpanded,
                        onDismissRequest = { supplierExpanded = false }
                    ) {
                        suppliers.forEach { supplier ->
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

                // Type selector
                ExposedDropdownMenuBox(
                    expanded = typeExpanded,
                    onExpandedChange = { typeExpanded = !typeExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedType.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("类型 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = typeExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = typeExpanded,
                        onDismissRequest = { typeExpanded = false }
                    ) {
                        SupplyChainType.entries.forEach { type ->
                            DropdownMenuItem(
                                text = { Text(type.displayName) },
                                onClick = {
                                    selectedType = type
                                    typeExpanded = false
                                }
                            )
                        }
                    }
                }

                // Payment terms
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = prepaymentPercent,
                        onValueChange = { prepaymentPercent = it.filter { c -> c.isDigit() } },
                        label = { Text("预付%") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = paymentDays,
                        onValueChange = { paymentDays = it.filter { c -> c.isDigit() } },
                        label = { Text("账期(天)") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                }

                Text(
                    text = "SKU定价将在详情页添加",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    selectedSupplier?.let { supplier ->
                        onConfirm(
                            supplier.id,
                            supplier.name,
                            selectedType,
                            selectedItems,
                            prepaymentPercent.toDoubleOrNull() ?: 30.0,
                            paymentDays.toIntOrNull() ?: 30
                        )
                    }
                },
                enabled = selectedSupplier != null
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

@Composable
private fun SupplyChainDetailDialog(
    supplyChain: SupplyChain,
    items: List<SupplyChainItem>,
    skus: List<Sku>,
    onDismiss: () -> Unit,
    onAddSku: (Long, String, Double, Double, Boolean) -> Unit,
    onRemoveSku: (SupplyChainItem) -> Unit,
    onDelete: () -> Unit
) {
    var showAddSkuDialog by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("#${supplyChain.id} ${supplyChain.supplierName}") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("类型", style = MaterialTheme.typography.bodyMedium)
                    TypeBadge(type = supplyChain.type)
                }

                supplyChain.paymentTerms?.let { terms ->
                    DetailRow("预付款", "${terms.prepaymentPercent}%")
                    DetailRow("账期", "${terms.paymentDays}天")
                }

                HorizontalDivider()

                // SKU Pricing section
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "SKU定价",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    TextButton(onClick = { showAddSkuDialog = true }) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                        Text("添加")
                    }
                }

                if (items.isEmpty()) {
                    Text(
                        "暂无SKU定价",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    items.forEach { item ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(item.skuName, style = MaterialTheme.typography.bodyMedium)
                                Text(
                                    "¥${item.price}${if (item.isFloating) " (浮动)" else ""}" +
                                            if (item.deposit > 0) " | 押金 ¥${item.deposit}" else "",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            IconButton(onClick = { onRemoveSku(item) }) {
                                Icon(Icons.Default.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Delete button
                OutlinedButton(
                    onClick = { showDeleteConfirm = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("删除供应链")
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭")
            }
        }
    )

    if (showAddSkuDialog) {
        AddSkuPricingDialog(
            skus = skus,
            onDismiss = { showAddSkuDialog = false },
            onConfirm = { skuId, skuName, price, deposit, isFloating ->
                onAddSku(skuId, skuName, price, deposit, isFloating)
                showAddSkuDialog = false
            }
        )
    }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("确认删除") },
            text = { Text("确定要删除此供应链协议吗？所有SKU定价也将被删除。") },
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddSkuPricingDialog(
    skus: List<Sku>,
    onDismiss: () -> Unit,
    onConfirm: (Long, String, Double, Double, Boolean) -> Unit
) {
    var selectedSku by remember { mutableStateOf<Sku?>(null) }
    var price by remember { mutableStateOf("") }
    var deposit by remember { mutableStateOf("") }
    var isFloating by remember { mutableStateOf(false) }
    var skuExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加SKU定价") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ExposedDropdownMenuBox(
                    expanded = skuExpanded,
                    onExpandedChange = { skuExpanded = !skuExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedSku?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("SKU *") },
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
                    value = price,
                    onValueChange = { price = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("单价 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = deposit,
                    onValueChange = { deposit = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("设备押金") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = isFloating, onCheckedChange = { isFloating = it })
                    Text("浮动价格")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    selectedSku?.let { sku ->
                        val priceValue = price.toDoubleOrNull() ?: 0.0
                        val depositValue = deposit.toDoubleOrNull() ?: 0.0
                        onConfirm(sku.id, sku.name, priceValue, depositValue, isFloating)
                    }
                },
                enabled = selectedSku != null && price.isNotBlank()
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
