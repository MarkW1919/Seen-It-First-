package com.reposcan.pro.ui.screens.scan

import androidx.compose.runtime.Immutable
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.CameraStatus
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.domain.repository.IDetectionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@Immutable
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
    private val detectionRepository: IDetectionRepository,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _state = MutableStateFlow(ScanState())
    val state: StateFlow<ScanState> = _state.asStateFlow()

    private var simulationJob: Job? = null

    fun toggleScanning() {
        val newScanning = !_state.value.isScanning
        _state.update { it.copy(isScanning = newScanning) }
        if (!newScanning) {
            simulationJob?.cancel()
            simulationJob = null
        }
    }

    fun startDemoSimulation() {
        simulationJob?.cancel()
        val demoDetections = detectionRepository.getDemoDetections().items
        _state.update {
            it.copy(
                cameraStatus = CameraStatus(
                    isConnected = true, fps = 29.0, nightMode = false,
                    streaming = true, resolution = "1920x1080"
                )
            )
        }

        simulationJob = viewModelScope.launch {
            var index = 0
            while (_state.value.isScanning) {
                delay(3000)
                if (!_state.value.isScanning) break
                val det = demoDetections[index % demoDetections.size].copy(
                    id = "live-${System.currentTimeMillis()}-$index"
                )
                _state.update { current ->
                    val currentFeed = listOf(det) + current.liveFeed.take(99)
                    current.copy(
                        liveFeed = currentFeed,
                        totalScanned = current.totalScanned + 1,
                        totalPlates = current.totalPlates + det.plateReads.size,
                        cameraStatus = current.cameraStatus.copy(
                            fps = 27.0 + (Math.random() * 3)
                        )
                    )
                }
                index++
            }
        }
    }

    fun clearFeed() {
        _state.update { it.copy(liveFeed = emptyList(), totalScanned = 0, totalPlates = 0) }
    }

    override fun onCleared() {
        super.onCleared()
        simulationJob?.cancel()
    }
}
