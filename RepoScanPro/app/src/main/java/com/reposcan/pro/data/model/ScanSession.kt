package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class ScanSession(
    val id: String,
    @SerializedName("agent_id") val agentId: String,
    val name: String?,
    val status: String,
    @SerializedName("total_detections") val totalDetections: Int,
    @SerializedName("total_plates") val totalPlates: Int,
    @SerializedName("total_alerts") val totalAlerts: Int,
    @SerializedName("distance_miles") val distanceMiles: Double,
    @SerializedName("started_at") val startedAt: String,
    @SerializedName("ended_at") val endedAt: String?,
    val config: Map<String, Any>?
)
