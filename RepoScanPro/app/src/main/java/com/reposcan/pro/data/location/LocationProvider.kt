package com.reposcan.pro.data.location

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.Looper
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.reposcan.pro.data.model.LocationState
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LocationProvider @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val fusedClient = LocationServices.getFusedLocationProviderClient(context)

    private val _location = MutableStateFlow(LocationState())
    val location: StateFlow<LocationState> = _location.asStateFlow()

    private var locationCallback: LocationCallback? = null
    private var kalmanLat = KalmanFilter1D(processNoise = 1e-5, measurementNoise = 1e-4)
    private var kalmanLng = KalmanFilter1D(processNoise = 1e-5, measurementNoise = 1e-4)
    private var lastSmoothedHeading = 0f
    private var isHighAccuracy = false

    // Jitter filter: reject teleportation glitches
    private var lastValidLocation: Location? = null
    private val maxJumpMeters = 100.0

    @SuppressLint("MissingPermission")
    fun startUpdates(highAccuracy: Boolean = false) {
        stopUpdates()
        isHighAccuracy = highAccuracy

        val request = LocationRequest.Builder(
            if (highAccuracy) Priority.PRIORITY_HIGH_ACCURACY
            else Priority.PRIORITY_BALANCED_POWER_ACCURACY,
            if (highAccuracy) 1_000L else 3_000L
        ).apply {
            setMinUpdateIntervalMillis(if (highAccuracy) 500L else 2_000L)
            setMaxUpdateDelayMillis(if (highAccuracy) 2_000L else 5_000L)
            setMinUpdateDistanceMeters(if (highAccuracy) 1f else 5f)
        }.build()

        val callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val loc = result.lastLocation ?: return
                processLocation(loc)
            }
        }
        locationCallback = callback
        fusedClient.requestLocationUpdates(request, callback, Looper.getMainLooper())
        _location.update { it.copy(isActive = true) }
    }

    fun stopUpdates() {
        locationCallback?.let { fusedClient.removeLocationUpdates(it) }
        locationCallback = null
        _location.update { it.copy(isActive = false) }
    }

    @SuppressLint("MissingPermission")
    fun switchToHighAccuracy() {
        if (locationCallback != null && !isHighAccuracy) {
            startUpdates(highAccuracy = true)
        }
    }

    @SuppressLint("MissingPermission")
    fun switchToBalancedPower() {
        if (locationCallback != null && isHighAccuracy) {
            startUpdates(highAccuracy = false)
        }
    }

    private fun processLocation(location: Location) {
        // Jitter filter: reject impossible jumps (GPS glitches)
        lastValidLocation?.let { prev ->
            val timeDeltaS = (location.time - prev.time) / 1000.0
            if (timeDeltaS > 0) {
                val distance = prev.distanceTo(location)
                if (distance > maxJumpMeters && timeDeltaS < 1.0) {
                    return // Reject — impossible speed
                }
            }
        }
        lastValidLocation = location

        // Kalman filter for smooth coordinates
        val filteredLat = kalmanLat.update(location.latitude)
        val filteredLng = kalmanLng.update(location.longitude)

        // Heading smoothing (handles 0/360 wraparound)
        val rawHeading = if (location.hasBearing()) location.bearing else lastSmoothedHeading
        lastSmoothedHeading = smoothHeading(rawHeading, lastSmoothedHeading)

        _location.update {
            LocationState(
                latitude = filteredLat,
                longitude = filteredLng,
                accuracy = location.accuracy,
                heading = lastSmoothedHeading,
                speed = location.speed,
                isActive = true,
                lastUpdateMs = location.time
            )
        }
    }

    private fun smoothHeading(raw: Float, previous: Float): Float {
        var diff = raw - previous
        if (diff > 180f) diff -= 360f
        if (diff < -180f) diff += 360f
        return (previous + diff * 0.3f).mod(360f)
    }
}

/**
 * Simple 1D Kalman filter for smoothing GPS coordinates.
 *
 * @param processNoise Q — how much the actual value drifts per update
 * @param measurementNoise R — expected GPS measurement noise
 */
private class KalmanFilter1D(
    private val processNoise: Double,
    private val measurementNoise: Double,
) {
    private var estimate = 0.0
    private var errorCovariance = 1.0
    private var initialized = false

    fun update(measurement: Double): Double {
        if (!initialized) {
            estimate = measurement
            initialized = true
            return estimate
        }
        // Prediction step
        val predictionError = errorCovariance + processNoise
        // Update step
        val kalmanGain = predictionError / (predictionError + measurementNoise)
        estimate += kalmanGain * (measurement - estimate)
        errorCovariance = (1 - kalmanGain) * predictionError
        return estimate
    }
}
