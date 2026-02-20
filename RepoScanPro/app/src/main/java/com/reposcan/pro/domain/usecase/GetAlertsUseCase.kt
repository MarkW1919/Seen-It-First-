package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.HotListAlert
import com.reposcan.pro.domain.repository.IHotListRepository
import javax.inject.Inject

class GetAlertsUseCase @Inject constructor(
    private val hotListRepository: IHotListRepository
) {
    suspend operator fun invoke(isDemoMode: Boolean): Result<List<HotListAlert>> {
        return if (isDemoMode) {
            Result.success(hotListRepository.getDemoAlerts())
        } else {
            hotListRepository.getAlerts()
        }
    }
}
