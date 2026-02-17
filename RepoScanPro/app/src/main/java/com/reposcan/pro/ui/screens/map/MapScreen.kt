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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.data.model.DetectionList
import com.reposcan.pro.data.model.PlateRead
import com.reposcan.pro.ui.theme.Blue400
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Navy800
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.Slate400
import com.reposcan.pro.ui.theme.Yellow400

@Composable
fun MapScreen(
    isDemoMode: Boolean,
    modifier: Modifier = Modifier
) {
    val demoDetections = remember {
        listOf(
            Detection(
                id = "map-1", agentId = null, sessionId = null,
                vehicleType = "car", vehicleColor = "Black", vehicleMake = "Toyota",
                vehicleModel = "Camry", vehicleYear = 2021, vehicleConfidence = 0.95,
                imagePath = null, thumbnailPath = null,
                latitude = 34.0522, longitude = -118.2437,
                address = "123 Main St, Los Angeles", heading = null, speed = null,
                extra = null, createdAt = "2024-06-15T14:30:00Z",
                plateReads = listOf(
                    PlateRead("pr-1", "ABC1234", "CA", null, 0.97, null, null, "2024-06-15T14:30:00Z")
                )
            ),
            Detection(
                id = "map-2", agentId = null, sessionId = null,
                vehicleType = "truck", vehicleColor = "White", vehicleMake = "Ford",
                vehicleModel = "F-150", vehicleYear = 2020, vehicleConfidence = 0.92,
                imagePath = null, thumbnailPath = null,
                latitude = 34.0535, longitude = -118.2450,
                address = "456 Oak Ave, Los Angeles", heading = null, speed = null,
                extra = null, createdAt = "2024-06-15T14:25:00Z",
                plateReads = listOf(
                    PlateRead("pr-2", "XYZ9876", "CA", null, 0.94, null, null, "2024-06-15T14:25:00Z")
                )
            ),
            Detection(
                id = "map-3", agentId = null, sessionId = null,
                vehicleType = "suv", vehicleColor = "Red", vehicleMake = "Honda",
                vehicleModel = "CR-V", vehicleYear = 2022, vehicleConfidence = 0.88,
                imagePath = null, thumbnailPath = null,
                latitude = 34.0510, longitude = -118.2420,
                address = "789 Elm Blvd, Los Angeles", heading = null, speed = null,
                extra = null, createdAt = "2024-06-15T14:20:00Z",
                plateReads = listOf(
                    PlateRead("pr-3", "DEF5678", "NV", null, 0.91, null, null, "2024-06-15T14:20:00Z")
                )
            )
        )
    }

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

        // Canvas-based map visualization
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(16.dp)
                .background(Navy800, MaterialTheme.shapes.medium)
        ) {
            Canvas(modifier = Modifier.fillMaxSize().padding(24.dp)) {
                // Grid lines
                val gridColor = Slate400.copy(alpha = 0.2f)
                for (i in 0..4) {
                    val x = size.width * i / 4f
                    val y = size.height * i / 4f
                    drawLine(gridColor, Offset(x, 0f), Offset(x, size.height), strokeWidth = 1f)
                    drawLine(gridColor, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
                }

                // Plot detection points
                val colors = listOf(Red400, Yellow400, Green400)
                demoDetections.forEachIndexed { index, det ->
                    val lat = det.latitude ?: return@forEachIndexed
                    val lng = det.longitude ?: return@forEachIndexed
                    // Normalize to canvas coordinates
                    val normX = ((lng - (-118.250)) / 0.010f).coerceIn(0.0, 1.0)
                    val normY = ((34.055 - lat) / 0.010f).coerceIn(0.0, 1.0)
                    val cx = (normX * size.width).toFloat()
                    val cy = (normY * size.height).toFloat()

                    // Outer ring
                    drawCircle(colors[index % colors.size].copy(alpha = 0.3f), radius = 24f, center = Offset(cx, cy))
                    // Inner dot
                    drawCircle(colors[index % colors.size], radius = 10f, center = Offset(cx, cy))
                }
            }

            // Legend
            Column(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp)
            ) {
                Text(
                    text = "${demoDetections.size} detections",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400
                )
                Text(
                    text = "Los Angeles, CA",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400
                )
            }
        }

        // Detection list below map
        Column(
            modifier = Modifier.padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            val pinColors = listOf(Red400, Yellow400, Green400)
            demoDetections.forEachIndexed { index, det ->
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

        // Spacer at bottom
        Box(modifier = Modifier.padding(bottom = 16.dp))
    }
}
