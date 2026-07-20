package com.shanyin.erp.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Rule
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Business
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.Inventory
import androidx.compose.material.icons.filled.LocalShipping
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.PointOfSale
import androidx.compose.material.icons.filled.Receipt
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Upload
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.filled.Store
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(
    val route: String,
    val title: String,
    val icon: ImageVector? = null
) {
    // Splash Navigation
    data object Splash : Screen("splash", "Splash", null)

    // Main Navigation
    data object Dashboard : Screen("dashboard", "仪表盘", Icons.Default.Dashboard)
    data object MasterData : Screen("master_data", "主数据", Icons.Default.Store)
    data object Business : Screen("business", "业务管理", Icons.Default.Business)
    data object VirtualContract : Screen("virtual_contract", "虚拟合同", Icons.Default.Receipt)
    data object SupplyChain : Screen("supply_chain", "供应链", Icons.Default.ShoppingCart)
    data object Inventory : Screen("inventory", "仓储", Icons.Default.Inventory)
    data object Logistics : Screen("logistics", "物流", Icons.Default.LocalShipping)
    data object Finance : Screen("finance", "财务", Icons.Default.AccountBalance)
    data object TimeRules : Screen("time_rules", "时间规则", Icons.AutoMirrored.Filled.Rule)

    // Sub-screens
    data object CustomerList : Screen("customer_list", "客户管理", Icons.Default.Person)
    data object SupplierList : Screen("supplier_list", "供应商", Icons.Default.Store)
    data object SkuList : Screen("sku_list", "商品", Icons.Default.PointOfSale)
    data object PointList : Screen("point_list", "地点管理", Icons.Default.Place)
    data object PartnerList : Screen("partner_list", "合作伙伴", Icons.Default.Group)
    data object BankAccountList : Screen("bank_account_list", "银行账户", Icons.Default.AccountBalance)

    // Supply Chain sub-screens
    data object SupplyChainCreate : Screen("supply_chain_create", "新建供应链", null)
    data object SupplyChainDetail : Screen("supply_chain_detail/{chainId}", "供应链详情", null) {
        fun createRoute(chainId: Long) = "supply_chain_detail/$chainId"
    }

    // Data import
    data object Import : Screen("import", "导入数据", Icons.Default.Upload)
}

val mainScreens = listOf(
    Screen.Dashboard,
    Screen.MasterData,
    Screen.Business,
    Screen.VirtualContract,
    Screen.SupplyChain,
    Screen.Inventory,
    Screen.Logistics,
    Screen.Finance,
    Screen.TimeRules
)

val masterDataSubScreens = listOf(
    Screen.CustomerList,
    Screen.SupplierList,
    Screen.SkuList,
    Screen.PointList,
    Screen.PartnerList,
    Screen.BankAccountList
)
