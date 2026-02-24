package com.reposcan.pro.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = Blue500,
    onPrimary = Navy900,
    secondary = Blue400,
    onSecondary = Navy900,
    tertiary = Purple400,
    background = Navy900,
    onBackground = Slate300,
    surface = Navy800,
    onSurface = Slate300,
    surfaceVariant = Navy700,
    onSurfaceVariant = Slate400,
    error = Red500,
    onError = Navy900
)

private val LightColorScheme = lightColorScheme(
    primary = Blue600,
    onPrimary = Slate300,
    secondary = Blue700,
    onSecondary = Slate300,
    tertiary = Purple400,
    background = Slate300,
    onBackground = Navy900,
    surface = Slate300,
    onSurface = Navy900,
    surfaceVariant = Slate400,
    onSurfaceVariant = Navy700,
    error = Red500,
    onError = Slate300
)

@Composable
fun RepoScanProTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
