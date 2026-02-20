package com.reposcan.pro.data.remote

import com.reposcan.pro.util.PreferencesManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import okhttp3.Interceptor
import okhttp3.Response
import java.util.concurrent.atomic.AtomicReference
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    preferencesManager: PreferencesManager
) : Interceptor {

    private val cachedToken = AtomicReference<String?>(null)

    init {
        preferencesManager.accessToken
            .onEach { cachedToken.set(it) }
            .launchIn(CoroutineScope(SupervisorJob() + Dispatchers.IO))
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = cachedToken.get()
        val request = if (!token.isNullOrBlank()) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}
