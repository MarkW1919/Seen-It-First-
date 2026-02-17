package com.reposcan.pro.data.repository

import com.reposcan.pro.data.model.HotListAlert
import com.reposcan.pro.data.model.HotListEntry
import com.reposcan.pro.data.remote.ApiService
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class HotListRepository @Inject constructor(
    private val apiService: ApiService
) {

    suspend fun getEntries(activeOnly: Boolean = true): Result<List<HotListEntry>> {
        return try {
            val response = apiService.getHotListEntries(activeOnly)
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch hot list: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createEntry(data: Map<String, Any?>): Result<HotListEntry> {
        return try {
            val response = apiService.createHotListEntry(data)
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to create entry: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteEntry(id: String): Result<Unit> {
        return try {
            val response = apiService.deleteHotListEntry(id)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to delete entry: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getAlerts(status: String? = null): Result<List<HotListAlert>> {
        return try {
            val response = apiService.getAlerts(status)
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch alerts: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun acknowledgeAlert(id: String): Result<HotListAlert> {
        return try {
            val response = apiService.updateAlert(id, mapOf("status" to "acknowledged"))
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to acknowledge alert: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun getDemoEntries(): List<HotListEntry> {
        return listOf(
            HotListEntry(
                id = "hl-001", plateText = "ABC1234", plateState = "CA",
                caseNumber = "CASE-2024-0042", lenderName = "First National Bank",
                orderType = "repossession", vehicleYear = 2021, vehicleMake = "Toyota",
                vehicleModel = "Camry", vehicleColor = "Black", vin = "1HGBH41JXMN109186",
                debtorName = "John Smith", debtorAddress = "123 Main St, Los Angeles, CA 90012",
                isActive = true, priority = "high", notes = "Frequent location: downtown parking garage",
                createdAt = "2024-06-01T00:00:00Z", updatedAt = "2024-06-10T00:00:00Z",
                expiresAt = null
            ),
            HotListEntry(
                id = "hl-002", plateText = "XYZ9876", plateState = "CA",
                caseNumber = "CASE-2024-0089", lenderName = "Pacific Credit Union",
                orderType = "repossession", vehicleYear = 2020, vehicleMake = "Ford",
                vehicleModel = "F-150", vehicleColor = "White", vin = null,
                debtorName = "Jane Doe", debtorAddress = null,
                isActive = true, priority = "normal", notes = null,
                createdAt = "2024-06-05T00:00:00Z", updatedAt = "2024-06-05T00:00:00Z",
                expiresAt = null
            )
        )
    }

    fun getDemoAlerts(): List<HotListAlert> {
        return listOf(
            HotListAlert(
                id = "alert-001", hotlistEntryId = "hl-001", detectionId = "det-001",
                plateTextMatched = "ABC1234", matchConfidence = 0.98,
                latitude = 34.0522, longitude = -118.2437, address = "123 Main St, Los Angeles, CA",
                status = "new", acknowledgedAt = null, resolvedAt = null,
                notes = null, createdAt = "2024-06-15T14:30:00Z", hotlistEntry = null
            )
        )
    }
}
