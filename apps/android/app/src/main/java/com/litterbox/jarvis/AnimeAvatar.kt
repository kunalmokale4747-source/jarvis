package com.litterbox.jarvis

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun AnimeAvatar(state: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.size(128.dp).background(Color(0xFF121A33)),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("JARVIS", color = Color(0xFFD6E6FF), fontSize = 12.sp)
        Text(state, color = Color(0xFF8CE7FF), fontSize = 10.sp)
    }
}