package com.reposcan.pro.data.repository

import com.reposcan.pro.data.local.DetectionDao
import com.reposcan.pro.data.local.DetectionEntity
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.data.model.DetectionList
import com.reposcan.pro.data.model.PlateRead
import com.reposcan.pro.data.remote.ApiService
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DetectionRepository @Inject constructor(
    private val apiService: ApiService,
    private val detectionDao: DetectionDao
) {

    fun getCachedDetections(limit: Int = 100): Flow<List<DetectionEntity>> {
        return detectionDao.getRecentDetections(limit)
    }

    fun searchCachedPlates(query: String): Flow<List<DetectionEntity>> {
        return detectionDao.searchByPlate(query)
    }

    suspend fun fetchDetections(page: Int = 1, pageSize: Int = 20): Result<DetectionList> {
        return try {
            val response = apiService.getDetections(page, pageSize)
            if (response.isSuccessful) {
                val detectionList = response.body()!!
                cacheDetections(detectionList.items)
                Result.success(detectionList)
            } else {
                Result.failure(Exception("Failed to fetch detections: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun searchPlate(query: String, exact: Boolean = false): Result<DetectionList> {
        return try {
            val response = apiService.searchPlate(query, exact)
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Search failed: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private suspend fun cacheDetections(detections: List<Detection>) {
        val entities = detections.map { det ->
            val firstPlate = det.plateReads.firstOrNull()
            DetectionEntity(
                id = det.id,
                vehicleType = det.vehicleType,
                vehicleColor = det.vehicleColor,
                vehicleMake = det.vehicleMake,
                vehicleModel = det.vehicleModel,
                vehicleYear = det.vehicleYear,
                vehicleConfidence = det.vehicleConfidence,
                latitude = det.latitude,
                longitude = det.longitude,
                address = det.address,
                plateText = firstPlate?.plateText,
                plateConfidence = firstPlate?.confidence,
                imagePath = det.imagePath,
                createdAt = det.createdAt
            )
        }
        detectionDao.insertAll(entities)
    }

    fun getDemoDetections(): DetectionList {
        val detections = listOf(
            Detection(
                id = "det-001", agentId = "demo-user-001", sessionId = null,
                vehicleType = "car", vehicleColor = "Black", vehicleMake = "Toyota",
                vehicleModel = "Camry", vehicleYear = 2021, vehicleConfidence = 0.95,
                imagePath = null, thumbnailPath = null,
                latitude = 34.0522, longitude = -118.2437, address = "123 Main St, Los Angeles, CA",
                heading = 180.0, speed = 35.0, extra = null,
                createdAt = "2024-06-15T14:30:00Z",
                plateReads = listOf(
                    PlateRead("pr-001", "ABC1234", "CA", "standard", 0.97, null, "ABC1234", "2024-06-15T14:30:00Z")
                )
            ),
            Detection(
                id = "det-002", agentId = "demo-user-001", sessionId = null,
                vehicleType = "truck", vehicleColor = "White", vehicleMake = "Ford",
                vehicleModel = "F-150", vehicleYear = 2020, vehicleConfidence = 0.92,
                imagePath = null, thumbnailPath = null,
                latitude = 34.0535, longitude = -118.2450, address = "456 Oak Ave, Los Angeles, CA",
                heading = 90.0, speed = 25.0, extra = null,
                createdAt = "2024-06-15T14:25:00Z",
                plateReads = listOf(
                    PlateRead("pr-002", "XYZ9876", "CA", "standard", 0.94, null, "XYZ9876", "2024-06-15T14:25:00Z")
                )
            ),
            Detection(
                id = "det-003", agentId = "demo-user-001", sessionId = null,
                vehicleType = "suv", vehicleColor = "Silver", vehicleMake = "Honda",
                vehicleModel = "CR-V", vehicleYear = 2022, vehicleConfidence = 0.89,
                imagePath = null, thumbnailPath = null,
                latitude = 34.0510, longitude = -118.2420, address = "789 Elm Blvd, Los Angeles, CA",
                heading = 270.0, speed = 40.0, extra = null,
                createdAt = "2024-06-15T14:20:00Z",
                plateReads = listOf(
                    PlateRead("pr-003", "DEF5678", "NV", "standard", 0.91, null, "DEF5678", "2024-06-15T14:20:00Z")
                )
            )
        )
        return DetectionList(items = detections, total = detections.size, page = 1, pageSize = 20)
    }
}
