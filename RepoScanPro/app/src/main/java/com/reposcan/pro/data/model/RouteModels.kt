package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class RouteResponse(
    val id: String,
    val name: String?,
    val status: String,
    @SerializedName("current_stop_index") val currentStopIndex: Int,
    @SerializedName("total_stops") val totalStops: Int,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("completed_at") val completedAt: String?,
    val stops: List<RouteStopResponse>
)

data class RouteStopResponse(
    val id: String,
    @SerializedName("order_index") val orderIndex: Int,
    val address: String,
    val latitude: Double,
    val longitude: Double,
    @SerializedName("geofence_radius_m") val geofenceRadiusM: Double,
    val status: String,
    @SerializedName("arrived_at") val arrivedAt: String?,
    @SerializedName("scan_started_at") val scanStartedAt: String?,
    @SerializedName("completed_at") val completedAt: String?,
    @SerializedName("plates_found") val platesFound: Int,
    val notes: String?
)

data class RouteCreateRequest(
    val name: String?,
    val stops: List<StopCreateRequest>
)

data class StopCreateRequest(
    val address: String,
    val latitude: Double,
    val longitude: Double,
    @SerializedName("geofence_radius_m") val geofenceRadiusM: Double = 50.0
)

data class LocationState(
    val latitude: Double = 0.0,
    val longitude: Double = 0.0,
    val accuracy: Float = Float.MAX_VALUE,
    val heading: Float = 0f,
    val speed: Float = 0f,
    val isActive: Boolean = false,
    val lastUpdateMs: Long = 0L
)
