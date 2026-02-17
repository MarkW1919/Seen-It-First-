package com.reposcan.pro.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.repository.AuthRepository
import com.reposcan.pro.util.PreferencesManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsState(
    val darkMode: Boolean = true,
    val alertSoundEnabled: Boolean = true,
    val alertVibrationEnabled: Boolean = true,
    val baseUrl: String = ""
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val preferencesManager: PreferencesManager,
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsState())
    val state: StateFlow<SettingsState> = _state.asStateFlow()

    init {
        loadSettings()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            _state.value = SettingsState(
                darkMode = preferencesManager.darkMode.first(),
                alertSoundEnabled = preferencesManager.alertSound.first(),
                alertVibrationEnabled = preferencesManager.alertVibration.first(),
                baseUrl = preferencesManager.baseUrl.first()
            )
        }
    }

    fun setDarkMode(enabled: Boolean) {
        viewModelScope.launch {
            preferencesManager.setDarkMode(enabled)
            _state.value = _state.value.copy(darkMode = enabled)
        }
    }

    fun setAlertSound(enabled: Boolean) {
        viewModelScope.launch {
            preferencesManager.setAlertSound(enabled)
            _state.value = _state.value.copy(alertSoundEnabled = enabled)
        }
    }

    fun setAlertVibration(enabled: Boolean) {
        viewModelScope.launch {
            preferencesManager.setAlertVibration(enabled)
            _state.value = _state.value.copy(alertVibrationEnabled = enabled)
        }
    }

    fun setBaseUrl(url: String) {
        viewModelScope.launch {
            preferencesManager.setBaseUrl(url)
            _state.value = _state.value.copy(baseUrl = url)
        }
    }

    fun logout(onLogout: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLogout()
        }
    }
}
