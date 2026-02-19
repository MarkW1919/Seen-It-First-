package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.User
import com.reposcan.pro.domain.repository.IAuthRepository
import com.reposcan.pro.util.PreferencesManager
import javax.inject.Inject

class LoginUseCase @Inject constructor(
    private val authRepository: IAuthRepository,
    private val preferencesManager: PreferencesManager
) {
    suspend operator fun invoke(email: String, password: String): Result<User> {
        val loginResult = authRepository.login(email, password)
        return loginResult.fold(
            onSuccess = {
                authRepository.getMe().also { userResult ->
                    if (userResult.isSuccess) {
                        preferencesManager.setDemoMode(false)
                    }
                }
            },
            onFailure = { Result.failure(it) }
        )
    }
}
