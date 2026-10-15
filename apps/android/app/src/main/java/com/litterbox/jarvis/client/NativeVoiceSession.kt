package com.litterbox.jarvis.client

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.provider.Settings

// Android WebRTC dependencies are intentionally not declared by this initial
// skeleton. The JARVIS backend remains the only manager of OpenAI credentials.
class NativeVoiceSession(
    val context: Activity,
) {
    fun ensureOverlayPermission(): Boolean {
        return if (Settings.canDrawOverlays(context)) {
            true
        } else {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${context.packageName}"),
            )
            context.startActivity(intent)
            false
        }
    }
}