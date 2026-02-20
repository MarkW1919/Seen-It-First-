package com.reposcan.pro.domain.usecase

import com.reposcan.pro.data.model.HotListEntry
import com.reposcan.pro.domain.repository.IHotListRepository
import javax.inject.Inject

class GetHotListEntriesUseCase @Inject constructor(
    private val hotListRepository: IHotListRepository
) {
    suspend operator fun invoke(isDemoMode: Boolean): Result<List<HotListEntry>> {
        return if (isDemoMode) {
            Result.success(hotListRepository.getDemoEntries())
        } else {
            hotListRepository.getEntries()
        }
    }
}
