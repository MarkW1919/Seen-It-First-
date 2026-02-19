package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.domain.repository.IDetectionRepository
import javax.inject.Inject

class SearchPlateUseCase @Inject constructor(
    private val detectionRepository: IDetectionRepository
) {
    suspend operator fun invoke(query: String, isDemoMode: Boolean): Result<List<Detection>> {
        val normalizedQuery = query.trim().uppercase()
        if (normalizedQuery.isBlank()) return Result.success(emptyList())

        return if (isDemoMode) {
            val all = detectionRepository.getDemoDetections().items
            val filtered = all.filter { det ->
                det.plateReads.any { it.plateText.contains(normalizedQuery) }
            }
            Result.success(filtered)
        } else {
            detectionRepository.searchPlate(normalizedQuery).map { it.items }
        }
    }
}
