package com.shanyin.erp.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationDrawerItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.shanyin.erp.ui.navigation.Screen
import com.shanyin.erp.ui.navigation.mainScreens
import com.shanyin.erp.ui.screens.business.BusinessScreen
import com.shanyin.erp.ui.screens.dashboard.DashboardScreen
import com.shanyin.erp.ui.screens.finance.FinanceScreen
import com.shanyin.erp.ui.screens.inventory.InventoryScreen
import com.shanyin.erp.ui.screens.logistics.LogisticsScreen
import com.shanyin.erp.ui.screens.masterdata.CustomerListScreen
import com.shanyin.erp.ui.screens.masterdata.MasterDataScreen
import com.shanyin.erp.ui.screens.masterdata.SupplierListScreen
import com.shanyin.erp.ui.screens.masterdata.SkuListScreen
import com.shanyin.erp.ui.screens.masterdata.PointListScreen
import com.shanyin.erp.ui.screens.masterdata.PartnerListScreen
import com.shanyin.erp.ui.screens.masterdata.BankAccountListScreen
import com.shanyin.erp.ui.screens.importer.ImportScreen
import com.shanyin.erp.ui.screens.supplychain.SupplyChainScreen
import com.shanyin.erp.ui.screens.supplychain.SupplyChainCreateScreen
import com.shanyin.erp.ui.screens.timerules.TimeRulesScreen
import com.shanyin.erp.ui.screens.vc.VirtualContractScreen
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShanYinApp(
    navController: NavHostController = rememberNavController()
) {
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route ?: Screen.Dashboard.route

    val currentScreen = mainScreens.find { it.route == currentRoute } ?: Screen.Dashboard

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                Box(modifier = Modifier.fillMaxSize()) {
                    DrawerContent(
                        currentRoute = currentRoute,
                        onNavigate = { route ->
                            scope.launch {
                                drawerState.close()
                                navController.navigate(route) {
                                    popUpTo(Screen.Dashboard.route) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        }
                    )
                }
            }
        }
    ) {
        Scaffold { paddingValues ->
            NavHost(
                navController = navController,
                startDestination = Screen.Splash.route,
                modifier = Modifier.padding(paddingValues)
            ) {
                composable(Screen.Splash.route) {
                    com.shanyin.erp.ui.screens.splash.SplashScreen(onNavigateToDashboard = {
                        navController.navigate(Screen.Dashboard.route) {
                            popUpTo(Screen.Splash.route) { inclusive = true }
                        }
                    })
                }
                composable(Screen.Dashboard.route) { DashboardScreen(navController = navController) }
                composable(Screen.MasterData.route) { MasterDataScreen(navController) }
                composable(Screen.Business.route) { BusinessScreen() }
                composable(Screen.VirtualContract.route) { VirtualContractScreen() }
                composable(Screen.SupplyChain.route) { SupplyChainScreen(navController) }
                composable(Screen.SupplyChainCreate.route) { SupplyChainCreateScreen(navController) }
                composable(Screen.Inventory.route) { InventoryScreen() }
                composable(Screen.Logistics.route) { LogisticsScreen() }
                composable(Screen.Finance.route) { FinanceScreen() }
                composable(Screen.TimeRules.route) { TimeRulesScreen() }
                composable(Screen.CustomerList.route) { CustomerListScreen() }
                composable(Screen.SupplierList.route) { SupplierListScreen() }
                composable(Screen.SkuList.route) { SkuListScreen() }
                composable(Screen.PointList.route) { PointListScreen() }
                composable(Screen.PartnerList.route) { PartnerListScreen() }
                composable(Screen.BankAccountList.route) { BankAccountListScreen() }
                composable(Screen.Import.route) { ImportScreen(onNavigateBack = { navController.popBackStack() }) }
            }
        }
    }
}

@Composable
private fun DrawerContent(
    currentRoute: String,
    onNavigate: (String) -> Unit
) {
    androidx.compose.foundation.layout.Column(
        modifier = Modifier.fillMaxSize()
    ) {
        mainScreens.forEach { screen ->
            NavigationDrawerItem(
                icon = {
                    screen.icon?.let { Icon(it, contentDescription = screen.title) }
                },
                label = { Text(screen.title) },
                selected = currentRoute == screen.route,
                onClick = { onNavigate(screen.route) },
                modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
            )
        }
        Spacer(modifier = Modifier.weight(1f))
        HorizontalDivider()
        NavigationDrawerItem(
            icon = { Icon(Screen.Import.icon!!, contentDescription = Screen.Import.title) },
            label = { Text(Screen.Import.title) },
            selected = currentRoute == Screen.Import.route,
            onClick = { onNavigate(Screen.Import.route) },
            modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
        )
    }
}
