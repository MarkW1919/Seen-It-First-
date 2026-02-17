package com.reposcan.pro.ui.screens.hotlist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.HotListEntry
import com.reposcan.pro.data.repository.HotListRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HotListState(
    val entries: List<HotListEntry> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val showAddDialog: Boolean = false
)

@HiltViewModel
class HotListViewModel @Inject constructor(
    private val hotListRepository: HotListRepository
) : ViewModel() {

    private val _state = MutableStateFlow(HotListState())
    val state: StateFlow<HotListState> = _state.asStateFlow()

    fun loadEntries(isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            if (isDemoMode) {
                _state.value = HotListState(entries = hotListRepository.getDemoEntries())
            } else {
                hotListRepository.getEntries().fold(
                    onSuccess = { entries ->
                        _state.value = HotListState(entries = entries)
                    },
                    onFailure = { e ->
                        _state.value = HotListState(error = e.message)
                    }
                )
            }
        }
    }

    fun deleteEntry(id: String, isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.value = _state.value.copy(
                entries = _state.value.entries.filter { it.id != id }
            )
            if (!isDemoMode) {
                hotListRepository.deleteEntry(id)
            }
        }
    }

    fun addEntry(plateText: String, vehicleInfo: String, isDemoMode: Boolean) {
        viewModelScope.launch {
            val newEntry = HotListEntry(
                id = "hl-${System.currentTimeMillis()}",
                plateText = plateText.uppercase(),
                plateState = null,
                caseNumber = null,
                lenderName = null,
                orderType = "repossession",
                vehicleYear = null,
                vehicleMake = vehicleInfo.ifBlank { null },
                vehicleModel = null,
                vehicleColor = null,
                vin = null,
                debtorName = null,
                debtorAddress = null,
                isActive = true,
                priority = "normal",
                notes = null,
                createdAt = java.time.Instant.now().toString(),
                updatedAt = java.time.Instant.now().toString(),
                expiresAt = null
            )
            _state.value = _state.value.copy(
                entries = listOf(newEntry) + _state.value.entries,
                showAddDialog = false
            )
            if (!isDemoMode) {
                hotListRepository.createEntry(
                    mapOf("plate_text" to plateText.uppercase(), "vehicle_make" to vehicleInfo)
                )
            }
        }
    }

    fun toggleAddDialog() {
        _state.value = _state.value.copy(showAddDialog = !_state.value.showAddDialog)
    }
}
