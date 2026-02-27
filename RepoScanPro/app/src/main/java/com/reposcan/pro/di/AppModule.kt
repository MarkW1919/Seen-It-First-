package com.reposcan.pro.di

import android.content.Context
import androidx.room.Room
import com.reposcan.pro.data.local.AppDatabase
import com.reposcan.pro.data.local.DetectionDao
import com.reposcan.pro.util.PreferencesManager
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun providePreferencesManager(
        @ApplicationContext context: Context
    ): PreferencesManager {
        return PreferencesManager(context)
    }

    @Provides
    @Singleton
    fun provideDatabase(
        @ApplicationContext context: Context
    ): AppDatabase {
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "reposcan_db"
        ).build()
    }

    @Provides
    @Singleton
    fun provideDetectionDao(database: AppDatabase): DetectionDao {
        return database.detectionDao()
    }
}
