package com.litterbox.jarvis

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import android.widget.TextView

class FloatingCompanionService : Service() {
    private var windowManager: WindowManager? = null
    private var avatarView: TextView? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        ensureNotificationChannel()
        startForeground(1001, buildForegroundNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (avatarView == null) {
            val wm = getSystemService(WINDOW_SERVICE) as WindowManager
            windowManager = wm
            val view = TextView(this).apply {
                text = "JARVIS"
                gravity = Gravity.CENTER
                setPadding(24, 24, 24, 24)
            }
            view.setBackgroundResource(android.R.drawable.stat_happy)
            val params = WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
                PixelFormat.TRANSLUCENT,
            )
            params.gravity = Gravity.TOP or Gravity.START
            params.x = 100
            params.y = 100
            view.setOnTouchListener { thisView, event ->
                thisView.x = event.rawX - thisView.width / 2f
                thisView.y = event.rawY - thisView.height / 2f
                false
            }
            wm.addView(view, params)
            avatarView = view
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        avatarView?.let {
            runCatching { windowManager?.removeView(it) }
        }
        avatarView = null
        super.onDestroy()
    }

    private fun ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val channel = NotificationChannel(
                "jarvis_overlay",
                "JARVIS Overlay",
                NotificationManager.IMPORTANCE_LOW,
            )
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildForegroundNotification(): Notification {
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, "jarvis_overlay")
        } else {
            Notification.Builder(this)
        }
        return builder
            .setContentTitle("JARVIS companion")
            .setContentText("Floating companion available")
            .setSmallIcon(android.R.drawable.sym_def_app_icon)
            .setOngoing(true)
            .build()
    }
}