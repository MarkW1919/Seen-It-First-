package com.reposcan.pro.util

import android.location.Location

/**
 * Shared geolocation utilities.
 *
 * Consolidates the distance calculation that was previously duplicated
 * in ArrivalDetector, AutoScanController, and MapScreen.
 */
object GeoUtils {

    /**
     * Compute the distance in meters between two lat/lng points.
     */
    fun distanceBetween(
        lat1: Double, lng1: Double,
        lat2: Double, lng2: Double
    ): Float {
        val results = FloatArray(1)
        Location.distanceBetween(lat1, lng1, lat2, lng2, results)
        return results[0]
    }
}
