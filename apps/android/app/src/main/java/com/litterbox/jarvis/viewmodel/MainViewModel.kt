package com.litterbox.jarvis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.litterbox.jarvis.client.BackendClient
import com.litterbox.jarvis.client.SettingsStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class MainViewModel(private val store: SettingsStore) : ViewModel() {
    private val _status = MutableStateFlow(store.backendBaseUrl)
    val status: StateFlow<String> = _status
    private val _message = MutableStateFlow("")
    val message: StateFlow<String> = _message
    private val _reply = MutableStateFlow("")
    val reply: StateFlow<String> = _reply

    fun login(email: String, backendBaseUrl: String = store.backendBaseUrl) {
        val url = backendBaseUrl.trim()
        if (url.isBlank()) {
            _message.value = "Enter a backend URL."
            return
        }
        store.backendBaseUrl = url
        val client = BackendClient(url)
        _status.value = url
        viewModelScope.launch {
            try {
                store.authToken = client.login(email.trim())
                _message.value = "Connected."
            } catch (exception: Exception) {
                _message.value = "Login failed. Check the backend URL and dev auth settings."
            }
        }
    }

    fun send(text: String) {
        val token = store.authToken ?: run {
            _reply.value = "Login first."
            return
        }
        val url = store.backendBaseUrl
        val client = BackendClient(url)
        viewModelScope.launch {
            try {
                _reply.value = "Thinking..."
                val response = client.chat(token, text.trim(), null)
                val assistant = response.optJSONObject("assistant_message")
                _reply.value = assistant?.optString("content") ?: "Response received."
            } catch (exception: Exception) {
                _reply.value = "Request failed safely."
            }
        }
    }
}