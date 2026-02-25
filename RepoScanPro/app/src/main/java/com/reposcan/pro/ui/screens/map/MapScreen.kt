package com.reposcan.pro.ui.screens.map

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Navigation
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.data.model.RouteStopResponse
import com.reposcan.pro.ui.theme.Blue400
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Navy800
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.Slate400
import com.reposcan.pro.ui.theme.Yellow400

@Composable
fun MapScreen(
    isDemoMode: Boolean,
    viewModel: MapViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    // Location permission launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val fine = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true
        val coarse = permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (fine || coarse) {
            viewModel.onLocationPermissionGranted()
        }
    }

    LaunchedEffect(Unit) {
        viewModel.loadDetections(isDemoMode)
        if (!isDemoMode) viewModel.loadActiveRoute()

        val hasFine = ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        val hasCoarse = ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (hasFine || hasCoarse) {
            viewModel.onLocationPermissionGranted()
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }

    DisposableEffect(Unit) {
        onDispose { viewModel.stopNavigation() }
    }

    MapContent(
        state = state,
        onRetry = { viewModel.loadDetections(isDemoMode) },
        onStartNavigation = { viewModel.startNavigation() },
        onStopNavigation = { viewModel.stopNavigation() },
        onToggleAutoScan = { viewModel.toggleAutoScan() },
        onCompleteStop = { viewModel.completeCurrentStop() },
        onSkipStop = { viewModel.skipCurrentStop() }
    )
}

@Composable
private fun MapContent(
    state: MapState,
    onRetry: () -> Unit,
    onStartNavigation: () -> Unit,
    onStopNavigation: () -> Unit,
    onToggleAutoScan: () -> Unit,
    onCompleteStop: () -> Unit,
    onSkipStop: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(top = 8.dp)
    ) {
        // Header with GPS status
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Navigation Map",
                style = MaterialTheme.typography.headlineMedium
            )
            GpsIndicator(isActive = state.gpsActive, accuracy = state.gpsAccuracy)
        }

        // Map canvas
        MapCanvas(state = state)

        // Route panel
        state.activeRoute?.let {
            RoutePanel(
                state = state,
                onStartNavigation = onStartNavigation,
                onStopNavigation = onStopNavigation,
                onToggleAutoScan = onToggleAutoScan,
                onCompleteStop = onCompleteStop,
                onSkipStop = onSkipStop
            )
        }

        // Scan status
        if (state.scanProgress.isNotEmpty()) {
            ScanStatusCard(state)
        }

        // Detection list
        if (state.detections.isNotEmpty()) {
            DetectionList(detections = state.detections)
        }

        // Error / Loading
        when {
            state.isLoading && state.detections.isEmpty() -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(100.dp),
                    contentAlignment = Alignment.Center
                ) { CircularProgressIndicator() }
            }
            state.error != null && state.detections.isEmpty() -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(text = state.error!!, color = MaterialTheme.colorScheme.error)
                    TextButton(onClick = onRetry) { Text("Retry") }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))
    }
}

@Composable
private fun GpsIndicator(isActive: Boolean, accuracy: Float) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        Icon(
            imageVector = Icons.Filled.MyLocation,
            contentDescription = "GPS",
            modifier = Modifier.size(14.dp),
            tint = if (isActive) Green400 else Red400
        )
        Text(
            text = if (isActive) {
                if (accuracy < 50f) "GPS (${accuracy.toInt()}m)" else "GPS (weak)"
            } else "NO GPS",
            style = MaterialTheme.typography.labelSmall,
            color = if (isActive) Green400 else Red400
        )
    }
}

@Composable
private fun MapCanvas(state: MapState) {
    val routeStops = state.activeRoute?.stops ?: emptyList()
    val currentIdx = state.currentStopIndex
    val detections = state.detections

    val bounds = remember(detections, routeStops, state.userLat, state.userLng, state.gpsActive) {
        computeBounds(detections, routeStops, state)
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(280.dp)
            .padding(16.dp)
            .background(Navy800, MaterialTheme.shapes.medium)
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
        ) {
            val gridColor = Slate400.copy(alpha = 0.15f)
            for (i in 0..4) {
                val x = size.width * i / 4f
                val y = size.height * i / 4f
                drawLine(gridColor, Offset(x, 0f), Offset(x, size.height), strokeWidth = 0.5f)
                drawLine(gridColor, Offset(0f, y), Offset(size.width, y), strokeWidth = 0.5f)
            }

            bounds?.let { b ->
                // Route connection lines
                if (routeStops.size > 1) {
                    drawRouteLines(routeStops, b, currentIdx)
                }

                // Geofence radius for current target
                routeStops.getOrNull(currentIdx)?.let { target ->
                    if (target.status == "pending" || target.status == "arrived") {
                        val cx = b.normalizeX(target.longitude, size.width)
                        val cy = b.normalizeY(target.latitude, size.height)
                        val radiusPx = (target.geofenceRadiusM / b.spanMeters * size.width)
                            .toFloat().coerceIn(15f, 80f)
                        drawCircle(
                            color = Yellow400.copy(alpha = 0.15f),
                            radius = radiusPx,
                            center = Offset(cx, cy)
                        )
                        drawCircle(
                            color = Yellow400.copy(alpha = 0.4f),
                            radius = radiusPx,
                            center = Offset(cx, cy),
                            style = Stroke(
                                width = 1.5f,
                                pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 4f))
                            )
                        )
                    }
                }

                // Detection pins
                detections.forEachIndexed { index, det ->
                    val lat = det.latitude ?: return@forEachIndexed
                    val lng = det.longitude ?: return@forEachIndexed
                    val cx = b.normalizeX(lng, size.width)
                    val cy = b.normalizeY(lat, size.height)
                    val color = when (index % 3) {
                        0 -> Red400; 1 -> Yellow400; else -> Green400
                    }
                    drawCircle(color.copy(alpha = 0.25f), radius = 16f, center = Offset(cx, cy))
                    drawCircle(color, radius = 6f, center = Offset(cx, cy))
                }

                // Route stop pins
                routeStops.forEach { stop ->
                    val cx = b.normalizeX(stop.longitude, size.width)
                    val cy = b.normalizeY(stop.latitude, size.height)
                    val isCurrent = stop.orderIndex == currentIdx
                    val color = when (stop.status) {
                        "completed" -> Green400
                        "skipped" -> Slate400
                        "scanning", "arrived" -> Yellow400
                        else -> if (isCurrent) Red400 else Red400.copy(alpha = 0.5f)
                    }
                    val r = if (isCurrent) 12f else 8f
                    drawCircle(color.copy(alpha = 0.3f), r + 6f, Offset(cx, cy))
                    drawCircle(color, r, Offset(cx, cy))
                    if (stop.status == "completed") {
                        drawCircle(Color.White, 4f, Offset(cx, cy))
                    }
                }

                // User location (blue dot)
                if (state.gpsActive && state.userLat != 0.0) {
                    val ux = b.normalizeX(state.userLng, size.width)
                    val uy = b.normalizeY(state.userLat, size.height)
                    drawCircle(Blue400.copy(alpha = 0.2f), 20f, Offset(ux, uy))
                    drawCircle(Blue400, 8f, Offset(ux, uy))
                    drawCircle(Color.White, 3f, Offset(ux, uy))
                }
            }
        }

        // Legend overlay
        Column(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(8.dp)
        ) {
            if (routeStops.isNotEmpty()) {
                Text(
                    "${state.completedStops}/${routeStops.size} stops",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400
                )
            }
            if (detections.isNotEmpty()) {
                Text(
                    "${detections.size} detections",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400
                )
            }
        }
    }
}

private fun DrawScope.drawRouteLines(
    stops: List<RouteStopResponse>,
    bounds: MapBounds,
    currentIdx: Int
) {
    for (i in 0 until stops.size - 1) {
        val s1 = stops[i]
        val s2 = stops[i + 1]
        val x1 = bounds.normalizeX(s1.longitude, size.width)
        val y1 = bounds.normalizeY(s1.latitude, size.height)
        val x2 = bounds.normalizeX(s2.longitude, size.width)
        val y2 = bounds.normalizeY(s2.latitude, size.height)
        val active = i >= currentIdx
        drawLine(
            color = if (active) Slate400.copy(alpha = 0.5f) else Green400.copy(alpha = 0.3f),
            start = Offset(x1, y1),
            end = Offset(x2, y2),
            strokeWidth = if (active) 2f else 1f,
            pathEffect = if (active) PathEffect.dashPathEffect(floatArrayOf(8f, 4f)) else null
        )
    }
}

@Composable
private fun RoutePanel(
    state: MapState,
    onStartNavigation: () -> Unit,
    onStopNavigation: () -> Unit,
    onToggleAutoScan: () -> Unit,
    onCompleteStop: () -> Unit,
    onSkipStop: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = state.activeRoute?.name ?: "Active Route",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "${state.completedStops}/${state.activeRoute?.totalStops ?: 0} done",
                    style = MaterialTheme.typography.labelMedium,
                    color = Green400
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Current stop info
            state.currentStop?.let { stop ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        imageVector = Icons.Filled.Navigation,
                        contentDescription = null,
                        tint = Red400,
                        modifier = Modifier.size(20.dp)
                    )
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = stop.address,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 2
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (state.distanceText.isNotEmpty()) {
                                Text(
                                    text = state.distanceText,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Text(
                                text = when (stop.status) {
                                    "arrived" -> "Arrived"
                                    "scanning" -> "Scanning..."
                                    "completed" -> "Done"
                                    else -> if (state.isApproaching) "Approaching" else "En route"
                                },
                                style = MaterialTheme.typography.bodySmall,
                                color = when (stop.status) {
                                    "arrived", "scanning" -> Yellow400
                                    "completed" -> Green400
                                    else -> if (state.isApproaching) Yellow400
                                    else MaterialTheme.colorScheme.onSurfaceVariant
                                }
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Auto-scan toggle
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Auto-scan on arrival", style = MaterialTheme.typography.bodySmall)
                Switch(
                    checked = state.autoScanEnabled,
                    onCheckedChange = { onToggleAutoScan() }
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (state.gpsActive && state.activeRoute?.status == "active") {
                    Button(
                        onClick = onStartNavigation,
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = Green400)
                    ) {
                        Icon(Icons.Filled.Navigation, null, Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Navigate", style = MaterialTheme.typography.labelMedium)
                    }
                }
                OutlinedButton(onClick = onCompleteStop, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.CheckCircle, null, Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Done", style = MaterialTheme.typography.labelMedium)
                }
                OutlinedButton(onClick = onSkipStop, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.SkipNext, null, Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Skip", style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun ScanStatusCard(state: MapState) {
    val (statusText, statusColor) = when (state.scanProgress) {
        "arrived" -> "Arrived at stop" to Yellow400
        "warming_up" -> "Warming up pipeline..." to Yellow400
        "scanning" -> "Auto-scanning..." to Blue400
        "complete" -> "Scan complete" to Green400
        "failed" -> "Scan failed" to Red400
        "route_complete" -> "Route complete!" to Green400
        else -> state.scanProgress to Slate400
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        colors = CardDefaults.cardColors(containerColor = statusColor.copy(alpha = 0.1f))
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Box(Modifier.size(8.dp).background(statusColor, CircleShape))
            Text(statusText, style = MaterialTheme.typography.bodyMedium, color = statusColor)
            if (state.isAutoScanning) {
                CircularProgressIndicator(
                    modifier = Modifier.size(14.dp),
                    strokeWidth = 2.dp,
                    color = statusColor
                )
            }
        }
    }
}

@Composable
private fun DetectionList(detections: List<Detection>) {
    val pinColors = remember { listOf(Red400, Yellow400, Green400) }

    Column(
        modifier = Modifier.padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Text(
            "Recent Detections",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(vertical = 4.dp)
        )
        detections.take(5).forEachIndexed { index, det ->
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Box(
                        Modifier
                            .size(10.dp)
                            .background(pinColors[index % pinColors.size], CircleShape)
                    )
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            det.plateReads.firstOrNull()?.plateText ?: "No plate",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            det.address ?: "${det.latitude}, ${det.longitude}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Text(
                        "${det.vehicleMake ?: ""} ${det.vehicleModel ?: ""}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Blue400
                    )
                }
            }
        }
    }
}

// ── Map bounds ──────────────────────────────────────────────────────────────

private data class MapBounds(
    val minLat: Double,
    val maxLat: Double,
    val minLng: Double,
    val maxLng: Double
) {
    private val latRange get() = (maxLat - minLat).coerceAtLeast(0.001)
    private val lngRange get() = (maxLng - minLng).coerceAtLeast(0.001)
    private val pad = 0.1

    val spanMeters: Double get() = latRange * 111_320.0

    fun normalizeX(lng: Double, width: Float): Float {
        val norm = ((lng - minLng) / lngRange * (1 - 2 * pad) + pad).coerceIn(0.0, 1.0)
        return (norm * width).toFloat()
    }

    fun normalizeY(lat: Double, height: Float): Float {
        val norm = ((maxLat - lat) / latRange * (1 - 2 * pad) + pad).coerceIn(0.0, 1.0)
        return (norm * height).toFloat()
    }
}

private fun computeBounds(
    detections: List<Detection>,
    stops: List<RouteStopResponse>,
    state: MapState
): MapBounds? {
    val lats = mutableListOf<Double>()
    val lngs = mutableListOf<Double>()

    detections.forEach { d ->
        d.latitude?.let { lats.add(it) }
        d.longitude?.let { lngs.add(it) }
    }
    stops.forEach { s ->
        lats.add(s.latitude)
        lngs.add(s.longitude)
    }
    if (state.gpsActive && state.userLat != 0.0) {
        lats.add(state.userLat)
        lngs.add(state.userLng)
    }

    if (lats.isEmpty() || lngs.isEmpty()) return null
    return MapBounds(lats.min(), lats.max(), lngs.min(), lngs.max())
}
