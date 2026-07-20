package com.shanyin.erp.ui.screens.finance

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
import com.shanyin.erp.domain.usecase.finance.ApArDetailItem
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinanceScreen(
    viewModel: FinanceViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val accountBalances by viewModel.accountBalances.collectAsState()
    val monthlyReport by viewModel.currentMonthlyReport.collectAsState()
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
            when (uiState.selectedTab) {
                0 -> FloatingActionButton(onClick = { viewModel.showCreateCashFlowDialog() }) {
                    Icon(Icons.Default.Add, contentDescription = "添加资金流水")
                }
                1 -> FloatingActionButton(onClick = { viewModel.showCreateVoucherDialog() }) {
                    Icon(Icons.Default.Add, contentDescription = "添加凭证")
                }
                2 -> FloatingActionButton(onClick = { viewModel.showAccountDialog() }) {
                    Icon(Icons.Default.Add, contentDescription = "添加账户")
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
                text = "财务管理",
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
                    text = { Text("资金流水") },
                    icon = { Icon(Icons.Default.Payments, contentDescription = null) }
                )
                Tab(
                    selected = uiState.selectedTab == 1,
                    onClick = { viewModel.setSelectedTab(1) },
                    text = { Text("凭证管理") },
                    icon = { Icon(Icons.Default.Receipt, contentDescription = null) }
                )
                Tab(
                    selected = uiState.selectedTab == 2,
                    onClick = { viewModel.setSelectedTab(2) },
                    text = { Text("账户") },
                    icon = { Icon(Icons.Default.AccountBalance, contentDescription = null) }
                )
                Tab(
                    selected = uiState.selectedTab == 3,
                    onClick = { viewModel.setSelectedTab(3) },
                    text = { Text("应付账款") },
                    icon = { Icon(Icons.Default.AccountBalanceWallet, contentDescription = null) }
                )
                Tab(
                    selected = uiState.selectedTab == 4,
                    onClick = { viewModel.setSelectedTab(4) },
                    text = { Text("应收账款") },
                    icon = { Icon(Icons.Default.Receipt, contentDescription = null) }
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
                    CashFlowList(
                        cashFlows = viewModel.getFilteredCashFlows(),
                        onDelete = { viewModel.deleteCashFlow(it) }
                    )
                }
                uiState.selectedTab == 1 -> {
                    VoucherList(
                        vouchers = viewModel.getVouchers(),
                        journalEntries = uiState.journalEntries,
                        onInternalTransferClick = { viewModel.showInternalTransferDialog() },
                        onExternalFundClick = { viewModel.showExternalFundDialog() }
                    )
                }
                uiState.selectedTab == 2 -> {
                    AccountList(
                        accounts = uiState.financeAccounts,
                        balances = accountBalances,
                        onDelete = { viewModel.deleteFinanceAccount(it) }
                    )
                }
                uiState.selectedTab == 3 -> {
                    ApDetailList(
                        items = uiState.apDetails,
                        totalBalance = uiState.apBalance
                    )
                }
                uiState.selectedTab == 4 -> {
                    ArDetailList(
                        items = uiState.arDetails,
                        totalBalance = uiState.arBalance
                    )
                }
            }
        }
    }

    // Create Cash Flow Dialog
    if (uiState.showCreateCashFlowDialog) {
        CreateCashFlowDialog(
            virtualContracts = uiState.virtualContracts,
            bankAccounts = uiState.bankAccounts,
            onDismiss = { viewModel.dismissCreateCashFlowDialog() },
            onConfirm = { vcId, type, amount, payerId, payeeId, desc, date ->
                viewModel.createCashFlow(vcId, type, amount, payerId, payeeId, desc, date)
            }
        )
    }

    // Create Voucher Dialog
    if (uiState.showCreateVoucherDialog) {
        CreateVoucherDialog(
            financeAccounts = uiState.financeAccounts,
            onDismiss = { viewModel.dismissCreateVoucherDialog() },
            onConfirm = { entries ->
                viewModel.createVoucher(entries)
            }
        )
    }

    // Account Dialog
    if (uiState.showAccountDialog) {
        CreateAccountDialog(
            onDismiss = { viewModel.dismissAccountDialog() },
            onConfirm = { account ->
                viewModel.saveFinanceAccount(account)
            }
        )
    }

    // Internal Transfer Dialog
    if (uiState.showInternalTransferDialog) {
        InternalTransferDialog(
            bankAccounts = uiState.bankAccounts,
            onDismiss = { viewModel.dismissInternalTransferDialog() },
            onConfirm = { fromId, toId, amount, desc ->
                viewModel.performInternalTransfer(fromId, toId, amount, desc)
            }
        )
    }

    // External Fund Dialog
    if (uiState.showExternalFundDialog) {
        ExternalFundDialog(
            bankAccounts = uiState.bankAccounts,
            onDismiss = { viewModel.dismissExternalFundDialog() },
            onConfirm = { accountId, fundType, amount, entity, desc, isInbound ->
                viewModel.performExternalFund(accountId, fundType, amount, entity, desc, isInbound)
            }
        )
    }
}

@Composable
private fun CashFlowList(
    cashFlows: List<CashFlowWithDirection>,
    onDelete: (CashFlow) -> Unit
) {
    if (cashFlows.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Payments,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无资金流水", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            items(cashFlows, key = { it.cashFlow.id }) { item ->
                CashFlowCard(
                    item = item,
                    onDelete = { onDelete(item.cashFlow) }
                )
            }
        }
    }
}

@Composable
private fun CashFlowCard(
    item: CashFlowWithDirection,
    onDelete: () -> Unit
) {
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()) }
    val cf = item.cashFlow

    val amountColor = if (item.isIncome) Color(0xFF2E7D32) else Color(0xFFC62828)
    val directionLabel = if (item.isIncome) "流入" else "流出"

    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // 第一行：类型 + 方向标签 + 金额
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = cf.type?.displayName ?: "未知",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Surface(
                        color = if (item.isIncome) Color(0xFFE8F5E9) else Color(0xFFFFEBEE),
                        shape = MaterialTheme.shapes.extraSmall
                    ) {
                        Text(
                            text = directionLabel,
                            style = MaterialTheme.typography.labelSmall,
                            color = if (item.isIncome) Color(0xFF2E7D32) else Color(0xFFC62828),
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                    // VC 类型标签
                    item.vcTypeName?.let { vcName ->
                        Spacer(modifier = Modifier.width(4.dp))
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = MaterialTheme.shapes.extraSmall
                        ) {
                            Text(
                                text = vcName,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                            )
                        }
                    }
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "${if (item.isIncome) "+" else "-"}¥${String.format("%.2f", cf.amount)}",
                        style = MaterialTheme.typography.titleMedium,
                        color = amountColor
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        if (cf.financeTriggered) {
                            Surface(
                                color = Color(0xFFE8F5E9),
                                shape = MaterialTheme.shapes.extraSmall
                            ) {
                                Text(
                                    text = "已凭证化",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color(0xFF388E3C),
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                                )
                            }
                        }
                        cf.voucherPath?.takeIf { it.isNotBlank() }?.let {
                            Surface(
                                color = Color(0xFFE3F2FD),
                                shape = MaterialTheme.shapes.extraSmall
                            ) {
                                Text(
                                    text = it,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color(0xFF1976D2),
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                                )
                            }
                        }
                    }
                }
            }

            // RETURN VC 显示退款方向
            if (item.vcReturnDirection != null) {
                Spacer(modifier = Modifier.height(4.dp))
                val returnDirText = when (item.vcReturnDirection) {
                    ReturnDirection.US_TO_SUPPLIER -> "我们退货给供应商，供应商退款给我们"
                    ReturnDirection.CUSTOMER_TO_US -> "客户退货给我们，我们退款给客户"
                }
                Text(
                    text = returnDirText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

            // 第二行：付款/收款账户（主体名称大字体 + 银行信息小字体）
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                AccountDisplayChip("付", item.payerDisplayName)
                AccountDisplayChip("收", item.payeeDisplayName)
                cf.virtualContractId?.let { InfoChip("VC#$it") }
            }

            // 第三行：付款详情
            cf.paymentInfo?.let { pi ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    pi.paymentMethod?.let { InfoChip(it) }
                    pi.bankName?.let { InfoChip(it) }
                    pi.referenceNo?.let { InfoChip("REF: $it") }
                }
            }

            Spacer(modifier = Modifier.height(4.dp))

            // 第四行：日期 + 描述
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                cf.transactionDate?.let { date ->
                    Text(
                        text = dateFormat.format(Date(date)),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } ?: Text(
                    text = dateFormat.format(Date(cf.timestamp)),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            cf.description?.let { desc ->
                if (desc.isNotBlank()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = desc,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun VoucherList(
    vouchers: Map<String, List<FinancialJournalEntry>>,
    journalEntries: List<FinancialJournalEntry>,
    onInternalTransferClick: () -> Unit,
    onExternalFundClick: () -> Unit
) {
    val entriesWithoutVoucher = journalEntries.filter { it.voucherNo == null }

    if (vouchers.isEmpty() && entriesWithoutVoucher.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Receipt,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无凭证", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            // Internal transfer and external fund buttons
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.End
                ) {
                    TextButton(onClick = onExternalFundClick) {
                        Icon(Icons.Default.AccountBalanceWallet, contentDescription = null)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("外部出入金")
                    }
                    TextButton(onClick = onInternalTransferClick) {
                        Icon(Icons.Default.SwapHoriz, contentDescription = null)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("内部划拨")
                    }
                }
            }

            // Entries without voucher
            if (entriesWithoutVoucher.isNotEmpty()) {
                item {
                    Text(
                        text = "未凭证化分录",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                }
                items(entriesWithoutVoucher, key = { "pending_${it.id}" }) { entry ->
                    JournalEntryCard(entry = entry, isPending = true)
                }
            }

            // Vouchers
            vouchers.forEach { (voucherNo, entries) ->
                item {
                    Text(
                        text = "凭证号: $voucherNo",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                }
                items(entries, key = { "v_${voucherNo}_${it.id}" }) { entry ->
                    JournalEntryCard(entry = entry, isPending = false)
                }
            }
        }
    }
}

@Composable
private fun JournalEntryCard(
    entry: FinancialJournalEntry,
    isPending: Boolean
) {
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = if (isPending) CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
        ) else CardDefaults.cardColors()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = entry.accountName ?: "账户 #${entry.accountId}",
                    style = MaterialTheme.typography.bodyMedium
                )
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    if (entry.debit > 0) {
                        Text(
                            text = "借: ¥${String.format("%.2f", entry.debit)}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFC62828)
                        )
                    }
                    if (entry.credit > 0) {
                        Text(
                            text = "贷: ¥${String.format("%.2f", entry.credit)}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFF2E7D32)
                        )
                    }
                }
            }
            entry.summary?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Text(
                text = dateFormat.format(Date(entry.transactionDate)),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun AccountList(
    accounts: List<FinanceAccount>,
    balances: Map<Long, Double>,
    onDelete: (FinanceAccount) -> Unit
) {
    if (accounts.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.AccountBalance,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无财务账户", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            // Group by category
            val grouped = accounts.groupBy { it.category }
            FinanceCategory.entries.forEach { category ->
                val categoryAccounts = grouped[category] ?: emptyList()
                if (categoryAccounts.isNotEmpty()) {
                    item {
                        Text(
                            text = category.displayName,
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                    items(categoryAccounts, key = { it.id }) { account ->
                        FinanceAccountCard(
                            account = account,
                            balance = balances[account.id] ?: 0.0,
                            onDelete = { onDelete(account) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun FinanceAccountCard(
    account: FinanceAccount,
    balance: Double,
    onDelete: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = account.level1Name,
                    style = MaterialTheme.typography.titleMedium
                )
                account.level2Name?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                account.direction?.let {
                    Text(
                        text = it.displayName,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Text(
                text = "¥${String.format("%.2f", balance)}",
                style = MaterialTheme.typography.titleMedium,
                color = if (balance >= 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
            )
        }
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

/**
 * 账户显示芯片：三行显示
 * 格式：
 * 付
 * 客户名
 * [账号]
 */
@Composable
private fun AccountDisplayChip(prefix: String, displayName: String?) {
    if (displayName.isNullOrBlank()) return
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.small
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalAlignment = Alignment.Start
        ) {
            // 第一行：前缀
            Text(
                text = prefix,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary
            )
            // 第二行：主体名称
            val parts = displayName.split(" ", limit = 2)
            Text(
                text = parts.getOrElse(0) { displayName },
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            // 第三行：账号后四位
            if (displayName.contains("[")) {
                Text(
                    text = displayName.substringAfter("[").let { "[$it" },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                )
            }
        }
    }
}

private data class VoucherEntryDraft(
    val accountId: Long,
    val accountName: String,
    val debit: Double,
    val credit: Double,
    val summary: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreateCashFlowDialog(
    virtualContracts: List<VirtualContract>,
    bankAccounts: List<BankAccount>,
    onDismiss: () -> Unit,
    onConfirm: (Long?, CashFlowType, Double, Long?, Long?, String?, Long?) -> Unit
) {
    var selectedVc by remember { mutableStateOf<VirtualContract?>(null) }
    var selectedType by remember { mutableStateOf(CashFlowType.PREPAYMENT) }
    var amount by remember { mutableStateOf("") }
    var selectedPayer by remember { mutableStateOf<BankAccount?>(null) }
    var selectedPayee by remember { mutableStateOf<BankAccount?>(null) }
    var description by remember { mutableStateOf("") }
    var vcExpanded by remember { mutableStateOf(false) }
    var typeExpanded by remember { mutableStateOf(false) }
    var payerExpanded by remember { mutableStateOf(false) }
    var payeeExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加资金流水") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                ExposedDropdownMenuBox(
                    expanded = vcExpanded,
                    onExpandedChange = { vcExpanded = !vcExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedVc?.let { "${it.type?.displayName} #${it.id}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("关联合同") },
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

                ExposedDropdownMenuBox(
                    expanded = typeExpanded,
                    onExpandedChange = { typeExpanded = !typeExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedType.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("类型") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = typeExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = typeExpanded,
                        onDismissRequest = { typeExpanded = false }
                    ) {
                        CashFlowType.entries.forEach { type ->
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

                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("金额 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                ExposedDropdownMenuBox(
                    expanded = payerExpanded,
                    onExpandedChange = { payerExpanded = !payerExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedPayer?.accountInfo?.let { "${it.bankName} ${it.accountNumber}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("付款账户") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = payerExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = payerExpanded,
                        onDismissRequest = { payerExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无") },
                            onClick = {
                                selectedPayer = null
                                payerExpanded = false
                            }
                        )
                        bankAccounts.forEach { account ->
                            DropdownMenuItem(
                                text = { Text("${account.accountInfo?.bankName} ${account.accountInfo?.accountNumber}") },
                                onClick = {
                                    selectedPayer = account
                                    payerExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = payeeExpanded,
                    onExpandedChange = { payeeExpanded = !payeeExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedPayee?.accountInfo?.let { "${it.bankName} ${it.accountNumber}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("收款账户") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = payeeExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = payeeExpanded,
                        onDismissRequest = { payeeExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("无") },
                            onClick = {
                                selectedPayee = null
                                payeeExpanded = false
                            }
                        )
                        bankAccounts.forEach { account ->
                            DropdownMenuItem(
                                text = { Text("${account.accountInfo?.bankName} ${account.accountInfo?.accountNumber}") },
                                onClick = {
                                    selectedPayee = account
                                    payeeExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onConfirm(
                        selectedVc?.id,
                        selectedType,
                        amount.toDoubleOrNull() ?: 0.0,
                        selectedPayer?.id,
                        selectedPayee?.id,
                        description.takeIf { it.isNotBlank() },
                        System.currentTimeMillis()
                    )
                },
                enabled = amount.isNotBlank()
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
private fun CreateVoucherDialog(
    financeAccounts: List<FinanceAccount>,
    onDismiss: () -> Unit,
    onConfirm: (List<FinancialJournalEntry>) -> Unit
) {
    var entries by remember { mutableStateOf(listOf<VoucherEntryDraft>()) }
    var accountExpanded by remember { mutableStateOf(false) }
    var selectedAccount by remember { mutableStateOf<FinanceAccount?>(null) }
    var debitAmount by remember { mutableStateOf("") }
    var creditAmount by remember { mutableStateOf("") }
    var summary by remember { mutableStateOf("") }

    val totalDebit = entries.sumOf { it.debit }
    val totalCredit = entries.sumOf { it.credit }
    val isBalanced = totalDebit == totalCredit && totalDebit > 0

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("创建复式记账凭证") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Add entry form
                ExposedDropdownMenuBox(
                    expanded = accountExpanded,
                    onExpandedChange = { accountExpanded = !accountExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedAccount?.level1Name ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("账户") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = accountExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = accountExpanded,
                        onDismissRequest = { accountExpanded = false }
                    ) {
                        financeAccounts.forEach { account ->
                            DropdownMenuItem(
                                text = { Text(account.level1Name) },
                                onClick = {
                                    selectedAccount = account
                                    accountExpanded = false
                                }
                            )
                        }
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = debitAmount,
                        onValueChange = { debitAmount = it.filter { c -> c.isDigit() || c == '.' } },
                        label = { Text("借方金额") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = creditAmount,
                        onValueChange = { creditAmount = it.filter { c -> c.isDigit() || c == '.' } },
                        label = { Text("贷方金额") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                }

                OutlinedTextField(
                    value = summary,
                    onValueChange = { summary = it },
                    label = { Text("摘要") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                TextButton(
                    onClick = {
                        selectedAccount?.let { account ->
                            val draft = VoucherEntryDraft(
                                accountId = account.id,
                                accountName = account.level1Name,
                                debit = debitAmount.toDoubleOrNull() ?: 0.0,
                                credit = creditAmount.toDoubleOrNull() ?: 0.0,
                                summary = summary
                            )
                            entries = entries + draft
                            debitAmount = ""
                            creditAmount = ""
                            summary = ""
                            selectedAccount = null
                        }
                    },
                    enabled = selectedAccount != null && (debitAmount.isNotBlank() || creditAmount.isNotBlank())
                ) {
                    Icon(Icons.Default.Add, contentDescription = null)
                    Text("添加分录")
                }

                HorizontalDivider()

                // Entry list
                Text(
                    "分录列表 (${entries.size})",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )

                entries.forEachIndexed { index, entry ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(entry.accountName, style = MaterialTheme.typography.bodySmall)
                            if (entry.debit > 0) Text("借: ¥${entry.debit}", style = MaterialTheme.typography.bodySmall, color = Color(0xFFC62828))
                            if (entry.credit > 0) Text("贷: ¥${entry.credit}", style = MaterialTheme.typography.bodySmall, color = Color(0xFF2E7D32))
                        }
                        IconButton(onClick = {
                            entries = entries.toMutableList().also { it.removeAt(index) }
                        }) {
                            Icon(Icons.Default.Close, contentDescription = "移除")
                        }
                    }
                }

                Text(
                    "合计: 借 ¥$totalDebit | 贷 ¥$totalCredit ${if (!isBalanced) "⚠️ 不平衡" else "✓"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (isBalanced) Color(0xFF388E3C) else MaterialTheme.colorScheme.error
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val journalEntries = entries.map {
                        FinancialJournalEntry(
                            accountId = it.accountId,
                            accountName = it.accountName,
                            debit = it.debit,
                            credit = it.credit,
                            summary = it.summary.takeIf { s -> s.isNotBlank() }
                        )
                    }
                    onConfirm(journalEntries)
                },
                enabled = isBalanced
            ) {
                Text("创建凭证")
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
private fun CreateAccountDialog(
    onDismiss: () -> Unit,
    onConfirm: (FinanceAccount) -> Unit
) {
    var selectedCategory by remember { mutableStateOf(FinanceCategory.ASSET) }
    var level1Name by remember { mutableStateOf("") }
    var level2Name by remember { mutableStateOf("") }
    var selectedDirection by remember { mutableStateOf<AccountDirection?>(null) }
    var categoryExpanded by remember { mutableStateOf(false) }
    var directionExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加财务账户") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                ExposedDropdownMenuBox(
                    expanded = categoryExpanded,
                    onExpandedChange = { categoryExpanded = !categoryExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedCategory.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("类别") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = categoryExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = categoryExpanded,
                        onDismissRequest = { categoryExpanded = false }
                    ) {
                        FinanceCategory.entries.forEach { category ->
                            DropdownMenuItem(
                                text = { Text(category.displayName) },
                                onClick = {
                                    selectedCategory = category
                                    categoryExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = level1Name,
                    onValueChange = { level1Name = it },
                    label = { Text("一级科目 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = level2Name,
                    onValueChange = { level2Name = it },
                    label = { Text("二级科目") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                ExposedDropdownMenuBox(
                    expanded = directionExpanded,
                    onExpandedChange = { directionExpanded = !directionExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedDirection?.displayName ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("借贷方向") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = directionExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = directionExpanded,
                        onDismissRequest = { directionExpanded = false }
                    ) {
                        AccountDirection.entries.forEach { direction ->
                            DropdownMenuItem(
                                text = { Text(direction.displayName) },
                                onClick = {
                                    selectedDirection = direction
                                    directionExpanded = false
                                }
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val account = FinanceAccount(
                        category = selectedCategory,
                        level1Name = level1Name,
                        level2Name = level2Name.takeIf { it.isNotBlank() },
                        direction = selectedDirection
                    )
                    onConfirm(account)
                },
                enabled = level1Name.isNotBlank()
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
private fun InternalTransferDialog(
    bankAccounts: List<BankAccount>,
    onDismiss: () -> Unit,
    onConfirm: (Long, Long, Double, String?) -> Unit
) {
    var fromAccount by remember { mutableStateOf<BankAccount?>(null) }
    var toAccount by remember { mutableStateOf<BankAccount?>(null) }
    var amount by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var fromExpanded by remember { mutableStateOf(false) }
    var toExpanded by remember { mutableStateOf(false) }

    val isValid = fromAccount != null && toAccount != null &&
            fromAccount?.id != toAccount?.id &&
            (amount.toDoubleOrNull() ?: 0.0) > 0

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("内部资金划拨") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = "源账户 → 目标账户",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                ExposedDropdownMenuBox(
                    expanded = fromExpanded,
                    onExpandedChange = { fromExpanded = !fromExpanded }
                ) {
                    OutlinedTextField(
                        value = fromAccount?.accountInfo?.let { "${it.bankName} ${it.accountNumber}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("源账户 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = fromExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = fromExpanded,
                        onDismissRequest = { fromExpanded = false }
                    ) {
                        bankAccounts.forEach { account ->
                            DropdownMenuItem(
                                text = { Text("${account.accountInfo?.bankName} ${account.accountInfo?.accountNumber}") },
                                onClick = {
                                    fromAccount = account
                                    fromExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = toExpanded,
                    onExpandedChange = { toExpanded = !toExpanded }
                ) {
                    OutlinedTextField(
                        value = toAccount?.accountInfo?.let { "${it.bankName} ${it.accountNumber}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("目标账户 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = toExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = toExpanded,
                        onDismissRequest = { toExpanded = false }
                    ) {
                        bankAccounts.forEach { account ->
                            DropdownMenuItem(
                                text = { Text("${account.accountInfo?.bankName} ${account.accountInfo?.accountNumber}") },
                                onClick = {
                                    toAccount = account
                                    toExpanded = false
                                }
                            )
                        }
                    }
                }

                if (fromAccount?.id == toAccount?.id && fromAccount != null && toAccount != null) {
                    Text(
                        text = "源账户与目标账户不能相同",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }

                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("划拨金额 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onConfirm(
                        fromAccount!!.id,
                        toAccount!!.id,
                        amount.toDoubleOrNull() ?: 0.0,
                        description.takeIf { it.isNotBlank() }
                    )
                },
                enabled = isValid
            ) {
                Text("确认划拨")
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
private fun ExternalFundDialog(
    bankAccounts: List<BankAccount>,
    onDismiss: () -> Unit,
    onConfirm: (Long, String, Double, String, String?, Boolean) -> Unit
) {
    var selectedAccount by remember { mutableStateOf<BankAccount?>(null) }
    var fundType by remember { mutableStateOf(FundTypeItem.inboundTypes.first()) }
    var amount by remember { mutableStateOf("") }
    var externalEntity by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var isInbound by remember { mutableStateOf(true) }
    var accountExpanded by remember { mutableStateOf(false) }
    var fundTypeExpanded by remember { mutableStateOf(false) }

    val isValid = selectedAccount != null && externalEntity.isNotBlank() &&
            (amount.toDoubleOrNull() ?: 0.0) > 0

    val fundTypes = if (isInbound) FundTypeItem.inboundTypes else FundTypeItem.outboundTypes

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (isInbound) "外部入金" else "外部出金") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    FilterChip(
                        selected = isInbound,
                        onClick = {
                            isInbound = true
                            fundType = FundTypeItem.inboundTypes.first()
                        },
                        label = { Text("入金") }
                    )
                    FilterChip(
                        selected = !isInbound,
                        onClick = {
                            isInbound = false
                            fundType = FundTypeItem.outboundTypes.first()
                        },
                        label = { Text("出金") }
                    )
                }

                ExposedDropdownMenuBox(
                    expanded = accountExpanded,
                    onExpandedChange = { accountExpanded = !accountExpanded }
                ) {
                    OutlinedTextField(
                        value = selectedAccount?.accountInfo?.let { "${it.bankName} ${it.accountNumber}" } ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("银行账户 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = accountExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = accountExpanded,
                        onDismissRequest = { accountExpanded = false }
                    ) {
                        bankAccounts.forEach { account ->
                            DropdownMenuItem(
                                text = { Text("${account.accountInfo?.bankName} ${account.accountInfo?.accountNumber}") },
                                onClick = {
                                    selectedAccount = account
                                    accountExpanded = false
                                }
                            )
                        }
                    }
                }

                ExposedDropdownMenuBox(
                    expanded = fundTypeExpanded,
                    onExpandedChange = { fundTypeExpanded = !fundTypeExpanded }
                ) {
                    OutlinedTextField(
                        value = fundType.shortName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("资金性质 *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = fundTypeExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = fundTypeExpanded,
                        onDismissRequest = { fundTypeExpanded = false }
                    ) {
                        fundTypes.forEach { type ->
                            DropdownMenuItem(
                                text = { Text(type.shortName) },
                                onClick = {
                                    fundType = type
                                    fundTypeExpanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = externalEntity,
                    onValueChange = { externalEntity = it },
                    label = { Text("外部实体名称 *") },
                    placeholder = { Text("例如：股东张三、XX银行") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("金额 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("备注") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onConfirm(
                        selectedAccount!!.id,
                        fundType.fullName,
                        amount.toDoubleOrNull() ?: 0.0,
                        externalEntity,
                        description.takeIf { it.isNotBlank() },
                        isInbound
                    )
                },
                enabled = isValid
            ) {
                Text("确认")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}

// Fund type items matching Desktop FundNature
private object FundTypeItem {
    val inboundTypes = listOf(
        FundType("实收资本", "实收资本 (股东注资/增资)"),
        FundType("其他应付款", "其他应付款 (外部借款/暂付款)"),
        FundType("其他应收款", "其他应收款 (收回垫款)"),
        FundType("管理费用", "管理费用 (冲减过往支出)")
    )

    val outboundTypes = listOf(
        FundType("管理费用", "管理费用 (日常开支/报销/办公)"),
        FundType("其他应付款", "其他应付款 (还款/退款)"),
        FundType("其他应收款", "其他应收款 (借给外部/垫付金)"),
        FundType("实收资本", "实收资本 (减资/分红)")
    )
}

private data class FundType(
    val shortName: String,
    val fullName: String
)

// ==================== AP/AR Detail List ====================

@Composable
fun ApDetailList(
    items: List<ApArDetailItem>,
    totalBalance: Double
) {
    if (items.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.AccountBalanceWallet,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无应付账款记录", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            // Balance summary card
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "应付账款余额",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            text = "¥${String.format("%.2f", totalBalance)}",
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            item {
                Text(
                    text = "明细账（共 ${items.size} 笔）",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(vertical = 8.dp)
                )
            }

            items(items, key = { "${it.voucherNo}_${it.date}" }) { item ->
                ApArDetailCard(item = item, isAp = true)
            }
        }
    }
}

@Composable
fun ArDetailList(
    items: List<ApArDetailItem>,
    totalBalance: Double
) {
    if (items.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Default.Receipt,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text("暂无应收账款记录", style = MaterialTheme.typography.bodyLarge)
            }
        }
    } else {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 80.dp)
        ) {
            // Balance summary card
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "应收账款余额",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            text = "¥${String.format("%.2f", totalBalance)}",
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.secondary
                        )
                    }
                }
            }

            item {
                Text(
                    text = "明细账（共 ${items.size} 笔）",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(vertical = 8.dp)
                )
            }

            items(items, key = { "${it.voucherNo}_${it.date}" }) { item ->
                ApArDetailCard(item = item, isAp = false)
            }
        }
    }
}

@Composable
private fun ApArDetailCard(
    item: ApArDetailItem,
    isAp: Boolean
) {
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = item.counterpartName ?: "供应商",
                        style = MaterialTheme.typography.titleMedium
                    )
                    item.voucherNo.takeIf { it.isNotBlank() }?.let {
                        Text(
                            text = "凭证: $it",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                Column(horizontalAlignment = Alignment.End) {
                    if (item.credit > 0) {
                        Text(
                            text = "+¥${String.format("%.2f", item.credit)}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (isAp) Color(0xFFC62828) else Color(0xFF2E7D32)
                        )
                    }
                    if (item.debit > 0) {
                        Text(
                            text = "-¥${String.format("%.2f", item.debit)}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (isAp) Color(0xFF2E7D32) else Color(0xFFC62828)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(4.dp))

            item.summary.takeIf { it.isNotBlank() }?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = dateFormat.format(Date(item.date)),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                item.vcId?.let {
                    Text(
                        text = "VC#$it",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "累计余额",
                    style = MaterialTheme.typography.labelSmall
                )
                Text(
                    text = "¥${String.format("%.2f", item.balance)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (item.balance > 0) {
                        if (isAp) Color(0xFFC62828) else Color(0xFF2E7D32)
                    } else {
                        MaterialTheme.colorScheme.onSurface
                    }
                )
            }
        }
    }
}
