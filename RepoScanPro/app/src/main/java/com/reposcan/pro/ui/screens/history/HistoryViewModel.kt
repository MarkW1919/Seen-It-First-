package com.reposcan.pro.ui.screens.history

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
data class HistoryState(
    val detections: List<Detection> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val page: Int = 1,
    val hasMore: Boolean = true
)

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val getDetectionsUseCase: GetDetectionsUseCase,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _state = MutableStateFlow(HistoryState())
    val state: StateFlow<HistoryState> = _state.asStateFlow()

    fun loadHistory(isDemoMode: Boolean) {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            getDetectionsUseCase(isDemoMode, page = 1).fold(
                onSuccess = { list ->
                    _state.update {
                        HistoryState(
                            detections = list.items,
                            page = 1,
                            hasMore = if (isDemoMode) false else list.items.size < list.total
                        )
                    }
                },
                onFailure = { e ->
                    _state.update {
                        HistoryState(error = e.message ?: "Failed to load history")
                    }
                }
            )
        }
    }

    fun loadMore(isDemoMode: Boolean) {
        if (_state.value.isLoading || !_state.value.hasMore || isDemoMode) return
        viewModelScope.launch {
            val nextPage = _state.value.page + 1
            _state.update { it.copy(isLoading = true) }
            getDetectionsUseCase(isDemoMode = false, page = nextPage).fold(
                onSuccess = { list ->
                    _state.update { current ->
                        current.copy(
                            detections = current.detections + list.items,
                            isLoading = false,
                            page = nextPage,
                            hasMore = (current.detections.size + list.items.size) < list.total
                        )
                    }
                },
                onFailure = {
                    _state.update { it.copy(isLoading = false) }
                }
            )
        }
    }
}
