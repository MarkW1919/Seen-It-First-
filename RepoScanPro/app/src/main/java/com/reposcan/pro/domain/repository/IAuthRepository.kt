package com.reposcan.pro.domain.repository

import com.reposcan.pro.data.model.TokenResponse
import com.reposcan.pro.data.model.User

interface IAuthRepository {
    suspend fun login(email: String, password: String): Result<TokenResponse>
    suspend fun getMe(): Result<User>
    suspend fun logout()
    fun getDemoUser(): User
    fun getDemoToken(): TokenResponse
}
