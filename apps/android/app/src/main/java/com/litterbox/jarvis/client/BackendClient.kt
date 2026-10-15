package com.litterbox.jarvis.client

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

data class LoginResult(val token: String)

class BackendClient(
    var baseUrl: String,
) {
    private val http = OkHttpClient()

    private fun url(path: String): String = baseUrl.trimEnd('/') + path

    suspend fun login(email: String): String = withContext(Dispatchers.IO) {
        val body = JSONObject().apply { put("email", email) }.toString()
        val req = Request.Builder().url(url("/api/v1/auth/login"))
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        http.newCall(req).execute().use { response ->
            if (!response.isSuccessful) throw IllegalStateException("Login HTTP ${response.code}")
            JSONObject(requireNotNull(response.body).string()).getString("token")
        }
    }

    suspend fun chat(token: String, message: String, sessionId: String?): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            put("message", message)
            sessionId?.let { put("session_id", it) }
        }
        val req = Request.Builder().url(url("/api/v1/chat"))
            .header("Authorization", "Bearer $token")
            .post(body.toString().toRequestBody("application/json".toMediaType()))
            .build()
        http.newCall(req).execute().use { response ->
            if (!response.isSuccessful) throw IllegalStateException("Chat HTTP ${response.code}")
            JSONObject(requireNotNull(response.body).string())
        }
    }

    suspend fun realtimeStatus(token: String): JSONObject = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(url("/api/v1/voice/realtime/status"))
            .header("Authorization", "Bearer $token")
            .get()
            .build()
        http.newCall(req).execute().use { response ->
            if (!response.isSuccessful) throw IllegalStateException("Realtime status HTTP ${response.code}")
            JSONObject(requireNotNull(response.body).string())
        }
    }

    suspend fun realtimeSession(token: String): String = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(url("/api/v1/voice/realtime/session"))
            .header("Authorization", "Bearer $token")
            .post("{}".toRequestBody("application/json".toMediaType()))
            .build()
        http.newCall(req).execute().use { response ->
            if (!response.isSuccessful) throw IllegalStateException("Realtime session HTTP ${response.code}")
            requireNotNull(response.body).string()
        }
    }
}