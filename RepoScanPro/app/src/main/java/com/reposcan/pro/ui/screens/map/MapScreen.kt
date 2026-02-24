package com.reposcan.pro.ui.screens.map

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.ui.theme.Blue400
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Navy800
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.RepoScanProTheme
import com.reposcan.pro.ui.theme.Slate400
import com.reposcan.pro.ui.theme.Yellow400

@Composable
fun MapScreen(
    isDemoMode: Boolean,
    viewModel: MapViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadDetections(isDemoMode)
    }

    MapContent(
        detections = state.detections,
        isLoading = state.isLoading,
        error = state.error,
        onRetry = { viewModel.loadDetections(isDemoMode) }
    )
}

@Composable
fun MapContent(
    detections: List<Detection>,
    isLoading: Boolean,
    error: String?,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(top = 8.dp)
    ) {
        Text(
            text = "Detection Map",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
        )

        when {
            isLoading && detections.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            }
            error != null && detections.isEmpty() -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(
                        text = error,
                        color = MaterialTheme.colorScheme.error
                    )
                    TextButton(onClick = onRetry) {
                        Text("Retry")
                    }
                }
            }
            detections.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No detections with location data",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            else -> {
                val pinColors = remember { listOf(Red400, Yellow400, Green400) }

                val bounds = remember(detections) {
                    val lats = detections.mapNotNull { it.latitude }
                    val lngs = detections.mapNotNull { it.longitude }
                    if (lats.isEmpty() || lngs.isEmpty()) null
                    else MapBounds(lats.min(), lats.max(), lngs.min(), lngs.max())
                }

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .padding(16.dp)
                        .background(Navy800, MaterialTheme.shapes.medium)
                ) {
                    Canvas(modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp)) {
                        val gridColor = Slate400.copy(alpha = 0.2f)
                        for (i in 0..4) {
                            val x = size.width * i / 4f
                            val y = size.height * i / 4f
                            drawLine(gridColor, Offset(x, 0f), Offset(x, size.height), strokeWidth = 1f)
                            drawLine(gridColor, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
                        }

                        bounds?.let { b ->
                            val latRange = (b.maxLat - b.minLat).coerceAtLeast(0.001)
                            val lngRange = (b.maxLng - b.minLng).coerceAtLeast(0.001)
                            val padding = 0.1

                            detections.forEachIndexed { index, det ->
                                val lat = det.latitude ?: return@forEachIndexed
                                val lng = det.longitude ?: return@forEachIndexed
                                val normX = ((lng - b.minLng) / lngRange * (1 - 2 * padding) + padding).coerceIn(0.0, 1.0)
                                val normY = ((b.maxLat - lat) / latRange * (1 - 2 * padding) + padding).coerceIn(0.0, 1.0)
                                val cx = (normX * size.width).toFloat()
                                val cy = (normY * size.height).toFloat()
                                val color = pinColors[index % pinColors.size]
                                drawCircle(color.copy(alpha = 0.3f), radius = 24f, center = Offset(cx, cy))
                                drawCircle(color, radius = 10f, center = Offset(cx, cy))
                            }
                        }
                    }

                    Column(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .padding(8.dp)
                    ) {
                        Text(
                            text = "${detections.size} detections",
                            style = MaterialTheme.typography.labelSmall,
                            color = Slate400
                        )
                    }
                }

                Column(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
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
                                    modifier = Modifier
                                        .size(10.dp)
                                        .background(pinColors[index % pinColors.size], CircleShape)
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = det.plateReads.firstOrNull()?.plateText ?: "No plate",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = det.address ?: "${det.latitude}, ${det.longitude}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Text(
                                    text = "${det.vehicleMake ?: ""} ${det.vehicleModel ?: ""}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Blue400
                                )
                            }
                        }
                    }
                }

                Box(modifier = Modifier.padding(bottom = 16.dp))
            }
        }
    }
}

private data class MapBounds(
    val minLat: Double,
    val maxLat: Double,
    val minLng: Double,
    val maxLng: Double
)

@Preview(showBackground = true, backgroundColor = 0xFF0F172A)
@Composable
private fun MapContentPreview() {
    RepoScanProTheme(darkTheme = true) {
        MapContent(
            detections = emptyList(),
            isLoading = false,
            error = null,
            onRetry = {}
        )
    }
}
