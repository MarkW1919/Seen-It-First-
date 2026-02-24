package com.reposcan.pro.domain.navigation

import android.location.Location
import com.reposcan.pro.data.location.LocationProvider
import com.reposcan.pro.data.model.RouteStopResponse
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ArrivalDetector @Inject constructor(
    private val locationProvider: LocationProvider
) {
    companion object {
        const val SPEED_THRESHOLD_MPS = 4.47f   // ~10 mph — must be slow
        const val DWELL_TIME_MS = 5_000L         // Must stay in geofence 5s
        const val ARRIVAL_COOLDOWN_MS = 300_000L // 5 min cooldown per stop
        const val MAX_GPS_ACCURACY_M = 50f       // Reject inaccurate fixes
    }

    data class ArrivalEvent(
        val stopId: String,
        val stopIndex: Int,
        val address: String,
        val latitude: Double,
        val longitude: Double,
        val distanceM: Float
    )

    private val _arrivalEvents = MutableSharedFlow<ArrivalEvent>(replay = 0)
    val arrivalEvents: SharedFlow<ArrivalEvent> = _arrivalEvents

    // Cooldown tracking: stopId -> arrival timestamp
    private val arrivedStopTimestamps = mutableMapOf<String, Long>()

    // Dwell tracking
    private var dwellStartMs = 0L
    private var dwellStopId: String? = null
    private var monitorJob: Job? = null

    fun startMonitoring(
        stops: List<RouteStopResponse>,
        currentIndex: Int,
        scope: CoroutineScope
    ) {
        stopMonitoring()
        monitorJob = scope.launch {
            locationProvider.location.collect { loc ->
                if (!loc.isActive || loc.accuracy > MAX_GPS_ACCURACY_M) return@collect

                // Find current target stop
                val target = stops.getOrNull(currentIndex) ?: return@collect
                if (target.status in listOf("completed", "skipped")) return@collect

                val distanceM = distanceBetween(
                    loc.latitude, loc.longitude,
                    target.latitude, target.longitude
                )

                val inGeofence = distanceM <= target.geofenceRadiusM
                val slowEnough = loc.speed < SPEED_THRESHOLD_MPS
                val notOnCooldown = !isOnCooldown(target.id)

                if (inGeofence && slowEnough && notOnCooldown) {
                    // Start or continue dwell timer
                    if (dwellStopId != target.id) {
                        dwellStopId = target.id
                        dwellStartMs = System.currentTimeMillis()
                    }

                    val dwellElapsed = System.currentTimeMillis() - dwellStartMs
                    if (dwellElapsed >= DWELL_TIME_MS) {
                        // Arrival confirmed
                        arrivedStopTimestamps[target.id] = System.currentTimeMillis()
                        dwellStopId = null
                        _arrivalEvents.emit(
                            ArrivalEvent(
                                stopId = target.id,
                                stopIndex = target.orderIndex,
                                address = target.address,
                                latitude = target.latitude,
                                longitude = target.longitude,
                                distanceM = distanceM
                            )
                        )
                    }
                } else {
                    // Left geofence or moving too fast — reset dwell
                    if (dwellStopId == target.id) {
                        dwellStopId = null
                    }
                }
            }
        }
    }

    fun stopMonitoring() {
        monitorJob?.cancel()
        monitorJob = null
        dwellStopId = null
    }

    fun clearCooldowns() {
        arrivedStopTimestamps.clear()
    }

    private fun isOnCooldown(stopId: String): Boolean {
        val lastArrival = arrivedStopTimestamps[stopId] ?: return false
        return System.currentTimeMillis() - lastArrival < ARRIVAL_COOLDOWN_MS
    }

    private fun distanceBetween(
        lat1: Double, lng1: Double,
        lat2: Double, lng2: Double
    ): Float {
        val results = FloatArray(1)
        Location.distanceBetween(lat1, lng1, lat2, lng2, results)
        return results[0]
    }
}
