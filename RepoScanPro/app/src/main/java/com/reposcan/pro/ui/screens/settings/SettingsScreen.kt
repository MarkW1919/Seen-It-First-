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
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.reposcan.pro.ui.theme.Red400
import com.reposcan.pro.ui.theme.RepoScanProTheme

@Composable
fun SettingsScreen(
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    SettingsContent(
        state = state,
        onDarkModeChange = { viewModel.setDarkMode(it) },
        onAlertSoundChange = { viewModel.setAlertSound(it) },
        onAlertVibrationChange = { viewModel.setAlertVibration(it) },
        onBaseUrlChange = { viewModel.setBaseUrl(it) },
        onLogout = { viewModel.logout(onLogout) }
    )
}

@Composable
fun SettingsContent(
    state: SettingsState,
    onDarkModeChange: (Boolean) -> Unit,
    onAlertSoundChange: (Boolean) -> Unit,
    onAlertVibrationChange: (Boolean) -> Unit,
    onBaseUrlChange: (String) -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "Settings",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        Text(
            text = "APPEARANCE",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        SettingsSwitch(
            label = "Dark Mode",
            checked = state.darkMode,
            onCheckedChange = onDarkModeChange
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

        Text(
            text = "ALERTS",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        SettingsSwitch(
            label = "Alert Sound",
            checked = state.alertSoundEnabled,
            onCheckedChange = onAlertSoundChange
        )
        SettingsSwitch(
            label = "Alert Vibration",
            checked = state.alertVibrationEnabled,
            onCheckedChange = onAlertVibrationChange
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

        Text(
            text = "CONNECTION",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedTextField(
            value = state.baseUrl,
            onValueChange = onBaseUrlChange,
            label = { Text("Backend URL") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

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

        Button(
            onClick = onLogout,
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

@Preview(showBackground = true, backgroundColor = 0xFF0F172A)
@Composable
private fun SettingsContentPreview() {
    RepoScanProTheme(darkTheme = true) {
        SettingsContent(
            state = SettingsState(isLoading = false),
            onDarkModeChange = {},
            onAlertSoundChange = {},
            onAlertVibrationChange = {},
            onBaseUrlChange = {},
            onLogout = {}
        )
    }
}
