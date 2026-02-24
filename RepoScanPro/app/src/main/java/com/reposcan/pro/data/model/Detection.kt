package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class Detection(
    val id: String,
    @SerializedName("agent_id") val agentId: String?,
    @SerializedName("session_id") val sessionId: String?,
    @SerializedName("vehicle_type") val vehicleType: String?,
    @SerializedName("vehicle_color") val vehicleColor: String?,
    @SerializedName("vehicle_make") val vehicleMake: String?,
    @SerializedName("vehicle_model") val vehicleModel: String?,
    @SerializedName("vehicle_year") val vehicleYear: Int?,
    @SerializedName("vehicle_confidence") val vehicleConfidence: Double?,
    @SerializedName("image_path") val imagePath: String?,
    @SerializedName("thumbnail_path") val thumbnailPath: String?,
    val latitude: Double?,
    val longitude: Double?,
    val address: String?,
    val heading: Double?,
    val speed: Double?,
    val extra: Map<String, Any>?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("plate_reads") val plateReads: List<PlateRead>
)

data class DetectionList(
    val items: List<Detection>,
    val total: Int,
    val page: Int,
    @SerializedName("page_size") val pageSize: Int
)
