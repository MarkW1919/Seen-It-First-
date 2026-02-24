package com.reposcan.pro.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [DetectionEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun detectionDao(): DetectionDao
}
