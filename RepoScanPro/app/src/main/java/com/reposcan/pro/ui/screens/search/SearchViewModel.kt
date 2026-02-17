package com.reposcan.pro.ui.screens.search

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

data class SearchState(
    val query: String = "",
    val results: List<Detection> = emptyList(),
    val isLoading: Boolean = false,
    val hasSearched: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class SearchViewModel @Inject constructor(
    private val detectionRepository: DetectionRepository
) : ViewModel() {

    private val _state = MutableStateFlow(SearchState())
    val state: StateFlow<SearchState> = _state.asStateFlow()

    fun updateQuery(query: String) {
        _state.value = _state.value.copy(query = query)
    }

    fun search(isDemoMode: Boolean) {
        val query = _state.value.query.trim().uppercase()
        if (query.isBlank()) return

        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, hasSearched = true, error = null)
            if (isDemoMode) {
                val all = detectionRepository.getDemoDetections().items
                val filtered = all.filter { det ->
                    det.plateReads.any { it.plateText.contains(query) }
                }
                _state.value = _state.value.copy(isLoading = false, results = filtered)
            } else {
                detectionRepository.searchPlate(query).fold(
                    onSuccess = { list ->
                        _state.value = _state.value.copy(isLoading = false, results = list.items)
                    },
                    onFailure = { e ->
                        _state.value = _state.value.copy(isLoading = false, error = e.message)
                    }
                )
            }
        }
    }

    fun clearSearch() {
        _state.value = SearchState()
    }
}
