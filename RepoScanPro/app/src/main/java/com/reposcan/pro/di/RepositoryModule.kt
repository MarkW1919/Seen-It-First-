package com.reposcan.pro.di

import com.reposcan.pro.data.repository.AuthRepository
import com.reposcan.pro.data.repository.DetectionRepository
import com.reposcan.pro.data.repository.HotListRepository
import com.reposcan.pro.domain.repository.IAuthRepository
import com.reposcan.pro.domain.repository.IDetectionRepository
import com.reposcan.pro.domain.repository.IHotListRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindAuthRepository(impl: AuthRepository): IAuthRepository

    @Binds
    @Singleton
    abstract fun bindDetectionRepository(impl: DetectionRepository): IDetectionRepository

    @Binds
    @Singleton
    abstract fun bindHotListRepository(impl: HotListRepository): IHotListRepository
}
