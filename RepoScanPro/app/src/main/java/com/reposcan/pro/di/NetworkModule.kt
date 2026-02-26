package com.reposcan.pro.di

import com.reposcan.pro.BuildConfig
import com.reposcan.pro.data.remote.ApiService
import com.reposcan.pro.data.remote.AuthInterceptor
import com.reposcan.pro.util.Constants
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient {
        val builder = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)

        // Only log HTTP traffic in debug builds — BODY level leaks auth tokens
        if (BuildConfig.DEBUG) {
            val logging = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.HEADERS
            }
            builder.addInterceptor(logging)
        }

        // Certificate pinning for production — prevents MITM attacks.
        // Pins are SHA-256 hashes of the server's public key.
        // FIXME: Enable certificate pinning before production release.
        //        Generate pins with: openssl s_client -connect <host>:443 | openssl x509 -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | openssl enc -base64
        //        Then uncomment the block below and replace the placeholder hashes.
        // if (!BuildConfig.DEBUG) {
        //     val pinner = CertificatePinner.Builder()
        //         .add(Constants.API_HOST, "sha256/<primary-pin-here>")
        //         .add(Constants.API_HOST, "sha256/<backup-pin-here>")
        //         .build()
        //     builder.certificatePinner(pinner)
        // }

        return builder.build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(Constants.DEFAULT_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): ApiService {
        return retrofit.create(ApiService::class.java)
    }
}
