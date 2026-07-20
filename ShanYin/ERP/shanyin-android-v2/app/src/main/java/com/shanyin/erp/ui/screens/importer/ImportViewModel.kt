package com.shanyin.erp.ui.screens.importer

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shanyin.erp.data.repository.ImportEvent
import com.shanyin.erp.data.repository.JsonImportRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ImportUiState(
    val status: ImportStatus = ImportStatus.Idle
)

sealed class ImportStatus {
    data object Idle : ImportStatus()
    data class Importing(val table: String = "", val current: Int = 0, val total: Int = 0) : ImportStatus()
    data class Success(val rows: Int) : ImportStatus()
    data class Error(val message: String) : ImportStatus()
}

@HiltViewModel
class ImportViewModel @Inject constructor(
    private val repository: JsonImportRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ImportUiState())
    val uiState: StateFlow<ImportUiState> = _uiState.asStateFlow()

    fun importFromJson(uri: Uri) {
        viewModelScope.launch {
            repository.importFromJson(uri).collect { event ->
                _uiState.value = when (event) {
                    is ImportEvent.Idle -> ImportUiState(ImportStatus.Importing())
                    is ImportEvent.Progress -> ImportUiState(
                        ImportStatus.Importing(event.table, event.current, event.total)
                    )
                    is ImportEvent.Success -> ImportUiState(ImportStatus.Success(event.totalRows))
                    is ImportEvent.Error -> ImportUiState(ImportStatus.Error(event.message))
                }
            }
        }
    }
}
