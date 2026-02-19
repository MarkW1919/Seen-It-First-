package com.reposcan.pro.data.repository

import com.reposcan.pro.data.model.LoginRequest
import com.reposcan.pro.data.model.TokenResponse
import com.reposcan.pro.data.model.User
import com.reposcan.pro.data.remote.ApiService
import com.reposcan.pro.domain.repository.IAuthRepository
import com.reposcan.pro.util.PreferencesManager
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val apiService: ApiService,
    private val preferencesManager: PreferencesManager
) : IAuthRepository {

    override suspend fun login(email: String, password: String): Result<TokenResponse> {
        return try {
            val response = apiService.login(LoginRequest(email, password))
            if (response.isSuccessful) {
                val token = response.body()!!
                preferencesManager.saveTokens(token.accessToken, token.refreshToken)
                Result.success(token)
            } else {
                Result.failure(Exception("Login failed: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getMe(): Result<User> {
        return try {
            val response = apiService.getMe()
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to get user: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun logout() {
        preferencesManager.clearTokens()
    }

    override fun getDemoUser(): User {
        return User(
            id = "demo-user-001",
            email = "demo@reposcan.pro",
            fullName = "Demo Agent",
            role = "agent",
            isActive = true,
            createdAt = "2024-01-01T00:00:00Z"
        )
    }

    override fun getDemoToken(): TokenResponse {
        return TokenResponse(
            accessToken = "demo-access-token",
            refreshToken = "demo-refresh-token",
            tokenType = "bearer"
        )
    }
}
