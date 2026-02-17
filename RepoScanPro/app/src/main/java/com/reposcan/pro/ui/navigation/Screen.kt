package com.reposcan.pro.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(
    val route: String,
    val title: String,
    val icon: ImageVector
) {
    data object Scan : Screen("scan", "Scan", Icons.Filled.CameraAlt)
    data object Alerts : Screen("alerts", "Alerts", Icons.Filled.Notifications)
    data object Map : Screen("map", "Map", Icons.Filled.Map)
    data object Search : Screen("search", "Search", Icons.Filled.Search)
    data object History : Screen("history", "History", Icons.Filled.History)
    data object HotList : Screen("hotlist", "Hot List", Icons.Filled.List)
    data object Settings : Screen("settings", "Settings", Icons.Filled.Settings)

    companion object {
        val bottomNavItems = listOf(Scan, Alerts, Map, Search, HotList)
    }
}
