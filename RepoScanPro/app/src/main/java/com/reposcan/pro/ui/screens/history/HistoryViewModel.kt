package com.reposcan.pro.ui.screens.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.data.repository.DetectionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HistoryState(
    val detections: List<Detection> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val page: Int = 1,
    val hasMore: Boolean = true
)

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val detectionRepository: DetectionRepository
) : ViewModel() {

    private val _state = MutableStateFlow(HistoryState())
    val state: StateFlow<HistoryState> = _state.asStateFlow()

    fun loadHistory(isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            if (isDemoMode) {
                val demoData = detectionRepository.getDemoDetections()
                _state.value = HistoryState(
                    detections = demoData.items,
                    hasMore = false
                )
            } else {
                detectionRepository.fetchDetections(page = 1).fold(
                    onSuccess = { list ->
                        _state.value = HistoryState(
                            detections = list.items,
                            page = 1,
                            hasMore = list.items.size < list.total
                        )
                    },
                    onFailure = { e ->
                        _state.value = HistoryState(error = e.message)
                    }
                )
            }
        }
    }

    fun loadMore() {
        if (_state.value.isLoading || !_state.value.hasMore) return
        viewModelScope.launch {
            val nextPage = _state.value.page + 1
            _state.value = _state.value.copy(isLoading = true)
            detectionRepository.fetchDetections(page = nextPage).fold(
                onSuccess = { list ->
                    _state.value = _state.value.copy(
                        detections = _state.value.detections + list.items,
                        isLoading = false,
                        page = nextPage,
                        hasMore = (_state.value.detections.size + list.items.size) < list.total
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(isLoading = false)
                }
            )
        }
    }
}
