package com.shanyin.erp.ui.screens.masterdata

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.shanyin.erp.domain.model.BankAccount
import com.shanyin.erp.domain.model.OwnerType

@Composable
fun BankAccountListScreen(
    viewModel: BankAccountListViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "银行账户",
                style = MaterialTheme.typography.headlineSmall
            )
            IconButton(onClick = { viewModel.showAddDialog() }) {
                Icon(Icons.Default.Add, contentDescription = "添加")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        when {
            uiState.isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            uiState.bankAccounts.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("暂无账户数据，点击 + 添加", style = MaterialTheme.typography.bodyLarge)
                }
            }
            else -> {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(uiState.bankAccounts, key = { it.id }) { account ->
                        BankAccountCard(
                            account = account,
                            onEdit = { viewModel.showEditDialog(account) },
                            onDelete = { viewModel.delete(account) }
                        )
                    }
                }
            }
        }
    }

    if (uiState.showDialog) {
        BankAccountDialog(
            account = uiState.editingAccount,
            onDismiss = { viewModel.dismissDialog() },
            onSave = { ownerType, bankName, accountName, accountNumber, isDefault ->
                viewModel.save(ownerType, bankName, accountName, accountNumber, isDefault)
            }
        )
    }
}

@Composable
private fun BankAccountCard(
    account: BankAccount,
    onEdit: () -> Unit,
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
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = account.accountInfo?.accountName ?: "未知",
                        style = MaterialTheme.typography.titleMedium
                    )
                    account.ownerType?.let {
                        AssistChip(
                            onClick = {},
                            label = { Text(it.displayName, style = MaterialTheme.typography.labelSmall) }
                        )
                    }
                    if (account.isDefault) {
                        SuggestionChip(
                            onClick = {},
                            label = { Text("默认", style = MaterialTheme.typography.labelSmall) }
                        )
                    }
                }
                account.accountInfo?.bankName?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                account.accountInfo?.accountNumber?.let {
                    Text(
                        text = "****$it",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Row {
                IconButton(onClick = onEdit) {
                    Icon(Icons.Default.Edit, contentDescription = "编辑")
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Default.Delete, contentDescription = "删除")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BankAccountDialog(
    account: BankAccount?,
    onDismiss: () -> Unit,
    onSave: (OwnerType, String, String, String, Boolean) -> Unit
) {
    var selectedOwnerType by remember { mutableStateOf(account?.ownerType ?: OwnerType.OURSELVES) }
    var bankName by remember { mutableStateOf(account?.accountInfo?.bankName ?: "") }
    var accountName by remember { mutableStateOf(account?.accountInfo?.accountName ?: "") }
    var accountNumber by remember { mutableStateOf(account?.accountInfo?.accountNumber ?: "") }
    var isDefault by remember { mutableStateOf(account?.isDefault ?: false) }
    var expanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (account == null) "添加账户" else "编辑账户") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ExposedDropdownMenuBox(
                    expanded = expanded,
                    onExpandedChange = { expanded = !expanded }
                ) {
                    OutlinedTextField(
                        value = selectedOwnerType.displayName,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("账户类型") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = expanded,
                        onDismissRequest = { expanded = false }
                    ) {
                        OwnerType.entries.forEach { type ->
                            DropdownMenuItem(
                                text = { Text(type.displayName) },
                                onClick = {
                                    selectedOwnerType = type
                                    expanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = bankName,
                    onValueChange = { bankName = it },
                    label = { Text("银行名称") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = accountName,
                    onValueChange = { accountName = it },
                    label = { Text("账户名称 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = accountNumber,
                    onValueChange = { accountNumber = it },
                    label = { Text("账号 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Checkbox(
                        checked = isDefault,
                        onCheckedChange = { isDefault = it }
                    )
                    Text("设为默认账户")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onSave(selectedOwnerType, bankName, accountName, accountNumber, isDefault)
                },
                enabled = accountName.isNotBlank() && accountNumber.isNotBlank()
            ) {
                Text("保存")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}
