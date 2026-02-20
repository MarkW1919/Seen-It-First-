package com.reposcan.pro.ui.screens.settings

import androidx.compose.runtime.Immutable
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.domain.usecase.LogoutUseCase
import com.reposcan.pro.util.PreferencesManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@Immutable
data class SettingsState(
    val darkMode: Boolean = true,
    val alertSoundEnabled: Boolean = true,
    val alertVibrationEnabled: Boolean = true,
    val baseUrl: String = "",
    val isLoading: Boolean = true
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val preferencesManager: PreferencesManager,
    private val logoutUseCase: LogoutUseCase,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsState())
    val state: StateFlow<SettingsState> = _state.asStateFlow()

    init {
        loadSettings()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            _state.update {
                SettingsState(
                    darkMode = preferencesManager.darkMode.first(),
                    alertSoundEnabled = preferencesManager.alertSound.first(),
                    alertVibrationEnabled = preferencesManager.alertVibration.first(),
                    baseUrl = preferencesManager.baseUrl.first(),
                    isLoading = false
                )
            }
        }
    }

    fun setDarkMode(enabled: Boolean) {
        _state.update { it.copy(darkMode = enabled) }
        viewModelScope.launch {
            preferencesManager.setDarkMode(enabled)
        }
    }

    fun setAlertSound(enabled: Boolean) {
        _state.update { it.copy(alertSoundEnabled = enabled) }
        viewModelScope.launch {
            preferencesManager.setAlertSound(enabled)
        }
    }

    fun setAlertVibration(enabled: Boolean) {
        _state.update { it.copy(alertVibrationEnabled = enabled) }
        viewModelScope.launch {
            preferencesManager.setAlertVibration(enabled)
        }
    }

    fun setBaseUrl(url: String) {
        _state.update { it.copy(baseUrl = url) }
        viewModelScope.launch {
            preferencesManager.setBaseUrl(url)
        }
    }

    fun logout(onLogout: () -> Unit) {
        viewModelScope.launch {
            logoutUseCase()
            onLogout()
        }
    }
}
