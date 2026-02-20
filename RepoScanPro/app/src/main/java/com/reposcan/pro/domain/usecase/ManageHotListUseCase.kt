package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.HotListEntry
import com.reposcan.pro.domain.repository.IHotListRepository
import javax.inject.Inject

class ManageHotListUseCase @Inject constructor(
    private val hotListRepository: IHotListRepository
) {
    suspend fun addEntry(
        plateText: String,
        vehicleInfo: String,
        isDemoMode: Boolean
    ): Result<HotListEntry> {
        val entry = HotListEntry(
            id = "hl-${System.currentTimeMillis()}",
            plateText = plateText.uppercase(),
            plateState = null,
            caseNumber = null,
            lenderName = null,
            orderType = "repossession",
            vehicleYear = null,
            vehicleMake = vehicleInfo.ifBlank { null },
            vehicleModel = null,
            vehicleColor = null,
            vin = null,
            debtorName = null,
            debtorAddress = null,
            isActive = true,
            priority = "normal",
            notes = null,
            createdAt = java.time.Instant.now().toString(),
            updatedAt = java.time.Instant.now().toString(),
            expiresAt = null
        )

        if (!isDemoMode) {
            hotListRepository.createEntry(
                mapOf("plate_text" to plateText.uppercase(), "vehicle_make" to vehicleInfo)
            )
        }

        return Result.success(entry)
    }

    suspend fun deleteEntry(id: String, isDemoMode: Boolean): Result<Unit> {
        return if (!isDemoMode) {
            hotListRepository.deleteEntry(id)
        } else {
            Result.success(Unit)
        }
    }

    suspend fun acknowledgeAlert(id: String): Result<Unit> {
        return hotListRepository.acknowledgeAlert(id).map { }
    }
}
