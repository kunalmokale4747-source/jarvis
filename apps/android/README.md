# JARVIS Android Companion (Prototype Source)

This directory contains a native Android application skeleton. It is not a built application and no APK has been produced in this environment.

## Actual toolchain status

Verified absent:
- `java` / `javac`
- Kotlin compiler
- Gradle
- Android SDK
- `sdkmanager`
- `adb`
- emulator

The operating system package metadata lists much older Android SDK/Gradle packages, but they cannot satisfy this project's Android Gradle Plugin 8.6.1 and compile SDK 35 configuration. Do not pretend they can.

## Intended build environment

- JDK 17
- Android Studio, Android Studio for Linux, or a CI runner with Gradle 8.11.1
- Android SDK Platform 35
- Android SDK Build-Tools compatible with API 35
- A physical Android device or emulator for runtime tests

## Local build commands

With Gradle installed in a suitable Android environment:

```bash
cd /root/jarvis/apps/android
gradle wrapper
./gradlew assembleDebug
```

Without generating a wrapper:

```bash
cd /root/jarvis/apps/android
gradle :app:assembleDebug
```

The expected debug APK path is:

```text
app/build/outputs/apk/debug/app-debug.apk
```

A GitHub Actions workflow is provided at `.github/workflows/android.yml` for a standard-hosted debug build. Running it outside this environment can download the compiler and SDK, but it was not run here.

## Backend connection

- The backend URL can be changed in the app screen.
- The default is `http://127.0.0.1:8000`.
- For access from a phone, run the backend on the same device or configure a backend with HTTPS and a real network setup.
- Never hardcode provider API keys in the Android app.

## Authentication and storage

- Login uses `POST /api/v1/auth/login`.
- Dev authentication must be enabled on the backend.
- The session token is stored using Android `EncryptedSharedPreferences`.
- The app does not store Groq, OpenAI Realtime, or other provider credentials.

## Permissions

- `SYSTEM_ALERT_WINDOW`: overlay display only after explicit user action.
- `ACCESS_NETWORK_STATE`, `INTERNET`: backend communication.
- `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`: foreground overlay service.
- `RECORD_AUDIO`: declared for future voice capture; this skeleton does not stream audio.
- `POST_NOTIFICATIONS`: foreground service notification.

## Honest limitations

- No APK was built and no Android runtime test was performed.
- Overlay dragging uses a simple touch handler.
- Native `OpenAI Realtime` WebRTC/Media capture is not implemented.
- Existing dashboard, tasks, and reminders are accessed through the same backend; no second database exists.
EOF