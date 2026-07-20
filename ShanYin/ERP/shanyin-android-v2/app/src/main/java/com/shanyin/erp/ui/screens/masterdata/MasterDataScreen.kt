package com.shanyin.erp.ui.screens.masterdata

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController

data class MasterDataItem(
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val route: String
)

val masterDataItems = listOf(
    MasterDataItem("业务管理", "业务信息维护", Icons.Default.Business, "business"),
    MasterDataItem("客户管理", "渠道客户信息维护", Icons.Default.Person, "customer_list"),
    MasterDataItem("地点管理", "运营点/仓库信息", Icons.Default.Place, "point_list"),
    MasterDataItem("供应商", "供应商信息管理", Icons.Default.Store, "supplier_list"),
    MasterDataItem("商品", "SKU商品管理", Icons.Default.PointOfSale, "sku_list"),
    MasterDataItem("合作伙伴", "外部合作伙伴", Icons.Default.Group, "partner_list"),
    MasterDataItem("银行账户", "资金账户管理", Icons.Default.AccountBalance, "bank_account_list")
)

@Composable
fun MasterDataScreen(navController: NavController) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            Text(
                text = "主数据管理",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.padding(vertical = 16.dp)
            )
        }
        items(masterDataItems) { item ->
            MasterDataCard(
                item = item,
                onClick = { navController.navigate(item.route) }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MasterDataCard(
    item: MasterDataItem,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Icon(
                imageVector = item.icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(48.dp)
            )
            Column {
                Text(
                    text = item.title,
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    text = item.subtitle,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
