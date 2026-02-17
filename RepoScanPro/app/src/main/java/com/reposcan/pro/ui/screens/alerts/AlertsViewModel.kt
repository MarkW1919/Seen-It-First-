package com.reposcan.pro.ui.screens.alerts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.HotListAlert
import com.reposcan.pro.data.repository.HotListRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AlertsState(
    val alerts: List<HotListAlert> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class AlertsViewModel @Inject constructor(
    private val hotListRepository: HotListRepository
) : ViewModel() {

    private val _state = MutableStateFlow(AlertsState())
    val state: StateFlow<AlertsState> = _state.asStateFlow()

    fun loadAlerts(isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            if (isDemoMode) {
                _state.value = AlertsState(alerts = hotListRepository.getDemoAlerts())
            } else {
                hotListRepository.getAlerts().fold(
                    onSuccess = { alerts ->
                        _state.value = AlertsState(alerts = alerts)
                    },
                    onFailure = { e ->
                        _state.value = AlertsState(error = e.message)
                    }
                )
            }
        }
    }

    fun acknowledgeAlert(id: String) {
        viewModelScope.launch {
            val updated = _state.value.alerts.map { alert ->
                if (alert.id == id) alert.copy(status = "acknowledged") else alert
            }
            _state.value = _state.value.copy(alerts = updated)
            hotListRepository.acknowledgeAlert(id)
        }
    }

    fun dismissAlert(id: String) {
        _state.value = _state.value.copy(
            alerts = _state.value.alerts.filter { it.id != id }
        )
    }
}
