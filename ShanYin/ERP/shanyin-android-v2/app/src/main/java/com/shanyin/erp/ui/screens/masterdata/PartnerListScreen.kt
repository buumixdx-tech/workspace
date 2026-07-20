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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.domain.model.ExternalPartner
import com.shanyin.erp.domain.model.PartnerType
import com.shanyin.erp.domain.usecase.DeletePartnerUseCase
import com.shanyin.erp.domain.usecase.GetAllPartnersUseCase
import com.shanyin.erp.domain.usecase.SavePartnerUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PartnerListUiState(
    val partners: List<ExternalPartner> = emptyList(),
    val isLoading: Boolean = true,
    val showDialog: Boolean = false,
    val editingPartner: ExternalPartner? = null,
    val error: String? = null
)

@HiltViewModel
class PartnerListViewModel @Inject constructor(
    private val getAllPartners: GetAllPartnersUseCase,
    private val savePartner: SavePartnerUseCase,
    private val deletePartner: DeletePartnerUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(PartnerListUiState())
    val uiState: StateFlow<PartnerListUiState> = _uiState.asStateFlow()

    init {
        loadPartners()
    }

    private fun loadPartners() {
        viewModelScope.launch {
            getAllPartners().collect { partners ->
                _uiState.update { it.copy(partners = partners, isLoading = false) }
            }
        }
    }

    fun showAddDialog() {
        _uiState.update { it.copy(showDialog = true, editingPartner = null) }
    }

    fun showEditDialog(partner: ExternalPartner) {
        _uiState.update { it.copy(showDialog = true, editingPartner = partner) }
    }

    fun dismissDialog() {
        _uiState.update { it.copy(showDialog = false, editingPartner = null) }
    }

    fun save(name: String, type: PartnerType?, address: String?, content: String?) {
        viewModelScope.launch {
            try {
                val partner = _uiState.value.editingPartner?.copy(
                    name = name, type = type, address = address, content = content
                ) ?: ExternalPartner(name = name, type = type, address = address, content = content)
                savePartner(partner)
                dismissDialog()
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }

    fun delete(partner: ExternalPartner) {
        viewModelScope.launch {
            try {
                deletePartner(partner)
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.message) }
            }
        }
    }
}

@Composable
fun PartnerListScreen(
    viewModel: PartnerListViewModel = hiltViewModel()
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
                text = "合作伙伴",
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
            uiState.partners.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("暂无合作伙伴数据，点击 + 添加", style = MaterialTheme.typography.bodyLarge)
                }
            }
            else -> {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(uiState.partners, key = { it.id }) { partner ->
                        PartnerCard(
                            partner = partner,
                            onEdit = { viewModel.showEditDialog(partner) },
                            onDelete = { viewModel.delete(partner) }
                        )
                    }
                }
            }
        }
    }

    if (uiState.showDialog) {
        PartnerDialog(
            partner = uiState.editingPartner,
            onDismiss = { viewModel.dismissDialog() },
            onSave = { name, type, address, content ->
                viewModel.save(name, type, address, content)
            }
        )
    }
}

@Composable
private fun PartnerCard(
    partner: ExternalPartner,
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
                Text(
                    text = partner.name,
                    style = MaterialTheme.typography.titleMedium
                )
                partner.type?.let {
                    AssistChip(
                        onClick = {},
                        label = { Text(it.displayName, style = MaterialTheme.typography.labelSmall) }
                    )
                }
                partner.address?.let {
                    Text(
                        text = it,
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
private fun PartnerDialog(
    partner: ExternalPartner?,
    onDismiss: () -> Unit,
    onSave: (String, PartnerType?, String?, String?) -> Unit
) {
    var name by remember { mutableStateOf(partner?.name ?: "") }
    var selectedType by remember { mutableStateOf(partner?.type) }
    var address by remember { mutableStateOf(partner?.address ?: "") }
    var content by remember { mutableStateOf(partner?.content ?: "") }
    var expanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (partner == null) "添加合作伙伴" else "编辑合作伙伴") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("名称 *") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                ExposedDropdownMenuBox(
                    expanded = expanded,
                    onExpandedChange = { expanded = !expanded }
                ) {
                    OutlinedTextField(
                        value = selectedType?.displayName ?: "",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("类型") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = expanded,
                        onDismissRequest = { expanded = false }
                    ) {
                        PartnerType.entries.forEach { type ->
                            DropdownMenuItem(
                                text = { Text(type.displayName) },
                                onClick = {
                                    selectedType = type
                                    expanded = false
                                }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = address,
                    onValueChange = { address = it },
                    label = { Text("地址") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = content,
                    onValueChange = { content = it },
                    label = { Text("备注") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 2,
                    maxLines = 4
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSave(name, selectedType, address.ifBlank { null }, content.ifBlank { null }) },
                enabled = name.isNotBlank()
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
