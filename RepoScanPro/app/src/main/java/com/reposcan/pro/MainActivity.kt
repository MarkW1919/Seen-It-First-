package com.reposcan.pro

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.reposcan.pro.ui.components.BottomNavBar
import com.reposcan.pro.ui.navigation.NavGraph
import com.reposcan.pro.ui.navigation.Screen
import com.reposcan.pro.ui.screens.login.LoginScreen
import com.reposcan.pro.ui.screens.login.LoginViewModel
import com.reposcan.pro.ui.theme.RepoScanProTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            RepoScanProTheme(darkTheme = true) {
                RepoScanApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RepoScanApp() {
    val loginViewModel: LoginViewModel = hiltViewModel()
    val loginState by loginViewModel.state.collectAsState()

    if (loginState.user == null) {
        // Show login screen
        LoginScreen(
            state = loginState,
            onLogin = { email, password -> loginViewModel.login(email, password) },
            onDemoMode = { loginViewModel.enterDemoMode() }
        )
    } else {
        // Show main app with navigation
        val navController = rememberNavController()
        val navBackStackEntry by navController.currentBackStackEntryAsState()
        val currentRoute = navBackStackEntry?.destination?.route

        val screenTitle = when (currentRoute) {
            Screen.Scan.route -> "RepoScan Pro"
            Screen.Alerts.route -> "Alerts"
            Screen.Map.route -> "Map"
            Screen.Search.route -> "Search"
            Screen.History.route -> "History"
            Screen.HotList.route -> "Hot List"
            Screen.Settings.route -> "Settings"
            else -> "RepoScan Pro"
        }

        Scaffold(
            modifier = Modifier.fillMaxSize(),
            topBar = {
                TopAppBar(
                    title = {
                        Text(
                            text = screenTitle,
                            style = MaterialTheme.typography.titleLarge
                        )
                    },
                    actions = {
                        if (currentRoute != Screen.History.route) {
                            IconButton(onClick = {
                                navController.navigate(Screen.History.route) {
                                    launchSingleTop = true
                                }
                            }) {
                                Icon(Icons.Filled.History, contentDescription = "History")
                            }
                        }
                        if (currentRoute != Screen.Settings.route) {
                            IconButton(onClick = {
                                navController.navigate(Screen.Settings.route) {
                                    launchSingleTop = true
                                }
                            }) {
                                Icon(Icons.Filled.Settings, contentDescription = "Settings")
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                        titleContentColor = MaterialTheme.colorScheme.onSurface,
                        actionIconContentColor = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                )
            },
            bottomBar = {
                BottomNavBar(navController = navController)
            }
        ) { innerPadding ->
            NavGraph(
                navController = navController,
                isDemoMode = loginState.isDemoMode,
                modifier = Modifier.padding(innerPadding)
            )
        }
    }
}
