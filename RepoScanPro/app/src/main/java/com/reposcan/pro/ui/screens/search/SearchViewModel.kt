package com.reposcan.pro.ui.screens.search

import androidx.compose.runtime.Immutable
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.domain.usecase.SearchPlateUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@Immutable
data class SearchState(
    val query: String = "",
    val results: List<Detection> = emptyList(),
    val isLoading: Boolean = false,
    val hasSearched: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class SearchViewModel @Inject constructor(
    private val searchPlateUseCase: SearchPlateUseCase,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _state = MutableStateFlow(
        SearchState(
            query = savedStateHandle.get<String>("search_query") ?: ""
        )
    )
    val state: StateFlow<SearchState> = _state.asStateFlow()

    fun updateQuery(query: String) {
        savedStateHandle["search_query"] = query
        _state.update { it.copy(query = query) }
    }

    fun search(isDemoMode: Boolean) {
        val query = _state.value.query.trim().uppercase()
        if (query.isBlank() || _state.value.isLoading) return

        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, hasSearched = true, error = null) }
            searchPlateUseCase(query, isDemoMode).fold(
                onSuccess = { results ->
                    _state.update { it.copy(isLoading = false, results = results) }
                },
                onFailure = { e ->
                    _state.update { it.copy(isLoading = false, error = e.message) }
                }
            )
        }
    }

    fun clearSearch() {
        savedStateHandle["search_query"] = ""
        _state.update { SearchState() }
    }
}
