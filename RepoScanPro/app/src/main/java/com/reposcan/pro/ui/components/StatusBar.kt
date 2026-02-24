package com.reposcan.pro.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.reposcan.pro.data.model.CameraStatus
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Purple400
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.Slate500

@Composable
fun StatusBar(
    isScanning: Boolean,
    cameraStatus: CameraStatus,
    hasGps: Boolean,
    modifier: Modifier = Modifier
) {
    val scanColor by animateColorAsState(
        targetValue = if (isScanning) Green400 else Slate500,
        label = "scanColor"
    )

    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Scanning status
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            androidx.compose.foundation.Canvas(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
            ) {
                drawCircle(color = scanColor)
            }
            Text(
                text = if (isScanning) "SCANNING" else "IDLE",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        // Camera info
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = if (cameraStatus.isConnected) "CAM OK" else "CAM OFF",
                style = MaterialTheme.typography.labelSmall,
                color = if (cameraStatus.isConnected) Green400 else Red400
            )
            if (cameraStatus.isConnected) {
                Text(
                    text = "${cameraStatus.fps.toInt()} FPS",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            if (cameraStatus.nightMode) {
                Text(
                    text = "IR",
                    style = MaterialTheme.typography.labelSmall,
                    color = Purple400
                )
            }
        }

        // GPS
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Icon(
                imageVector = Icons.Filled.LocationOn,
                contentDescription = "GPS",
                modifier = Modifier.size(12.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = if (hasGps) "GPS" else "NO GPS",
                style = MaterialTheme.typography.labelSmall,
                color = if (hasGps) Green400 else Red400
            )
        }
    }
}
