package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class User(
    val id: String,
    val email: String,
    @SerializedName("full_name") val fullName: String,
    val role: String,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("created_at") val createdAt: String
)
