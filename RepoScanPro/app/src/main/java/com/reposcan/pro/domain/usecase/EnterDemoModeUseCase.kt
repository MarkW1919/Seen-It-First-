package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.User
import com.reposcan.pro.domain.repository.IAuthRepository
import com.reposcan.pro.util.PreferencesManager
import javax.inject.Inject

class EnterDemoModeUseCase @Inject constructor(
    private val authRepository: IAuthRepository,
    private val preferencesManager: PreferencesManager
) {
    suspend operator fun invoke(): User {
        preferencesManager.setDemoMode(true)
        val demoToken = authRepository.getDemoToken()
        preferencesManager.saveTokens(demoToken.accessToken, demoToken.refreshToken)
        return authRepository.getDemoUser()
    }
}
