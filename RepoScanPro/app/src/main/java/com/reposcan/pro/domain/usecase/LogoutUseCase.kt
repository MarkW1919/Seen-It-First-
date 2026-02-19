package com.reposcan.pro.domain.usecase

import com.reposcan.pro.domain.repository.IAuthRepository
import javax.inject.Inject

class LogoutUseCase @Inject constructor(
    private val authRepository: IAuthRepository
) {
    suspend operator fun invoke() {
        authRepository.logout()
    }
}
