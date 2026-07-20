package com.shanyin.erp.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = Blue80,
    onPrimary = Gray90,
    primaryContainer = Blue40,
    onPrimaryContainer = Blue80,
    secondary = Teal80,
    onSecondary = Gray90,
    secondaryContainer = Teal40,
    onSecondaryContainer = Teal80,
    tertiary = Amber80,
    onTertiary = Gray90,
    tertiaryContainer = Amber40,
    onTertiaryContainer = Amber80,
    background = DarkBackground,
    onBackground = Gray10,
    surface = DarkSurface,
    onSurface = Gray10,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = Gray40,
    error = Error,
    onError = Gray10
)

private val LightColorScheme = lightColorScheme(
    primary = Blue40,
    onPrimary = Gray10,
    primaryContainer = Blue80,
    onPrimaryContainer = Blue20,
    secondary = Teal40,
    onSecondary = Gray10,
    secondaryContainer = Teal80,
    onSecondaryContainer = Teal20,
    tertiary = Amber40,
    onTertiary = Gray10,
    tertiaryContainer = Amber80,
    onTertiaryContainer = Amber20,
    background = Gray10,
    onBackground = Gray90,
    surface = Gray10,
    onSurface = Gray90,
    surfaceVariant = Gray20,
    onSurfaceVariant = Gray60,
    error = Error,
    onError = Gray10
)

@Composable
fun ShanyinERPTheme(
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

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
