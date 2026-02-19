package com.reposcan.pro.ui.screens.alerts

import androidx.compose.runtime.Immutable
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.HotListAlert
import com.reposcan.pro.domain.usecase.GetAlertsUseCase
import com.reposcan.pro.domain.usecase.ManageHotListUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@Immutable
data class AlertsState(
    val alerts: List<HotListAlert> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class AlertsViewModel @Inject constructor(
    private val getAlertsUseCase: GetAlertsUseCase,
    private val manageHotListUseCase: ManageHotListUseCase,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _state = MutableStateFlow(AlertsState())
    val state: StateFlow<AlertsState> = _state.asStateFlow()

    fun loadAlerts(isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            getAlertsUseCase(isDemoMode).fold(
                onSuccess = { alerts ->
                    _state.update { AlertsState(alerts = alerts) }
                },
                onFailure = { e ->
                    _state.update { AlertsState(error = e.message ?: "Failed to load alerts") }
                }
            )
        }
    }

    fun acknowledgeAlert(id: String) {
        _state.update { current ->
            current.copy(
                alerts = current.alerts.map { alert ->
                    if (alert.id == id) alert.copy(status = "acknowledged") else alert
                }
            )
        }
        viewModelScope.launch {
            manageHotListUseCase.acknowledgeAlert(id)
        }
    }

    fun dismissAlert(id: String) {
        _state.update { current ->
            current.copy(alerts = current.alerts.filter { it.id != id })
        }
    }
}
