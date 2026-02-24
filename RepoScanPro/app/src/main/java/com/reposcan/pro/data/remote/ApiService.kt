package com.reposcan.pro.data.remote

import com.reposcan.pro.data.model.CameraStatus
import com.reposcan.pro.data.model.Detection
import com.reposcan.pro.data.model.DetectionList
import com.reposcan.pro.data.model.HotListAlert
import com.reposcan.pro.data.model.HotListEntry
import com.reposcan.pro.data.model.LoginRequest
import com.reposcan.pro.data.model.RefreshRequest
import com.reposcan.pro.data.model.RegisterRequest
import com.reposcan.pro.data.model.RouteCreateRequest
import com.reposcan.pro.data.model.RouteResponse
import com.reposcan.pro.data.model.SystemStats
import com.reposcan.pro.data.model.TokenResponse
import com.reposcan.pro.data.model.User
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    // Auth
    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<TokenResponse>

    @POST("api/auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<User>

    @POST("api/auth/refresh")
    suspend fun refreshToken(@Body request: RefreshRequest): Response<TokenResponse>

    @GET("api/auth/me")
    suspend fun getMe(): Response<User>

    // Detections
    @GET("api/detections")
    suspend fun getDetections(
        @Query("page") page: Int? = null,
        @Query("page_size") pageSize: Int? = null,
        @Query("session_id") sessionId: String? = null,
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null
    ): Response<DetectionList>

    @GET("api/detections/{id}")
    suspend fun getDetection(@Path("id") id: String): Response<Detection>

    // Search
    @GET("api/search/plate")
    suspend fun searchPlate(
        @Query("q") query: String,
        @Query("exact") exact: Boolean? = null,
        @Query("page") page: Int? = null
    ): Response<DetectionList>

    @GET("api/search/nearby")
    suspend fun searchNearby(
        @Query("lat") lat: Double,
        @Query("lng") lng: Double,
        @Query("radius") radius: Double? = null
    ): Response<DetectionList>

    // Hot List
    @GET("api/hotlist/entries")
    suspend fun getHotListEntries(
        @Query("active_only") activeOnly: Boolean? = null
    ): Response<List<HotListEntry>>

    @POST("api/hotlist/entries")
    suspend fun createHotListEntry(@Body entry: Map<String, Any?>): Response<HotListEntry>

    @PATCH("api/hotlist/entries/{id}")
    suspend fun updateHotListEntry(
        @Path("id") id: String,
        @Body data: Map<String, Any?>
    ): Response<HotListEntry>

    @DELETE("api/hotlist/entries/{id}")
    suspend fun deleteHotListEntry(@Path("id") id: String): Response<Unit>

    @GET("api/hotlist/alerts")
    suspend fun getAlerts(@Query("status") status: String? = null): Response<List<HotListAlert>>

    @PATCH("api/hotlist/alerts/{id}")
    suspend fun updateAlert(
        @Path("id") id: String,
        @Body data: Map<String, Any?>
    ): Response<HotListAlert>

    // Camera
    @GET("api/camera/status")
    suspend fun getCameraStatus(): Response<CameraStatus>

    // System
    @GET("api/system/stats")
    suspend fun getSystemStats(): Response<SystemStats>

    // Health
    @GET("health")
    suspend fun healthCheck(): Response<Map<String, String>>

    // Routes
    @POST("api/routes")
    suspend fun createRoute(@Body body: RouteCreateRequest): Response<RouteResponse>

    @GET("api/routes")
    suspend fun getRoutes(
        @Query("status_filter") statusFilter: String? = null
    ): Response<List<RouteResponse>>

    @GET("api/routes/active")
    suspend fun getActiveRoute(): Response<RouteResponse>

    @GET("api/routes/{routeId}")
    suspend fun getRoute(@Path("routeId") routeId: String): Response<RouteResponse>

    @POST("api/routes/{routeId}/stops/{stopIndex}/arrive")
    suspend fun markArrival(
        @Path("routeId") routeId: String,
        @Path("stopIndex") stopIndex: Int
    ): Response<Map<String, Any>>

    @POST("api/routes/{routeId}/stops/{stopIndex}/scan-start")
    suspend fun startScanAtStop(
        @Path("routeId") routeId: String,
        @Path("stopIndex") stopIndex: Int
    ): Response<Map<String, Any>>

    @POST("api/routes/{routeId}/stops/{stopIndex}/complete")
    suspend fun completeStop(
        @Path("routeId") routeId: String,
        @Path("stopIndex") stopIndex: Int
    ): Response<Map<String, Any>>

    @POST("api/routes/{routeId}/stops/{stopIndex}/skip")
    suspend fun skipStop(
        @Path("routeId") routeId: String,
        @Path("stopIndex") stopIndex: Int
    ): Response<Map<String, Any>>

    @DELETE("api/routes/{routeId}")
    suspend fun deleteRoute(@Path("routeId") routeId: String): Response<Unit>
}
