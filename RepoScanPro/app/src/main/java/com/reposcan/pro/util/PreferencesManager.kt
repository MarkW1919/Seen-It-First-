package com.reposcan.pro.util

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(
    name = Constants.PREFERENCES_NAME
)

@Singleton
class PreferencesManager @Inject constructor(
    @ApplicationContext private val context: Context
) {

    private val dataStore = context.dataStore

    private object Keys {
        val ACCESS_TOKEN = stringPreferencesKey(Constants.KEY_ACCESS_TOKEN)
        val REFRESH_TOKEN = stringPreferencesKey(Constants.KEY_REFRESH_TOKEN)
        val BASE_URL = stringPreferencesKey(Constants.KEY_BASE_URL)
        val DARK_MODE = booleanPreferencesKey(Constants.KEY_DARK_MODE)
        val ALERT_SOUND = booleanPreferencesKey(Constants.KEY_ALERT_SOUND)
        val ALERT_VIBRATION = booleanPreferencesKey(Constants.KEY_ALERT_VIBRATION)
        val IS_DEMO_MODE = booleanPreferencesKey(Constants.KEY_IS_DEMO_MODE)
    }

    val accessToken: Flow<String?> = dataStore.data.map { it[Keys.ACCESS_TOKEN] }
    val refreshToken: Flow<String?> = dataStore.data.map { it[Keys.REFRESH_TOKEN] }
    val baseUrl: Flow<String> = dataStore.data.map { it[Keys.BASE_URL] ?: Constants.DEFAULT_BASE_URL }
    val darkMode: Flow<Boolean> = dataStore.data.map { it[Keys.DARK_MODE] ?: true }
    val alertSound: Flow<Boolean> = dataStore.data.map { it[Keys.ALERT_SOUND] ?: true }
    val alertVibration: Flow<Boolean> = dataStore.data.map { it[Keys.ALERT_VIBRATION] ?: true }
    val isDemoMode: Flow<Boolean> = dataStore.data.map { it[Keys.IS_DEMO_MODE] ?: false }

    suspend fun saveTokens(accessToken: String, refreshToken: String) {
        dataStore.edit { prefs ->
            prefs[Keys.ACCESS_TOKEN] = accessToken
            prefs[Keys.REFRESH_TOKEN] = refreshToken
        }
    }

    suspend fun clearTokens() {
        dataStore.edit { prefs ->
            prefs.remove(Keys.ACCESS_TOKEN)
            prefs.remove(Keys.REFRESH_TOKEN)
            prefs[Keys.IS_DEMO_MODE] = false
        }
    }

    suspend fun setBaseUrl(url: String) {
        dataStore.edit { it[Keys.BASE_URL] = url }
    }

    suspend fun setDarkMode(enabled: Boolean) {
        dataStore.edit { it[Keys.DARK_MODE] = enabled }
    }

    suspend fun setAlertSound(enabled: Boolean) {
        dataStore.edit { it[Keys.ALERT_SOUND] = enabled }
    }

    suspend fun setAlertVibration(enabled: Boolean) {
        dataStore.edit { it[Keys.ALERT_VIBRATION] = enabled }
    }

    suspend fun setDemoMode(enabled: Boolean) {
        dataStore.edit { it[Keys.IS_DEMO_MODE] = enabled }
    }
}
