package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class HotListEntry(
    val id: String,
    @SerializedName("plate_text") val plateText: String,
    @SerializedName("plate_state") val plateState: String?,
    @SerializedName("case_number") val caseNumber: String?,
    @SerializedName("lender_name") val lenderName: String?,
    @SerializedName("order_type") val orderType: String,
    @SerializedName("vehicle_year") val vehicleYear: Int?,
    @SerializedName("vehicle_make") val vehicleMake: String?,
    @SerializedName("vehicle_model") val vehicleModel: String?,
    @SerializedName("vehicle_color") val vehicleColor: String?,
    val vin: String?,
    @SerializedName("debtor_name") val debtorName: String?,
    @SerializedName("debtor_address") val debtorAddress: String?,
    @SerializedName("is_active") val isActive: Boolean,
    val priority: String,
    val notes: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("expires_at") val expiresAt: String?
)
