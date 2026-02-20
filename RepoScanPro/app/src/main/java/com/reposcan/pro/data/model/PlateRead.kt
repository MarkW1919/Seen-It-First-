package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class PlateRead(
    val id: String,
    @SerializedName("plate_text") val plateText: String,
    @SerializedName("plate_state") val plateState: String?,
    @SerializedName("plate_type") val plateType: String?,
    val confidence: Double,
    @SerializedName("plate_image_path") val plateImagePath: String?,
    @SerializedName("raw_ocr") val rawOcr: String?,
    @SerializedName("created_at") val createdAt: String
)
