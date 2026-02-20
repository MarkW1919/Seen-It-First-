package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class HotListAlert(
    val id: String,
    @SerializedName("hotlist_entry_id") val hotlistEntryId: String,
    @SerializedName("detection_id") val detectionId: String?,
    @SerializedName("plate_text_matched") val plateTextMatched: String,
    @SerializedName("match_confidence") val matchConfidence: Double,
    val latitude: Double?,
    val longitude: Double?,
    val address: String?,
    val status: String,
    @SerializedName("acknowledged_at") val acknowledgedAt: String?,
    @SerializedName("resolved_at") val resolvedAt: String?,
    val notes: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("hotlist_entry") val hotlistEntry: HotListEntry?
)
