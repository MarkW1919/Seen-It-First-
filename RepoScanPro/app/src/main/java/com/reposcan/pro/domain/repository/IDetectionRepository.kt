package com.reposcan.pro.domain.repository

import com.reposcan.pro.data.local.DetectionEntity
import com.reposcan.pro.data.model.DetectionList
import kotlinx.coroutines.flow.Flow

interface IDetectionRepository {
    fun getCachedDetections(limit: Int = 100): Flow<List<DetectionEntity>>
    fun searchCachedPlates(query: String): Flow<List<DetectionEntity>>
    suspend fun fetchDetections(page: Int = 1, pageSize: Int = 20): Result<DetectionList>
    suspend fun searchPlate(query: String, exact: Boolean = false): Result<DetectionList>
    fun getDemoDetections(): DetectionList
}
