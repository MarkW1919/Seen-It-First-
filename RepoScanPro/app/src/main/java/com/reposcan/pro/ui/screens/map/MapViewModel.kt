package com.reposcan.pro.ui.screens.map

import androidx.compose.runtime.Immutable
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.domain.usecase.GetDetectionsUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@Immutable
data class MapState(
    val detections: List<Detection> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class MapViewModel @Inject constructor(
    private val getDetectionsUseCase: GetDetectionsUseCase,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _state = MutableStateFlow(MapState())
    val state: StateFlow<MapState> = _state.asStateFlow()

    fun loadDetections(isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            getDetectionsUseCase(isDemoMode).fold(
                onSuccess = { list ->
                    val withCoords = list.items.filter { it.latitude != null && it.longitude != null }
                    _state.update { MapState(detections = withCoords) }
                },
                onFailure = { e ->
                    _state.update { MapState(error = e.message ?: "Failed to load detections") }
                }
            )
        }
    }
}
