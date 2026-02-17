package com.reposcan.pro.ui.screens.scan

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.CameraStatus
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.data.repository.DetectionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ScanState(
    val isScanning: Boolean = false,
    val liveFeed: List<Detection> = emptyList(),
    val cameraStatus: CameraStatus = CameraStatus(),
    val hasGps: Boolean = true,
    val totalScanned: Int = 0,
    val totalPlates: Int = 0
)

@HiltViewModel
class ScanViewModel @Inject constructor(
    private val detectionRepository: DetectionRepository
) : ViewModel() {

    private val _state = MutableStateFlow(ScanState())
    val state: StateFlow<ScanState> = _state.asStateFlow()

    fun toggleScanning() {
        _state.value = _state.value.copy(isScanning = !_state.value.isScanning)
    }

    fun startDemoSimulation() {
        val demoDetections = detectionRepository.getDemoDetections().items
        _state.value = _state.value.copy(
            cameraStatus = CameraStatus(
                isConnected = true, fps = 29.0, nightMode = false,
                streaming = true, resolution = "1920x1080"
            )
        )

        viewModelScope.launch {
            var index = 0
            while (_state.value.isScanning) {
                delay(3000)
                if (!_state.value.isScanning) break
                val det = demoDetections[index % demoDetections.size].copy(
                    id = "live-${System.currentTimeMillis()}-$index"
                )
                val currentFeed = listOf(det) + _state.value.liveFeed.take(99)
                _state.value = _state.value.copy(
                    liveFeed = currentFeed,
                    totalScanned = _state.value.totalScanned + 1,
                    totalPlates = _state.value.totalPlates + det.plateReads.size,
                    cameraStatus = _state.value.cameraStatus.copy(
                        fps = 27.0 + (Math.random() * 3)
                    )
                )
                index++
            }
        }
    }

    fun clearFeed() {
        _state.value = _state.value.copy(liveFeed = emptyList(), totalScanned = 0, totalPlates = 0)
    }
}
