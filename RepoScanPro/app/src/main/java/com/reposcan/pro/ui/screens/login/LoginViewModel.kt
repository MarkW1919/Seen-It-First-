package com.reposcan.pro.ui.screens.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.User
import com.reposcan.pro.data.repository.AuthRepository
import com.reposcan.pro.util.PreferencesManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val user: User? = null,
    val isDemoMode: Boolean = false
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val preferencesManager: PreferencesManager
) : ViewModel() {

    private val _state = MutableStateFlow(LoginState())
    val state: StateFlow<LoginState> = _state.asStateFlow()

    fun login(email: String, password: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            val result = authRepository.login(email, password)
            result.fold(
                onSuccess = {
                    val userResult = authRepository.getMe()
                    userResult.fold(
                        onSuccess = { user ->
                            preferencesManager.setDemoMode(false)
                            _state.value = _state.value.copy(
                                isLoading = false,
                                user = user,
                                isDemoMode = false
                            )
                        },
                        onFailure = { e ->
                            _state.value = _state.value.copy(
                                isLoading = false,
                                error = e.message ?: "Failed to get user info"
                            )
                        }
                    )
                },
                onFailure = { e ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = e.message ?: "Login failed"
                    )
                }
            )
        }
    }

    fun enterDemoMode() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            preferencesManager.setDemoMode(true)
            val demoUser = authRepository.getDemoUser()
            val demoToken = authRepository.getDemoToken()
            preferencesManager.saveTokens(demoToken.accessToken, demoToken.refreshToken)
            _state.value = _state.value.copy(
                isLoading = false,
                user = demoUser,
                isDemoMode = true
            )
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }
}
