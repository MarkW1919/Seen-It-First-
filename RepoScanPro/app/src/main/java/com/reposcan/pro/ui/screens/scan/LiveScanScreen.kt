package com.reposcan.pro.ui.screens.scan

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.reposcan.pro.data.model.CameraStatus
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.ui.components.DetectionCard
import com.reposcan.pro.ui.components.StatusBar
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.RepoScanProTheme

@Composable
fun LiveScanScreen(
    isDemoMode: Boolean,
    viewModel: ScanViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state.isScanning) {
        if (state.isScanning && isDemoMode) {
            viewModel.startDemoSimulation()
        }
    }

    LiveScanContent(
        state = state,
        onToggleScanning = { viewModel.toggleScanning() },
        onClearFeed = { viewModel.clearFeed() }
    )
}

@Composable
fun LiveScanContent(
    state: ScanState,
    onToggleScanning: () -> Unit,
    onClearFeed: () -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        modifier = modifier,
        floatingActionButton = {
            FloatingActionButton(
                onClick = onToggleScanning,
                containerColor = if (state.isScanning) Red400 else Green400
            ) {
                Icon(
                    imageVector = if (state.isScanning) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                    contentDescription = if (state.isScanning) "Stop Scan" else "Start Scan"
                )
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            StatusBar(
                isScanning = state.isScanning,
                cameraStatus = state.cameraStatus,
                hasGps = state.hasGps
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Live Scan Feed",
                        style = MaterialTheme.typography.titleLarge
                    )
                    Text(
                        text = "${state.totalScanned} vehicles | ${state.totalPlates} plates",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (state.liveFeed.isNotEmpty()) {
                    IconButton(onClick = onClearFeed) {
                        Icon(
                            Icons.Filled.Delete,
                            contentDescription = "Clear feed",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            if (state.liveFeed.isEmpty()) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(
                        text = if (state.isScanning) "Scanning..." else "Tap the play button to start scanning",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.liveFeed, key = { it.id }) { detection ->
                        DetectionCard(detection = detection)
                    }
                    item {
                        Spacer(modifier = Modifier.height(80.dp))
                    }
                }
            }
        }
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0F172A)
@Composable
private fun LiveScanContentPreview() {
    RepoScanProTheme(darkTheme = true) {
        LiveScanContent(
            state = ScanState(),
            onToggleScanning = {},
            onClearFeed = {}
        )
    }
}
