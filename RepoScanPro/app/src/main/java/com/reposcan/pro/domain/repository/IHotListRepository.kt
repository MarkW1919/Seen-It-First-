package com.reposcan.pro.domain.repository

import com.reposcan.pro.data.model.HotListAlert
import com.reposcan.pro.data.model.HotListEntry

interface IHotListRepository {
    suspend fun getEntries(activeOnly: Boolean = true): Result<List<HotListEntry>>
    suspend fun createEntry(data: Map<String, Any?>): Result<HotListEntry>
    suspend fun deleteEntry(id: String): Result<Unit>
    suspend fun getAlerts(status: String? = null): Result<List<HotListAlert>>
    suspend fun acknowledgeAlert(id: String): Result<HotListAlert>
    fun getDemoEntries(): List<HotListEntry>
    fun getDemoAlerts(): List<HotListAlert>
}
