package com.reposcan.pro.ui.screens.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.reposcan.pro.ui.theme.Red400

@Composable
fun SettingsScreen(
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "Settings",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        // Appearance
        Text(
            text = "APPEARANCE",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        SettingsSwitch(
            label = "Dark Mode",
            checked = state.darkMode,
            onCheckedChange = { viewModel.setDarkMode(it) }
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

        // Alerts
        Text(
            text = "ALERTS",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        SettingsSwitch(
            label = "Alert Sound",
            checked = state.alertSoundEnabled,
            onCheckedChange = { viewModel.setAlertSound(it) }
        )
        SettingsSwitch(
            label = "Alert Vibration",
            checked = state.alertVibrationEnabled,
            onCheckedChange = { viewModel.setAlertVibration(it) }
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

        // Connection
        Text(
            text = "CONNECTION",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedTextField(
            value = state.baseUrl,
            onValueChange = { viewModel.setBaseUrl(it) },
            label = { Text("Backend URL") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

        // About
        Text(
            text = "ABOUT",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "RepoScan Pro v1.0.0",
            style = MaterialTheme.typography.bodyMedium
        )
        Text(
            text = "AI-powered License Plate Recognition for Repossession Agents",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Logout
        Button(
            onClick = { viewModel.logout(onLogout) },
            colors = ButtonDefaults.buttonColors(containerColor = Red400),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Sign Out")
        }

        Spacer(modifier = Modifier.height(16.dp))
    }
}

@Composable
private fun SettingsSwitch(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = label, style = MaterialTheme.typography.bodyLarge)
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
