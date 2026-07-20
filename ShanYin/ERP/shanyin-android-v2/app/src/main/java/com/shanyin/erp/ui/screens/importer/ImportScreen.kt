package com.shanyin.erp.ui.screens.importer

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Upload
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.shanyin.erp.data.repository.ImportEvent

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ImportScreen(
    onNavigateBack: () -> Unit,
    viewModel: ImportViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    val filePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let { viewModel.importFromJson(it) }
    }

    LaunchedEffect(uiState.status) {
        if (uiState.status is ImportStatus.Success) {
            // 成功后 2 秒返回
            kotlinx.coroutines.delay(2000)
            onNavigateBack()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("导入数据") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            when (val status = uiState.status) {
                is ImportStatus.Idle -> {
                    IdleContent(onPickFile = { filePicker.launch(arrayOf("application/json")) })
                }
                is ImportStatus.Importing -> {
                    ImportingContent(
                        table = status.table,
                        current = status.current,
                        total = status.total
                    )
                }
                is ImportStatus.Success -> {
                    SuccessContent(rows = status.rows)
                }
                is ImportStatus.Error -> {
                    ErrorContent(
                        message = status.message,
                        onRetry = { filePicker.launch(arrayOf("application/json")) }
                    )
                }
            }
        }
    }
}

@Composable
private fun IdleContent(onPickFile: () -> Unit) {
    Icon(
        Icons.Default.Upload,
        contentDescription = null,
        modifier = Modifier.size(80.dp),
        tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.6f)
    )
    Spacer(modifier = Modifier.height(24.dp))
    Text(
        text = "从 Desktop 端导出数据",
        style = MaterialTheme.typography.titleMedium
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
        text = "在 Desktop 端运行 scripts/export_single_json.py，\n生成 database.json 文件后选择导入",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center
    )
    Spacer(modifier = Modifier.height(32.dp))
    Button(onClick = onPickFile) {
        Text("选择 database.json")
    }
}

@Composable
private fun ImportingContent(table: String, current: Int, total: Int) {
    CircularProgressIndicator()
    Spacer(modifier = Modifier.height(24.dp))
    Text(
        text = "正在导入…",
        style = MaterialTheme.typography.titleMedium
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
        text = table.ifEmpty { "准备中…" },
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
    if (total > 0) {
        Spacer(modifier = Modifier.height(8.dp))
        LinearProgressIndicator(
            progress = { current.toFloat() / total.toFloat() },
            modifier = Modifier.width(200.dp)
        )
        Text(
            text = "$current / $total 张表",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun SuccessContent(rows: Int) {
    Icon(
        Icons.Default.CheckCircle,
        contentDescription = null,
        modifier = Modifier.size(80.dp),
        tint = MaterialTheme.colorScheme.primary
    )
    Spacer(modifier = Modifier.height(24.dp))
    Text(
        text = "导入成功",
        style = MaterialTheme.typography.titleLarge
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
        text = "$rows 条记录已入库",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
        text = "即将返回…",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
}

@Composable
private fun ErrorContent(message: String, onRetry: () -> Unit) {
    Icon(
        Icons.Default.Error,
        contentDescription = null,
        modifier = Modifier.size(80.dp),
        tint = MaterialTheme.colorScheme.error
    )
    Spacer(modifier = Modifier.height(24.dp))
    Text(
        text = "导入失败",
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.error
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
        text = message,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center
    )
    Spacer(modifier = Modifier.height(24.dp))
    Button(onClick = onRetry) {
        Text("重试")
    }
}
