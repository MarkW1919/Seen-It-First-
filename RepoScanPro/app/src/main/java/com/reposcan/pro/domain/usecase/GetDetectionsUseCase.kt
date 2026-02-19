package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.DetectionList
import com.reposcan.pro.domain.repository.IDetectionRepository
import javax.inject.Inject

class GetDetectionsUseCase @Inject constructor(
    private val detectionRepository: IDetectionRepository
) {
    suspend operator fun invoke(
        isDemoMode: Boolean,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<DetectionList> {
        return if (isDemoMode) {
            Result.success(detectionRepository.getDemoDetections())
        } else {
            detectionRepository.fetchDetections(page, pageSize)
        }
    }
}
