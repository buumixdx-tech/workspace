package com.shanyin.erp.ui.screens.inventory

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
import com.shanyin.erp.domain.model.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InventoryScreen(
    viewModel: InventoryViewModel = hiltViewModel()
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
                FloatingActionButton(onClick = { viewModel.showEquipmentDialog() }) {
                    Icon(Icons.Default.Add, contentDescription = "添加设备")
                }
            } else {
                FloatingActionButton(onClick = { viewModel.showMaterialDialog() }) {
                    Icon(Icons.Default.Add, contentDescription = "添加物料")
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
                text = "仓储管理",
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
                    text = { Text("设备库存") },
                    icon = { Icon(Icons.Default.Memory, contentDescription = null) }
                )
                Tab(
                    selected = uiState.selectedTab == 1,
                    onClick = { viewModel.setSelectedTab(1) },
                    text = { Text("物料库存") },
                    icon = { Icon(Icons.Default.Inventory2, contentDescription = null) }
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
                    EquipmentInventoryList(
                        equipmentList = uiState.equipmentList,
                        onEquipmentClick = { viewModel.showEquipmentDetailDialog(it) }
                    )
                }
                else -> {
                    MaterialInventoryList(
                        materialList = uiState.materialList,
                        onMaterialClick = { viewModel.showMaterialDetailDialog(it) },
                        onTransferClick = { viewModel.showTransferDialog() }
                    )
                }
            }
        }
    }

    // Equipment Create Dialog
    if (uiState.showEquipmentDialog) {
        CreateEquipmentDialog(
            skus = uiState.skus,
            virtualContracts = uiState.virtualContracts,
            points = uiState.points,
            onDismiss = { viewModel.dismissEquipmentDialog() },
            onConfirm = { skuId, sn, opStatus, devStatus, vcId, pointId, deposit ->
                viewModel.createEquipment(skuId, sn, opStatus, devStatus, vcId, pointId, deposit)
            }
        )
    }

    // Material Create Dialog
    if (uiState.showMaterialDialog) {
        CreateMaterialDialog(
            skus = uiState.skus,
            points = uiState.points,
            onDismiss = { viewModel.dismissMaterialDialog() },
            onConfirm = { skuId, pointId, pointName, qty, price ->
                viewModel.createMaterial(skuId, pointId, pointName, qty, price)
            }
        )
    }

    // Equipment Detail Dialog
    if (uiState.showDetailDialog && uiState.selectedEquipment != null) {
        EquipmentDetailDialog(
            equipment = uiState.selectedEquipment!!,
            onDismiss = { viewModel.dismissDetailDialog() },
            onUpdateStatus = { opStatus, devStatus ->
                viewModel.updateEquipmentStatus(uiState.selectedEquipment!!.id, opStatus, devStatus)
            },
            onDelete = { viewModel.deleteEquipment(uiState.selectedEquipment!!) }
        )
    }

    // Material Detail Dialog
    if (uiState.showDetailDialog && uiState.selectedMaterial != null) {
        MaterialDetailDialog(
            material = uiState.selectedMaterial!!,
            skus = uiState.skus,
            points = uiState.points,
            onDismiss = { viewModel.dismissDetailDialog() },
            onUpdateStock = { pointId, pointName, qty, price ->
                viewModel.updateMaterialStock(uiState.selectedMaterial!!.skuId, pointId, pointName, qty, price)
            },
            onDelete = { viewModel.deleteMaterial(uiState.selectedMaterial!!) }
        )
    }

    // Transfer Dialog
    if (uiState.showTransferDialog) {
        TransferInventoryDialog(
            skus = uiState.skus,
            points = uiState.points,
            onDismiss = { viewModel.dismissTransferDialog() },
            onConfirm = { skuId, fromPointId, fromPointName, toPointId, toPointName, qty ->
                viewModel.transferMaterial(skuId, fromPointId, fromPointName, toPointId, toPointName, qty)
            }
        )
    }
}

@Composable
private fun EquipmentInventoryList(
    equipmentList: List<EquipmentInventory>,
    onEquipmentClick: (EquipmentInventory) -> Unit
) {
    if (equipmentList.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Memory,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无设备库存，点击 + 添加", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            items(equipmentList, key = { it.id }) { equipment ->
                EquipmentCard(equipment = equipment, onClick = { onEquipmentClick(equipment) })
            }
        }
    }
}

@Composable
private fun MaterialInventoryList(
    materialList: List<MaterialInventory>,
    onMaterialClick: (MaterialInventory) -> Unit,
    onTransferClick: () -> Unit
) {
    if (materialList.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Inventory2,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无物料库存，点击 + 添加", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            items(materialList, key = { it.id }) { material ->
                MaterialCard(material = material, onClick = { onMaterialClick(material) })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EquipmentCard(
    equipment: EquipmentInventory,
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
                        text = equipment.skuName ?: "未指定设备",
                        style = MaterialTheme.typography.titleMedium
                    )
                    equipment.sn?.let {
                        Text(
                            text = "SN: $it",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                Column(horizontalAlignment = Alignment.End) {
                    OperationalStatusBadge(status = equipment.operationalStatus)
                    Spacer(modifier = Modifier.height(4.dp))
                    DeviceStatusBadge(status = equipment.deviceStatus)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                equipment.vcTypeName?.let {
                    InfoChip("合同: $it")
                }
                equipment.pointName?.let {
                    InfoChip("地点: $it")
                }
                if (equipment.depositAmount > 0) {
                    InfoChip("押金: ¥${equipment.depositAmount}")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MaterialCard(
    material: MaterialInventory,
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
                Text(
                    text = material.skuName,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    text = "¥${String.format("%.2f", material.totalBalance)}",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            if (material.stockDistribution.isNotEmpty()) {
                material.stockDistribution.forEach { dist ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "${dist.pointName} (ID:${dist.pointId})",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "${dist.quantity} 件",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            } else {
                Text(
                    text = "暂无库存",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun OperationalStatusBadge(status: OperationalStatus) {
    val (bgColor, textColor) = when (status) {
        OperationalStatus.IN_STOCK -> Color(0xFFE3F2FD) to Color(0xFF1976D2)
        OperationalStatus.IN_OPERATION -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
        OperationalStatus.DISPOSAL -> Color(0xFFFFF3E0) to Color(0xFFE65100)
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
private fun DeviceStatusBadge(status: DeviceStatus) {
    val (bgColor, textColor) = when (status) {
        DeviceStatus.NORMAL -> Color(0xFFE8F5E9) to Color(0xFF388E3C)
        DeviceStatus.MAINTENANCE -> Color(0xFFFFF3E0) to Color(0xFFE65100)
        DeviceStatus.DAMAGED -> Color(0xFFFFEBEE) to Color(0xFFC62828)
        DeviceStatus.FAULT -> Color(0xFFFFEBEE) to Color(0xFFC62828)
        DeviceStatus.MAINTENANCE_REQUIRED -> Color(0xFFFFF3E0) to Color(0xFFE65100)
        DeviceStatus.LOCKED -> Color(0xFFECEFF1) to Color(0xFF546E7A)
    }
    Surface(color = bgColor, shape = MaterialTheme.shapes.small) {
        Text(
            text = status.displayName,
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
private fun CreateEquipmentDialog(
    skus: List<Sku>,
    virtualContracts: List<VirtualContract>,
    points: List<Point>,
    onDismiss: () -> Unit,
    onConfirm: (Long?, String?, OperationalStatus, DeviceStatus, Long?, Long?, Double) -> Unit
) {
    var selectedSku by remember { mutableStateOf<Sku?>(null) }
    var sn by remember { mutableStateOf("") }
    var selectedOpStatus by remember { mutableStateOf(OperationalStatus.IN_STOCK) }
    var selectedDevStatus by remember { mutableStateOf(DeviceStatus.NORMAL) }
    var selectedVc by remember { mutableStateOf<VirtualContract?>(null) }
    var selectedPoint by remember { mutableStateOf<Point?>(null) }
    var depositAmount by remember { mutableStateOf("") }
    var skuExpanded by remember { mutableStateOf(false) }
    var vcExpanded by remember { mutableStateOf(false) }
    var pointExpanded by remember { mutableStateOf(false) }
    var opStatusExpanded by remember { mutableStateOf(false) }
    var devStatusExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加设备库存") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // SKU selector
                ExposedDropdownMenuBox(
                    expanded = skuExpanded,
                    onExpandedChange = { skuExpanded = !skuExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedSku?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("设备SKU") },
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
                    value = sn,
                    onValueChange = { sn = it },
                    label = { Text("序列号") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                // Operational Status
                ExposedDropdownMenuBox(
                    expanded = opStatusExpanded,
                    onExpandedChange = { opStatusExpanded = !opStatusExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedOpStatus.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("运营状态") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = opStatusExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = opStatusExpanded,
                        onDismissRequest = { opStatusExpanded = false }
                    ) {
                        OperationalStatus.entries.forEach { status ->
                            DropdownMenuItem(
                                text = { Text(status.displayName) },
                                onClick = {
                                    selectedOpStatus = status
                                    opStatusExpanded = false
                                }
                            )
                        }
                    }
                }

                // Device Status
                ExposedDropdownMenuBox(
                    expanded = devStatusExpanded,
                    onExpandedChange = { devStatusExpanded = !devStatusExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedDevStatus.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("设备状态") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = devStatusExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = devStatusExpanded,
                        onDismissRequest = { devStatusExpanded = false }
                    ) {
                        DeviceStatus.entries.forEach { status ->
                            DropdownMenuItem(
                                text = { Text(status.displayName) },
                                onClick = {
                                    selectedDevStatus = status
                                    devStatusExpanded = false
                                }
                            )
                        }
                    }
                }

                // Virtual Contract selector
                ExposedDropdownMenuBox(
                    expanded = vcExpanded,
                    onExpandedChange = { vcExpanded = !vcExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedVc?.let { "${it.type?.displayName} #${it.id}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("虚拟合同") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = vcExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = vcExpanded,
                        onDismissRequest = { vcExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无") },
                            onClick = {
                                selectedVc = null
                                vcExpanded = false
                            }
                        )
                        virtualContracts.forEach { vc ->
                            DropdownMenuItem(
                                text = { Text("${vc.type?.displayName} #${vc.id}") },
                                onClick = {
                                    selectedVc = vc
                                    vcExpanded = false
                                }
                            )
                        }
                    }
                }

                // Point selector
                ExposedDropdownMenuBox(
                    expanded = pointExpanded,
                    onExpandedChange = { pointExpanded = !pointExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("地点") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = pointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = pointExpanded,
                        onDismissRequest = { pointExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无") },
                            onClick = {
                                selectedPoint = null
                                pointExpanded = false
                            }
                        )
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text(point.name) },
                                onClick = {
                                    selectedPoint = point
                                    pointExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = depositAmount,
                    onValueChange = { depositAmount = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("押金金额") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onConfirm(
                        selectedSku?.id,
                        sn.takeIf { it.isNotBlank() },
                        selectedOpStatus,
                        selectedDevStatus,
                        selectedVc?.id,
                        selectedPoint?.id,
                        depositAmount.toDoubleOrNull() ?: 0.0
                    )
                }
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
private fun CreateMaterialDialog(
    skus: List<Sku>,
    points: List<Point>,
    onDismiss: () -> Unit,
    onConfirm: (Long, Long, String, Int, Double) -> Unit
) {
    var selectedSku by remember { mutableStateOf<Sku?>(null) }
    var selectedPoint by remember { mutableStateOf<Point?>(null) }
    var quantity by remember { mutableStateOf("") }
    var averagePrice by remember { mutableStateOf("") }
    var skuExpanded by remember { mutableStateOf(false) }
    var pointExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加物料库存") },
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
                        label = { Text("物料SKU *") },
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

                // 点位选择器
                ExposedDropdownMenuBox(
                    expanded = pointExpanded,
                    onExpandedChange = { pointExpanded = !pointExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("仓库/点位 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = pointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = pointExpanded,
                        onDismissRequest = { pointExpanded = false }
                    ) {
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text("${point.name} (${point.type?.displayName ?: "点位"})") },
                                onClick = {
                                    selectedPoint = point
                                    pointExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = quantity,
                    onValueChange = { quantity = it.filter { c -> c.isDigit() } },
                    label = { Text("数量 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = averagePrice,
                    onValueChange = { averagePrice = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("单价") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    selectedSku?.let { sku ->
                        selectedPoint?.let { point ->
                            onConfirm(
                                sku.id,
                                point.id,
                                point.name,
                                quantity.toIntOrNull() ?: 0,
                                averagePrice.toDoubleOrNull() ?: 0.0
                            )
                        }
                    }
                },
                enabled = selectedSku != null && selectedPoint != null && quantity.isNotBlank()
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
private fun EquipmentDetailDialog(
    equipment: EquipmentInventory,
    onDismiss: () -> Unit,
    onUpdateStatus: (OperationalStatus?, DeviceStatus?) -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var selectedOpStatus by remember { mutableStateOf(equipment.operationalStatus) }
    var selectedDevStatus by remember { mutableStateOf(equipment.deviceStatus) }
    var opStatusExpanded by remember { mutableStateOf(false) }
    var devStatusExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("#${equipment.id} ${equipment.skuName ?: "设备"}") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                equipment.sn?.let {
                    DetailRow("序列号", it)
                }

                // Operational Status selector
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("运营状态", style = MaterialTheme.typography.bodyMedium)
                    ExposedDropdownMenuBox(
                        expanded = opStatusExpanded,
                        onExpandedChange = { opStatusExpanded = !opStatusExpanded },
                        modifier = Modifier.width(150.dp)
                    ) {
                        OutlinedTextField(
                            value = selectedOpStatus.displayName,
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = opStatusExpanded) },
                            modifier = Modifier.menuAnchor(),
                            singleLine = true
                        )
                        ExposedDropdownMenu(
                            expanded = opStatusExpanded,
                            onDismissRequest = { opStatusExpanded = false }
                        ) {
                            OperationalStatus.entries.forEach { status ->
                                DropdownMenuItem(
                                    text = { Text(status.displayName) },
                                    onClick = {
                                        selectedOpStatus = status
                                        opStatusExpanded = false
                                    }
                                )
                            }
                        }
                    }
                }

                // Device Status selector
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("设备状态", style = MaterialTheme.typography.bodyMedium)
                    ExposedDropdownMenuBox(
                        expanded = devStatusExpanded,
                        onExpandedChange = { devStatusExpanded = !devStatusExpanded },
                        modifier = Modifier.width(150.dp)
                    ) {
                        OutlinedTextField(
                            value = selectedDevStatus.displayName,
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = devStatusExpanded) },
                            modifier = Modifier.menuAnchor(),
                            singleLine = true
                        )
                        ExposedDropdownMenu(
                            expanded = devStatusExpanded,
                            onDismissRequest = { devStatusExpanded = false }
                        ) {
                            DeviceStatus.entries.forEach { status ->
                                DropdownMenuItem(
                                    text = { Text(status.displayName) },
                                    onClick = {
                                        selectedDevStatus = status
                                        devStatusExpanded = false
                                    }
                                )
                            }
                        }
                    }
                }

                equipment.vcTypeName?.let {
                    DetailRow("关联合同", it)
                }
                equipment.pointName?.let {
                    DetailRow("关联地点", it)
                }
                if (equipment.depositAmount > 0) {
                    DetailRow("押金", "¥${equipment.depositAmount}")
                }

                HorizontalDivider()

                OutlinedButton(
                    onClick = { showDeleteConfirm = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("删除设备")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onUpdateStatus(
                        if (selectedOpStatus != equipment.operationalStatus) selectedOpStatus else null,
                        if (selectedDevStatus != equipment.deviceStatus) selectedDevStatus else null
                    )
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
            text = { Text("确定要删除此设备库存记录吗？") },
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
private fun MaterialDetailDialog(
    material: MaterialInventory,
    skus: List<Sku>,
    points: List<Point>,
    onDismiss: () -> Unit,
    onUpdateStock: (Long, String, Int, Double) -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var selectedSku by remember { mutableStateOf(skus.find { it.id == material.skuId }) }
    var selectedPoint by remember { mutableStateOf(material.stockDistribution.firstOrNull()?.let { p -> points.find { it.id == p.pointId } }) }
    var quantity by remember { mutableStateOf(material.stockDistribution.firstOrNull()?.quantity?.toString() ?: "") }
    var averagePrice by remember { mutableStateOf(if (material.averagePrice > 0) material.averagePrice.toString() else "") }
    var skuExpanded by remember { mutableStateOf(false) }
    var pointExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("#${material.id} ${material.skuName}") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    "库存信息",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )

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

                // 点位选择器
                ExposedDropdownMenuBox(
                    expanded = pointExpanded,
                    onExpandedChange = { pointExpanded = !pointExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("仓库/点位") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = pointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = pointExpanded,
                        onDismissRequest = { pointExpanded = false }
                    ) {
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text("${point.name} (${point.type?.displayName ?: "点位"})") },
                                onClick = {
                                    selectedPoint = point
                                    pointExpanded = false
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

                OutlinedTextField(
                    value = averagePrice,
                    onValueChange = { averagePrice = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("单价") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                if (material.stockDistribution.size > 1) {
                    HorizontalDivider()
                    Text(
                        "所有仓库库存",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    material.stockDistribution.forEach { dist ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("${dist.pointName} (ID:${dist.pointId})", style = MaterialTheme.typography.bodySmall)
                            Text("${dist.quantity} 件", style = MaterialTheme.typography.bodySmall)
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
                    Text("删除物料")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    selectedPoint?.let { point ->
                        onUpdateStock(
                            point.id,
                            point.name,
                            quantity.toIntOrNull() ?: 0,
                            averagePrice.toDoubleOrNull() ?: 0.0
                        )
                    }
                    onDismiss()
                },
                enabled = selectedPoint != null && quantity.isNotBlank()
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
            text = { Text("确定要删除此物料库存记录吗？") },
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
private fun TransferInventoryDialog(
    skus: List<Sku>,
    points: List<Point>,
    onDismiss: () -> Unit,
    onConfirm: (Long, Long, String, Long, String, Int) -> Unit
) {
    var selectedSku by remember { mutableStateOf<Sku?>(null) }
    var fromPoint by remember { mutableStateOf<Point?>(null) }
    var toPoint by remember { mutableStateOf<Point?>(null) }
    var quantity by remember { mutableStateOf("") }
    var skuExpanded by remember { mutableStateOf(false) }
    var fromPointExpanded by remember { mutableStateOf(false) }
    var toPointExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("库存调拨") },
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
                        label = { Text("物料SKU *") },
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

                // 源仓库/点位选择器
                ExposedDropdownMenuBox(
                    expanded = fromPointExpanded,
                    onExpandedChange = { fromPointExpanded = !fromPointExpanded }
                ) {
                    OutlinedTextField(
                        value = fromPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("源仓库 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = fromPointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = fromPointExpanded,
                        onDismissRequest = { fromPointExpanded = false }
                    ) {
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text("${point.name} (${point.type?.displayName ?: "点位"})") },
                                onClick = {
                                    fromPoint = point
                                    fromPointExpanded = false
                                }
                            )
                        }
                    }
                }

                // 目标仓库/点位选择器
                ExposedDropdownMenuBox(
                    expanded = toPointExpanded,
                    onExpandedChange = { toPointExpanded = !toPointExpanded }
                ) {
                    OutlinedTextField(
                        value = toPoint?.name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("目标仓库 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = toPointExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = toPointExpanded,
                        onDismissRequest = { toPointExpanded = false }
                    ) {
                        points.forEach { point ->
                            DropdownMenuItem(
                                text = { Text("${point.name} (${point.type?.displayName ?: "点位"})") },
                                onClick = {
                                    toPoint = point
                                    toPointExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = quantity,
                    onValueChange = { quantity = it.filter { c -> c.isDigit() } },
                    label = { Text("调拨数量 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    selectedSku?.let { sku ->
                        fromPoint?.let { from ->
                            toPoint?.let { to ->
                                onConfirm(
                                    sku.id,
                                    from.id,
                                    from.name,
                                    to.id,
                                    to.name,
                                    quantity.toIntOrNull() ?: 0
                                )
                            }
                        }
                    }
                },
                enabled = selectedSku != null && fromPoint != null &&
                          toPoint != null && quantity.isNotBlank()
            ) {
                Text("调拨")
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
