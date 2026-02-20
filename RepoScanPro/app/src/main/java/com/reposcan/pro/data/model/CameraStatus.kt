package com.reposcan.pro.data.model

import com.google.gson.annotations.SerializedName

data class CameraStatus(
    @SerializedName("is_connected") val isConnected: Boolean = false,
    val resolution: String = "1920x1080",
    val fps: Double = 0.0,
    @SerializedName("night_mode") val nightMode: Boolean = false,
    @SerializedName("ir_enabled") val irEnabled: Boolean = false,
    @SerializedName("ptz_position") val ptzPosition: PtzPosition = PtzPosition(),
    val streaming: Boolean = false,
    @SerializedName("rtsp_url") val rtspUrl: String? = null
)

data class PtzPosition(
    val pan: Double = 0.0,
    val tilt: Double = 0.0,
    val zoom: Double = 1.0
)

data class SystemStats(
    @SerializedName("cpu_percent") val cpuPercent: Double = 0.0,
    @SerializedName("memory_used_mb") val memoryUsedMb: Double = 0.0,
    @SerializedName("memory_total_mb") val memoryTotalMb: Double = 0.0,
    @SerializedName("gpu_temp_c") val gpuTempC: Double = 0.0,
    @SerializedName("gpu_utilization") val gpuUtilization: Double = 0.0
)
