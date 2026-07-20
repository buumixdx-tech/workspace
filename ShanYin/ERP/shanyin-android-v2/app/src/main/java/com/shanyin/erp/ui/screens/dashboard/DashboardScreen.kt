package com.shanyin.erp.ui.screens.dashboard

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Rule
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.shanyin.erp.domain.model.*
import com.shanyin.erp.ui.navigation.Screen
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    navController: NavController,
    viewModel: DashboardViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    if (uiState.isLoading) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Header
        item {
            Text(
                text = "仪表盘",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "欢迎使用闪饮ERP系统",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        // KPI Section - Business Relationships
        item {
            SectionHeader(title = "业务关系", icon = Icons.Default.Business)
        }
        item {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    KpiCard(
                        title = "业务",
                        value = uiState.businessCount.toString(),
                        icon = Icons.Default.Business,
                        color = Color(0xFF7B1FA2),
                        onClick = { navController.navigate(Screen.Business.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "供应链",
                        value = uiState.supplyChainCount.toString(),
                        icon = Icons.Default.ShoppingCart,
                        color = Color(0xFF00838F),
                        onClick = { navController.navigate(Screen.SupplyChain.route) }
                    )
                }
            }
        }

        // KPI Section - Virtual Contract
        item {
            SectionHeader(title = "虚拟合同", icon = Icons.Default.Receipt)
        }
        item {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    KpiCard(
                        title = "虚拟合同",
                        value = uiState.vcCount.toString(),
                        icon = Icons.Default.Receipt,
                        color = Color(0xFF1976D2),
                        onClick = { navController.navigate(Screen.VirtualContract.route) }
                    )
                }
            }
        }

        // KPI Section - Business Operations
        item {
            SectionHeader(title = "业务操作", icon = Icons.Default.LocalShipping)
        }
        item {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    KpiCard(
                        title = "物流",
                        value = uiState.logisticsCount.toString(),
                        icon = Icons.Default.LocalShipping,
                        color = Color(0xFF5D4037),
                        onClick = { navController.navigate(Screen.Logistics.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "资金流",
                        value = uiState.cashFlowCount.toString(),
                        icon = Icons.Default.Payments,
                        color = Color(0xFF6A1B9A),
                        onClick = { navController.navigate(Screen.Finance.route) }
                    )
                }
            }
        }

        // KPI Section - Master Data (new row inserted before Inventory)
        item {
            SectionHeader(title = "主数据", icon = Icons.Default.Store)
        }
        item {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    KpiCard(
                        title = "客户",
                        value = uiState.customerCount.toString(),
                        icon = Icons.Default.Person,
                        color = Color(0xFF1976D2),
                        onClick = { navController.navigate(Screen.CustomerList.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "供应商",
                        value = uiState.supplierCount.toString(),
                        icon = Icons.Default.Store,
                        color = Color(0xFF388E3C),
                        onClick = { navController.navigate(Screen.SupplierList.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "SKU",
                        value = uiState.skuCount.toString(),
                        icon = Icons.Default.PointOfSale,
                        color = Color(0xFFE65100),
                        onClick = { navController.navigate(Screen.SkuList.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "点位",
                        value = "—",
                        icon = Icons.Default.LocationOn,
                        color = Color(0xFF00897B),
                        onClick = { navController.navigate(Screen.PointList.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "外部合作方",
                        value = "—",
                        icon = Icons.Default.SupervisorAccount,
                        color = Color(0xFF8D6E63),
                        onClick = { }
                    )
                }
            }
        }

        // KPI Section - Inventory
        item {
            SectionHeader(title = "仓储", icon = Icons.Default.Inventory)
        }
        item {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    KpiCard(
                        title = "设备库存",
                        value = uiState.equipmentInventoryCount.toString(),
                        icon = Icons.Default.Memory,
                        color = Color(0xFF00695C),
                        onClick = { navController.navigate(Screen.Inventory.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "物料库存",
                        value = uiState.materialInventoryCount.toString(),
                        icon = Icons.Default.Inventory2,
                        color = Color(0xFF558B2F),
                        onClick = { navController.navigate(Screen.Inventory.route) }
                    )
                }
            }
        }

        // KPI Section - Time Rules
        item {
            SectionHeader(title = "时间规则", icon = Icons.Default.Schedule)
        }
        item {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    KpiCard(
                        title = "规则总数",
                        value = uiState.timeRuleCount.toString(),
                        icon = Icons.AutoMirrored.Filled.Rule,
                        color = Color(0xFF5E35B1),
                        onClick = { navController.navigate(Screen.TimeRules.route) }
                    )
                }
                item {
                    KpiCard(
                        title = "预警中",
                        value = uiState.warningRuleCount.toString(),
                        icon = Icons.Default.Warning,
                        color = Color(0xFFC62828),
                        onClick = { navController.navigate(Screen.TimeRules.route) }
                    )
                }
            }
        }

        // Monthly Financial Summary
        item {
            SectionHeader(title = "本月财务", icon = Icons.Default.AccountBalance)
        }
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { navController.navigate(Screen.Finance.route) }
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        FinancialSummaryItem(
                            label = "收入",
                            value = uiState.monthlyRevenue,
                            color = Color(0xFF388E3C)
                        )
                        FinancialSummaryItem(
                            label = "支出",
                            value = uiState.monthlyExpense,
                            color = Color(0xFFC62828)
                        )
                        FinancialSummaryItem(
                            label = "净利润",
                            value = uiState.monthlyProfit,
                            color = if (uiState.monthlyProfit >= 0) Color(0xFF388E3C) else Color(0xFFC62828)
                        )
                    }
                }
            }
        }

        // Recent Cash Flows
        if (uiState.recentCashFlows.isNotEmpty()) {
            item {
                SectionHeader(title = "最近资金流水", icon = Icons.Default.Payments)
            }
            item {
                Card(
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        uiState.recentCashFlows.forEach { cashFlow ->
                            CashFlowRow(cashFlow = cashFlow)
                        }
                    }
                }
            }
        }

        // Bottom padding
        item {
            Spacer(modifier = Modifier.height(80.dp))
        }
    }
}

@Composable
private fun SectionHeader(title: String, icon: ImageVector) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(24.dp)
        )
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
private fun KpiCard(
    title: String,
    value: String,
    icon: ImageVector,
    color: Color,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .width(120.dp)
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = color.copy(alpha = 0.1f)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = color
            )
            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun FinancialSummaryItem(
    label: String,
    value: Double,
    color: Color
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = "¥${String.format("%.2f", value)}",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = color
        )
    }
}

@Composable
private fun BankAccountRow(account: BankAccount) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = account.accountInfo?.let { "${it.bankName} ${it.accountNumber}" } ?: "账户 #${account.id}",
                style = MaterialTheme.typography.bodyMedium
            )
            account.ownerType?.let {
                Text(
                    text = it.displayName,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (account.isDefault) {
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer,
                shape = MaterialTheme.shapes.small
            ) {
                Text(
                    text = "默认",
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                )
            }
        }
    }
}

@Composable
private fun CashFlowRow(cashFlow: CashFlow) {
    val dateFormat = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = cashFlow.type?.displayName ?: "未知",
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                text = cashFlow.transactionDate?.let { dateFormat.format(Date(it)) } ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Text(
            text = "¥${String.format("%.2f", cashFlow.amount)}",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary
        )
    }
}

@Composable
private fun EventRow(event: SystemEvent) {
    val dateFormat = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = event.eventType.displayName,
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                text = event.description ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1
            )
        }
        Text(
            text = dateFormat.format(Date(event.timestamp)),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
