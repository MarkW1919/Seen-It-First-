package com.reposcan.pro.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "detections")
data class DetectionEntity(
    @PrimaryKey val id: String,
    val vehicleType: String?,
    val vehicleColor: String?,
    val vehicleMake: String?,
    val vehicleModel: String?,
    val vehicleYear: Int?,
    val vehicleConfidence: Double?,
    val latitude: Double?,
    val longitude: Double?,
    val address: String?,
    val plateText: String?,
    val plateConfidence: Double?,
    val imagePath: String?,
    val createdAt: String
)
