package com.reposcan.pro.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.ui.theme.Blue400
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Yellow400

@Composable
fun DetectionCard(
    detection: Detection,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Vehicle info row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = buildString {
                            detection.vehicleYear?.let { append("$it ") }
                            detection.vehicleMake?.let { append("$it ") }
                            detection.vehicleModel?.let { append(it) }
                        }.ifBlank { "Unknown Vehicle" },
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    detection.vehicleColor?.let { color ->
                        Text(
                            text = "$color ${detection.vehicleType ?: "vehicle"}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                detection.vehicleConfidence?.let { conf ->
                    Text(
                        text = "${(conf * 100).toInt()}%",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        color = when {
                            conf >= 0.9 -> Green400
                            conf >= 0.7 -> Yellow400
                            else -> Blue400
                        }
                    )
                }
            }

            // Plate reads
            detection.plateReads.forEach { plate ->
                PlateDisplay(plateText = plate.plateText, confidence = plate.confidence)
            }

            // Location
            detection.address?.let { addr ->
                Text(
                    text = addr,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Timestamp
            Text(
                text = detection.createdAt.take(19).replace("T", " "),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
