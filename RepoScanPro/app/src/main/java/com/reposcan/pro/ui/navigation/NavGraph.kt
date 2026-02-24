package com.reposcan.pro.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.reposcan.pro.ui.screens.alerts.AlertsScreen
import com.reposcan.pro.ui.screens.history.HistoryScreen
import com.reposcan.pro.ui.screens.hotlist.HotListScreen
import com.reposcan.pro.ui.screens.map.MapScreen
import com.reposcan.pro.ui.screens.scan.LiveScanScreen
import com.reposcan.pro.ui.screens.search.SearchScreen
import com.reposcan.pro.ui.screens.settings.SettingsScreen

@Composable
fun NavGraph(
    navController: NavHostController,
    isDemoMode: Boolean,
    modifier: Modifier = Modifier
) {
    NavHost(
        navController = navController,
        startDestination = Screen.Scan.route,
        modifier = modifier
    ) {
        composable(Screen.Scan.route) {
            LiveScanScreen(isDemoMode = isDemoMode)
        }
        composable(Screen.Alerts.route) {
            AlertsScreen(isDemoMode = isDemoMode)
        }
        composable(Screen.Map.route) {
            MapScreen(isDemoMode = isDemoMode)
        }
        composable(Screen.Search.route) {
            SearchScreen(isDemoMode = isDemoMode)
        }
        composable(Screen.History.route) {
            HistoryScreen(isDemoMode = isDemoMode)
        }
        composable(Screen.HotList.route) {
            HotListScreen(isDemoMode = isDemoMode)
        }
        composable(Screen.Settings.route) {
            SettingsScreen(onLogout = {
                navController.navigate(Screen.Scan.route) {
                    popUpTo(0) { inclusive = true }
                }
            })
        }
    }
}
