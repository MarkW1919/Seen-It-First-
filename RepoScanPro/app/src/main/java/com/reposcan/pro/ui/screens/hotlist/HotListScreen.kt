package com.reposcan.pro.ui.screens.hotlist

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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.reposcan.pro.ui.components.PlateDisplay
import com.reposcan.pro.ui.theme.Blue500
import com.reposcan.pro.ui.theme.Green400
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.Yellow400

@Composable
fun HotListScreen(
    isDemoMode: Boolean,
    viewModel: HotListViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadEntries(isDemoMode)
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = { viewModel.toggleAddDialog() },
                containerColor = Blue500
            ) {
                Icon(Icons.Filled.Add, contentDescription = "Add Entry")
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(top = 8.dp)
        ) {
            Text(
                text = "Hot List",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
            )
            Text(
                text = "${state.entries.size} active entries",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp)
            )

            if (state.entries.isEmpty()) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(
                        text = "No hot list entries",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.entries, key = { it.id }) { entry ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.surfaceVariant
                            )
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    PlateDisplay(plateText = entry.plateText, confidence = 1.0)
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                                    ) {
                                        Text(
                                            text = entry.priority.uppercase(),
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = when (entry.priority) {
                                                "critical" -> Red400
                                                "high" -> Yellow400
                                                else -> Green400
                                            }
                                        )
                                        IconButton(onClick = {
                                            viewModel.deleteEntry(entry.id, isDemoMode)
                                        }) {
                                            Icon(
                                                Icons.Filled.Delete, "Delete",
                                                tint = Red400
                                            )
                                        }
                                    }
                                }

                                Spacer(modifier = Modifier.height(4.dp))

                                val vehicleDesc = buildString {
                                    entry.vehicleYear?.let { append("$it ") }
                                    entry.vehicleMake?.let { append("$it ") }
                                    entry.vehicleModel?.let { append("$it ") }
                                    entry.vehicleColor?.let { append("($it)") }
                                }
                                if (vehicleDesc.isNotBlank()) {
                                    Text(
                                        text = vehicleDesc.trim(),
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                }

                                entry.caseNumber?.let {
                                    Text(
                                        text = "Case: $it",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                entry.lenderName?.let {
                                    Text(
                                        text = "Lender: $it",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                entry.debtorName?.let {
                                    Text(
                                        text = "Debtor: $it",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }
                    item { Spacer(modifier = Modifier.height(80.dp)) }
                }
            }
        }
    }

    // Add dialog
    if (state.showAddDialog) {
        var plateText by rememberSaveable { mutableStateOf("") }
        var vehicleInfo by rememberSaveable { mutableStateOf("") }

        AlertDialog(
            onDismissRequest = { viewModel.toggleAddDialog() },
            title = { Text("Add Hot List Entry") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = plateText,
                        onValueChange = { plateText = it.uppercase() },
                        label = { Text("Plate Number") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = vehicleInfo,
                        onValueChange = { vehicleInfo = it },
                        label = { Text("Vehicle Make (optional)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = { viewModel.addEntry(plateText, vehicleInfo, isDemoMode) },
                    enabled = plateText.isNotBlank()
                ) {
                    Text("Add")
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.toggleAddDialog() }) {
                    Text("Cancel")
                }
            }
        )
    }
}
