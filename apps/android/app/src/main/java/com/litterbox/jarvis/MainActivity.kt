package com.litterbox.jarvis

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.litterbox.jarvis.data.SettingsStore
import com.litterbox.jarvis.viewmodel.MainViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = SettingsStore(this)
        val vm = MainViewModel(store)
        setContent {
            AppScreen(this, store, vm)
        }
    }
}

@Composable
fun AppScreen(context: Context, store: SettingsStore, vm: MainViewModel) {
    val status by vm.status.collectAsState()
    val message by vm.message.collectAsState()
    val reply by vm.reply.collectAsState()
    var backendUrl by remember { mutableStateOf(store.backendBaseUrl) }
    var email by remember { mutableStateOf("") }
    var text by remember { mutableStateOf("") }

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        AnimeAvatar(state = "idle")
        Text("JARVIS Companion")
        TextField(
            value = backendUrl,
            onValueChange = { backendUrl = it },
            label = { Text("Backend URL") },
            modifier = Modifier.fillMaxWidth(),
        )
        Text("Status: $status")
        TextField(value = email, onValueChange = { email = it }, label = { Text("Dev email") }, modifier = Modifier.fillMaxWidth())
        Button(onClick = { vm.login(email, backendUrl) }) { Text("Connect") }
        Text(message)
        TextField(value = text, onValueChange = { text = it }, label = { Text("Message") }, modifier = Modifier.fillMaxWidth())
        Button(onClick = { vm.send(text) }) { Text("Send") }
        Text(reply)
        Spacer(Modifier.height(4.dp))
        Button(onClick = {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(backendUrl.trimEnd('/')))
            context.startActivity(intent)
        }) { Text("Open Dashboard") }
        Button(onClick = {
            val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${context.packageName}"))
            context.startActivity(intent)
        }) { Text("Grant Overlay Permission") }
    }
}