package com.reposcan.pro.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface DetectionDao {

    @Query("SELECT * FROM detections ORDER BY createdAt DESC LIMIT :limit")
    fun getRecentDetections(limit: Int = 100): Flow<List<DetectionEntity>>

    @Query("SELECT * FROM detections WHERE plateText LIKE '%' || :query || '%' ORDER BY createdAt DESC")
    fun searchByPlate(query: String): Flow<List<DetectionEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(detections: List<DetectionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(detection: DetectionEntity)

    @Query("DELETE FROM detections")
    suspend fun clearAll()

    @Query("SELECT COUNT(*) FROM detections")
    suspend fun count(): Int
}
