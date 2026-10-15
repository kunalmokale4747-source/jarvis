"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, getToken } from "@/lib/api";
import { OpenAIRealtimeSession } from "@/lib/realtimeVoice";
import type {
  ChatMessage,
  NotificationItem,
  Reminder,
} from "@/lib/types";

type ChatSendResponse = {
  session_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  offline: boolean;
};

type AssistantTurn = {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
};

type VoiceStatus = "idle" | "listening" | "processing" | "speaking" | "error";

type SpeechRecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onstart: (() => void) | null;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

type MetaStatus = {
  ai?: {
    status?: string;
    detail?: string;
    providers?: string[];
    models?: string[];
  };
};

const LANGUAGE_OPTIONS = [
  { label: "English", code: "en-US", helper: "Standard English" },
  { label: "Hindi", code: "hi-IN", helper: "Hindi responses" },
  { label: "Hinglish", code: "hi-IN", helper: "Hindi + English practical mode" },
] as const;

function Ctor(): (new () => SpeechRecognitionInstance) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const STORAGE = "jarvis_voice_session_id";
const SETTINGS = "jarvis_voice_settings";

function loadSessionId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STORAGE);
  } catch {
    return null;
  }
}

function storeSessionId(id: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (id) window.localStorage.setItem(STORAGE, id);
    else window.localStorage.removeItem(STORAGE);
  } catch {
    // Private-mode storage failures must not break voice use.
  }
}


type AvatarState = "idle" | "listening" | "thinking" | "speaking" | "interrupted" | "disconnected" | "error";

function AnimeAvatar({ state }: { state: AvatarState }) {
  return (
    <div className="relative mx-auto h-64 w-full" aria-hidden="true">
      <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-cyan-950/40 to-transparent blur-2xl" />
      <div
        className={`relative mx-auto mt-6 h-56 w-48 ${state === "listening" ? "avatar-listening" : ""} ${state === "thinking" ? "avatar-thinking" : ""} ${state === "speaking" ? "avatar-speaking" : ""} ${state === "interrupted" ? "avatar-interrupted" : ""} ${state === "disconnected" ? "opacity-45 grayscale" : ""}`}
      >
        <div className="avatar-halo absolute inset-0 rounded-full bg-cyan-400/10" />
        <div className="avatar-float absolute left-1/2 top-5 -translate-x-1/2">
          <div className="h-32 w-32 rounded-full bg-gradient-to-b from-slate-100 via-cyan-100 to-indigo-200 shadow-2xl ring-2 ring-cyan-300/30 avatar-breath" />
          <div className="absolute left-4 top-10 h-4 w-7 rounded-full bg-slate-900/90 avatar-blink" />
          <div className="absolute right-4 top-10 h-4 w-7 rounded-full bg-slate-900/90 avatar-blink" />
          <div
            className={`absolute left-15 bottom-8 h-1.5 w-8 rounded-full bg-slate-900/80 transition-all duration-150 ${
              state === "speaking" ? "h-4 w-10 avatar-mouth" : state === "error" ? "h-2 w-6" : ""
            }`}
          />
          <div className="absolute -left-3 top-20 h-10 w-10 -rotate-12 rounded-full border border-pink-400/20 bg-pink-400/10 blur-[1px]" />
          <div className="absolute -right-3 top-20 h-10 w-10 rotate-12 rounded-full border border-pink-400/20 bg-pink-400/10 blur-[1px]" />
          <div className="absolute -top-8 h-16 w-32 rounded-t-[72px] bg-gradient-to-b from-indigo-500 to-cyan-700/80 shadow-lg" />
          <div className="absolute -top-2 left-10 h-12 w-12 rotate-[-18deg] rounded-full bg-indigo-400/70 blur-[1px]" />
          <div className="absolute -top-2 right-10 h-12 w-12 rotate-[18deg] rounded-full bg-indigo-400/70 blur-[1px]" />
        </div>
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-zinc-700/60 bg-zinc-950/70 px-4 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-zinc-100">
          {state}
        </div>
      </div>
    </div>
  );
}

export default function VoicePage() {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const listening = status === "listening";
  const [provider, setProvider] = useState<MetaStatus["ai"] | null>(null);
  const [supported, setSupported] = useState(false);
  const [ttsSupported, setTtsSupported] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [language, setLanguage] = useState<string>("en-US");
  const [voiceOutput, setVoiceOutput] = useState<"browser" | "android" | "text" | "live">("browser");
  const [liveStatus, setLiveStatus] = useState<"idle" | "connecting" | "connected" | "listening" | "thinking" | "speaking" | "interrupted" | "disconnected" | "error">("idle");
  const [liveMessage, setLiveMessage] = useState<string | null>(null);
  const [liveMuted, setLiveMuted] = useState(false);
  const liveSessionRef = useRef<OpenAIRealtimeSession | null>(null);
  const [realtimeConfigured, setRealtimeConfigured] = useState(false);
  const [nativeAvailable, setNativeAvailable] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [manual, setManual] = useState("");
  const [conversation, setConversation] = useState<AssistantTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderTime, setReminderTime] = useState("");
  const [reminderNote, setReminderNote] = useState("");
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const finalSentRef = useRef(false);
  const userStoppedRef = useRef(false);
  const statusRef = useRef<VoiceStatus>("idle");
  const spokenIds = useRef<Set<string>>(new Set());
  const transcriptRef = useRef("");

  const setStatusSync = useCallback((next: VoiceStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setStatusSync("idle");
  }, [setStatusSync]);

  const speakNative = useCallback(
    async (text: string, id: string) => {
      if (!autoSpeak || !nativeAvailable || spokenIds.current.has(id)) return;
      spokenIds.current.add(id);
      setStatusSync("speaking");
      try {
        await api("/api/v1/android/speak", {
          method: "POST",
          body: JSON.stringify({ text, language }),
        });
        setStatusSync("idle");
      } catch (err) {
        const msg = err instanceof ApiError ? err.whatHappened : "Native speech failed; use browser or text.";
        setError(msg);
        setStatusSync("error");
      }
    },
    [autoSpeak, language, nativeAvailable, setStatusSync],
  );

  const speak = useCallback(
    (text: string, id: string) => {
      if (!autoSpeak || spokenIds.current.has(id)) return;
      if (voiceOutput === "text" || voiceOutput === "live") {
        setStatusSync("idle");
        return;
      }
      spokenIds.current.add(id);
      if (voiceOutput === "android") {
        void speakNative(text, id);
        return;
      }
      if (!ttsSupported || typeof window === "undefined" || !("speechSynthesis" in window)) {
        setError("Browser speech is unavailable. Choose another output mode.");
        setStatusSync("error");
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = language;
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.onstart = () => setStatusSync("speaking");
      utterance.onend = () => setStatusSync("idle");
      utterance.onerror = () => {
        spokenIds.current.add(id);
        setStatusSync("idle");
      };
      setStatusSync("speaking");
      window.speechSynthesis.speak(utterance);
    },
    [autoSpeak, language, setStatusSync, speakNative, ttsSupported, voiceOutput],
  );

  const sendText = useCallback(
    async (text: string, source: "voice" | "text" = "text") => {
      const message = text.trim();
      if (!message) {
        if (source === "voice") setError("I did not catch a complete phrase. Please try again.");
        setStatusSync("idle");
        return;
      }
      transcriptRef.current = "";
      setTranscript("");
      setInterim("");
      setManual("");
      setError(null);
      setStatusSync("processing");

      const localId = `${Date.now()}-user`;
      setConversation((prev) => [
        ...prev,
        { id: localId, role: "user", text: message, createdAt: new Date().toISOString() },
      ]);

      try {
        const response = await api<ChatSendResponse>("/api/v1/chat", {
          method: "POST",
          body: JSON.stringify({ message, session_id: sessionId }),
        });
        setSessionId(response.session_id);
        storeSessionId(response.session_id);
        const reply = response.assistant_message.content;
        const replyId = response.assistant_message.id;
        setConversation((prev) => [
          ...prev,
          {
            id: replyId,
            role: "assistant",
            text: reply,
            createdAt: response.assistant_message.created_at,
          },
        ]);
        setStatusSync("idle");
        speak(reply, replyId);
      } catch (err) {
        const msg = err instanceof ApiError ? err.whatHappened : "I could not reach JARVIS.";
        setError(msg);
        setStatusSync("error");
      }
    },
    [sessionId, setStatusSync, speak],
  );

  const startListening = useCallback(() => {
    if (statusRef.current === "processing") return;
    if (voiceOutput === "live") {
      if (liveSessionRef.current) return;
      const token = getToken();
      if (!token) {
        setError("Live voice requires an authenticated JARVIS session.");
        setLiveStatus("error");
        return;
      }
      setLiveStatus("connecting");
      setStatusSync("processing");
      const session = new OpenAIRealtimeSession(token, {
        onState: (state) => {
          setLiveStatus(state);
          setStatusSync(
            state === "listening" || state === "connected"
              ? "listening"
              : state === "thinking" || state === "connecting"
                ? "processing"
                : state === "speaking"
                  ? "speaking"
                  : state === "error"
                    ? "error"
                    : "idle",
          );
        },
        onTranscript: (text) => {
          setTranscript(text);
          setManual("");
          setError(null);
        },
        onAssistantText: (text) => {
          setConversation((prev) => [...prev, { id: `live-${Date.now()}`, role: "assistant", text, createdAt: new Date().toISOString() }]);
        },
        onError: (message) => {
          setError(message);
          setStatusSync("error");
        },
      });
      setLiveStatus("connecting");
      liveSessionRef.current = session;
      session
        .connect()
        .then(() => {
          setLiveStatus("connected");
          setStatusSync("listening");
          setError(null);
        })
        .catch(() => {
          liveSessionRef.current = null;
          setLiveStatus("error");
          setStatusSync("error");
        });
      return;
    }
    const ctor = Ctor();
    if (!ctor) {
      setError("Speech recognition is not available in this browser or device. Use the text box instead.");
      setStatusSync("error");
      return;
    }
    setError(null);
    interveneStop();
    stopSpeaking();
    transcriptRef.current = "";
    finalSentRef.current = false;
    userStoppedRef.current = false;
    setTranscript("");
    setInterim("");

    let recognition: SpeechRecognitionInstance;
    try {
      recognition = new ctor();
    } catch (err) {
      setError("I could not start the microphone.");
      setStatusSync("error");
      return;
    }

    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
      setStatusSync("listening");
    };

    recognition.onresult = (event: any) => {
      let finalText = "";
      let interimText = "";
      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i][0]?.transcript ?? "";
        if (event.results[i].isFinal) finalText += `${result} `;
        else interimText += `${result} `;
      }
      const shown = (finalText || interimText).trim();
      transcriptRef.current = shown;
      setTranscript(finalText.trim());
      setInterim(interimText.trim());
      if (finalText.trim() && !finalSentRef.current) {
        finalSentRef.current = true;
        try {
          recognition.stop();
        } catch {
          // The browser may already be finished.
        }
        void sendText(finalText.trim(), "voice");
      }
    };

    recognition.onerror = (event: any) => {
      const code = event?.error ?? "unknown";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setError(
          "Microphone permission is denied. Allow access in browser settings, or use text input.",
        );
      } else if (code === "no-speech") {
        setError("I did not hear speech. Try again, or type your message.");
      } else if (code === "network") {
        setError("Speech recognition network error. Use text input or try again.");
      } else if (code === "aborted") {
        // User/desired interruption.
      } else {
        setError(`Microphone error: ${code}`);
      }
      setStatusSync(code === "aborted" ? "idle" : "error");
    };

    recognition.onend = () => {
      if (!finalSentRef.current && !userStoppedRef.current) {
        const heard = transcriptRef.current.trim();
        if (heard) {
          setError("I did not finish recognizing that phrase. Try again.");
        } else {
          setError(null);
        }
      }
      if (statusRef.current === "listening") setStatusSync("idle");
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch (err) {
      setError("I could not open the microphone.");
      setStatusSync("error");
    }
  }, [language, sendText, stopSpeaking, voiceOutput]);

  // `interveneStop` is declared after use in start; keep a local arrow here logically via assignment below.
  function interveneStop() {
    recognitionRef.current?.stop();
  }

  const stopListening = useCallback(() => {
    if (voiceOutput === "live" && liveSessionRef.current) {
      const session = liveSessionRef.current;
      liveSessionRef.current = null;
      void session.disconnect().finally(() => {
        setLiveStatus("disconnected");
        setStatusSync("idle");
      });
      return;
    }
    userStoppedRef.current = true;
    try {
      recognitionRef.current?.stop();
    } catch {
      // Already stopped.
    }
    setStatusSync("idle");
  }, [setStatusSync, voiceOutput]);

  const clearConversation = useCallback(() => {
    stopSpeaking();
    setConversation([]);
    setSessionId(null);
    storeSessionId(null);
    setTranscript("");
    setInterim("");
    setError(null);
    setStatusSync("idle");
  }, [setStatusSync, stopSpeaking]);

  const loadReminders = useCallback(async () => {
    try {
      const [rs, ns] = await Promise.all([
        api<Reminder[]>("/api/v1/reminders"),
        api<NotificationItem[]>("/api/v1/notifications?unread_only=true"),
      ]);
      setReminders(rs);
      setNotifications(ns);
    } catch {
      // Non-fatal: voice task results are already shown by chat.
    }
  }, []);

  const createReminder = useCallback(async () => {
    const title = reminderTitle.trim();
    if (!title || !reminderTime) {
      setError("A reminder needs a title and time.");
      setStatusSync("error");
      return;
    }
    const scheduled = new Date(reminderTime);
    if (Number.isNaN(scheduled.getTime())) {
      setError("That reminder time is invalid.");
      setStatusSync("error");
      return;
    }
    setError(null);
    setStatusSync("processing");
    try {
      await api("/api/v1/reminders", {
        method: "POST",
        body: JSON.stringify({
          title,
          message: reminderNote.trim() || null,
          scheduled_at: scheduled.toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
          channel: "web",
        }),
      });
      setReminderTitle("");
      setReminderTime("");
      setReminderNote("");
      await loadReminders();
      setConversation((prev) => [
        ...prev,
        {
          id: `reminder-${Date.now()}`,
          role: "assistant",
          text: `Reminder saved: ${title} at ${scheduled.toLocaleString()}.`,
          createdAt: new Date().toISOString(),
        },
      ]);
      setStatusSync("idle");
    } catch (err) {
      setError(err instanceof ApiError ? err.whatHappened : "Could not save the reminder.");
      setStatusSync("error");
    }
  }, [loadReminders, reminderNote, reminderTime, reminderTitle, setStatusSync]);

  const requestBrowserNotifications = useCallback(async () => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setError("Browser notifications are not supported in this environment.");
      setStatusSync("error");
      return;
    }
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setError("Browser notification permission is blocked. You can still use the reminder list in the app.");
        setStatusSync("error");
      } else {
        setError(null);
        setStatusSync("idle");
      }
    } catch {
      setError("Browser notification permission could not be requested.");
      setStatusSync("error");
    }
  }, [setStatusSync]);

  const cancelReminder = useCallback(
    async (id: string) => {
      try {
        await api(`/api/v1/reminders/${id}/cancel`, { method: "POST" });
        await loadReminders();
      } catch (err) {
        setError(err instanceof ApiError ? err.whatHappened : "Could not cancel that reminder.");
        setStatusSync("error");
      }
    },
    [loadReminders, setStatusSync],
  );

  useEffect(() => {
    setSupported(Boolean(Ctor()));
    setTtsSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    try {
      const raw = window.localStorage.getItem(SETTINGS);
      if (raw) {
        const saved = JSON.parse(raw);
        if (typeof saved.autoSpeak === "boolean") setAutoSpeak(saved.autoSpeak);
        if (typeof saved.language === "string") setLanguage(saved.language);
      }
    } catch {
      // Ignore malformed local preferences.
    }
    setSessionId(loadSessionId());
    void (async () => {
      try {
        const meta = await api<MetaStatus>("/api/v1/meta");
        setProvider(meta.ai ?? null);
      } catch {
        setProvider({ status: "unknown" });
      }
    })();
    void (async () => {
      try {
        const caps = await api<any>("/api/v1/android/capabilities");
        setNativeAvailable(Boolean(caps?.termux_api?.["termux-tts-speak"]));
      } catch {
        setNativeAvailable(false);
      }
    })();
    void loadReminders();
    void (async () => {
      try {
        const status = await api<any>("/api/v1/voice/realtime/status");
        setRealtimeConfigured(Boolean(status?.configured));
      } catch {
        setRealtimeConfigured(false);
      }
    })();
  }, [loadReminders]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SETTINGS, JSON.stringify({ autoSpeak, language, voiceOutput }));
    } catch {
      // Non-fatal.
    }
  }, [autoSpeak, language, voiceOutput]);

  useEffect(() => {
    const timer = window.setInterval(() => void loadReminders(), 15000);
    return () => window.clearInterval(timer);
  }, [loadReminders]);

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    if (notifications.length === 0) return;
    if (Notification.permission !== "granted") return;
    notifications.forEach((n) => {
      new Notification(n.title, { body: n.body ?? undefined });
      void api(`/api/v1/notifications/${n.id}/read`, { method: "POST" }).catch(() => undefined);
    });
  }, [notifications]);

  const avatarState: AvatarState = supported
    ? voiceOutput === "live"
      ? liveStatus === "listening" || liveStatus === "connected"
        ? "listening"
        : liveStatus === "thinking" || liveStatus === "connecting"
          ? "thinking"
          : liveStatus === "speaking"
            ? "speaking"
            : liveStatus === "interrupted"
              ? "interrupted"
              : liveStatus === "error" || liveStatus === "disconnected"
                ? liveStatus
                : "idle"
      : status === "idle"
        ? "idle"
        : status === "listening"
          ? "listening"
          : status === "processing"
            ? "thinking"
            : status === "speaking"
              ? "speaking"
              : status === "error"
                ? "error"
                : "idle"
    : "disconnected";

  const statusLabel =
    status === "listening"
      ? "Listening"
      : status === "processing"
        ? "Processing"
        : status === "speaking"
          ? "Speaking"
          : status === "error"
            ? "Error"
            : "Idle";

  const providerOnline = provider?.status === "online";
  const providerText =
    provider?.status === "online"
      ? `AI provider online: ${(provider.models ?? []).join(", ") || "configured"}`
      : provider?.status === "not_configured"
        ? "AI provider offline or stub — non-AI features remain available"
        : provider?.status === "error"
          ? "Configured AI provider could not be constructed"
          : "AI provider status unavailable";

  return (
    <div className="relative min-h-[calc(100svh-6rem)] overflow-hidden">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-3 py-4 text-zinc-100 sm:gap-6 sm:px-4 sm:py-6">
        <AnimeAvatar state={avatarState} />
      <style>{`
        @keyframes avatarBreath { 0%,100% { transform: scale(1); } 50% { transform: scale(1.015); } }
        @keyframes avatarBlink { 0%,94%,100% { transform: scaleY(1); } 95%,98% { transform: scaleY(0.1); } }
        @keyframes avatarFloat { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
        @keyframes avatarMouth { 0%,100% { height: 6px; width: 34px; } 50% { height: 15px; width: 40px; } }
        @keyframes avatarListening { 0%,100% { box-shadow: 0 0 0 0 rgba(34,211,238,.25); } 50% { box-shadow: 0 0 0 18px rgba(34,211,238,0); } }
        @keyframes avatarThinking { 0%,100% { opacity:.6; transform: rotate(-6deg);} 50% { opacity:1; transform: rotate(6deg);} }
        @keyframes avatarShake { 0%,100% { transform: translateX(0); } 25% { transform: translateX(-4px); } 75% { transform: translateX(4px); } }
        .avatar-breath { animation: avatarBreath 4s ease-in-out infinite; }
        .avatar-blink { animation: avatarBlink 4.8s infinite; }
        .avatar-float { animation: avatarFloat 5s ease-in-out infinite; }
        .avatar-halo.avatar-listening::before { }
        .avatar-listening { animation: avatarListening 1.8s infinite; border-radius: 9999px; }
        .avatar-thinking { animation: avatarThinking .85s ease-in-out infinite; }
        .avatar-speaking .avatar-mouth { animation: avatarMouth .32s infinite; }
        .avatar-interrupted { animation: avatarShake .35s 2; }
      `}</style>
      <header className="sticky top-0 z-10 space-y-2">
          <div className="rounded-2xl border border-cyan-900/60 bg-zinc-950/85 px-4 py-4 shadow-xl backdrop-blur">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cyan-400/90">
                  JARVIS Voice
                </p>
                <h1 className="mt-1 text-2xl font-semibold text-zinc-50">Hands-free assistant</h1>
                <p className="mt-1 text-sm text-zinc-400">
                  Speak or type. Responses are shown and can be read aloud.
                </p>
              </div>
              <div className="flex min-w-24 flex-col items-end gap-2">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    status === "listening"
                      ? "bg-red-950 text-red-200 ring-1 ring-red-700"
                      : status === "processing"
                        ? "bg-cyan-950 text-cyan-200 ring-1 ring-cyan-700"
                        : status === "speaking"
                          ? "bg-amber-950 text-amber-200 ring-1 ring-amber-700"
                          : status === "error"
                            ? "bg-red-950 text-red-200 ring-1 ring-red-700"
                            : "bg-zinc-900 text-zinc-200 ring-1 ring-zinc-700"
                  }`}
                  role="status"
                  aria-live="polite"
                >
                  {statusLabel}
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-xs ${
                    providerOnline ? "text-emerald-300" : "text-zinc-400"
                  }`}
                  title={provider?.detail}
                >
                  {providerText}
                </span>
              </div>
            </div>
          </div>
        </header>

        {!supported ? (
          <section className="rounded-xl border border-amber-800 bg-amber-950/30 p-4">
            <h2 className="text-sm font-semibold text-amber-200">Speech recognition unavailable</h2>
            <p className="mt-1 text-sm text-amber-100/80">
              This browser or device does not expose speech recognition. Text input still works, and web navigation does not require microphone access.
            </p>
          </section>
        ) : null}

        <section className="grid grid-cols-1 items-center gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 shadow-lg">
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={listening ? stopListening : startListening}
              disabled={status === "processing"}
              className={`h-28 w-28 shrink-0 rounded-full border text-base font-bold shadow-lg transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50 ${
                listening
                  ? "border-red-500 bg-red-950/80 text-red-200 ring-red-900"
                  : status === "processing"
                    ? "border-cyan-700 bg-cyan-950/70 text-cyan-200"
                    : "border-cyan-500 bg-cyan-950/40 text-cyan-200 ring-cyan-950"
              }`}
              aria-label={listening ? "Stop listening" : "Start listening"}
            >
              {listening ? "Stop" : "Mic"}
            </button>
            <div className="w-full space-y-3">
              <div>
                <p className="text-sm text-zinc-400">Language</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <button
                      key={opt.code + opt.label}
                      type="button"
                      onClick={() => setLanguage(opt.code)}
                      className={`rounded-full border px-4 py-2 text-sm ${
                        language === opt.code
                          ? "border-cyan-500 bg-cyan-950 text-cyan-200"
                          : "border-zinc-700 bg-zinc-950 text-zinc-300"
                      }`}
                    >
                      {opt.label}
                      <span className="ml-1 text-xs text-zinc-500">{opt.helper}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div>
              <p className="text-sm text-zinc-400">Speech output</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {[
                  { value: "live", label: "Live AI voice", enabled: realtimeConfigured },
                  { value: "browser", label: "Browser", enabled: ttsSupported },
                  { value: "android", label: "Native (Termux)", enabled: nativeAvailable },
                  { value: "text", label: "Text only", enabled: true },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    disabled={!opt.enabled}
                    onClick={() => setVoiceOutput(opt.value as "browser" | "android" | "text")}
                    className={`rounded-full border px-3 py-1 text-sm ${
                      voiceOutput === opt.value
                        ? "border-cyan-500 bg-cyan-950 text-cyan-200"
                        : "border-zinc-700 bg-zinc-950 text-zinc-300"
                    } disabled:opacity-40`}
                  >
                    {opt.label}{!opt.enabled ? " unavailable" : ""}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-sm text-zinc-300" aria-live="polite">
                {status === "listening"
                  ? "Listening… speak naturally."
                  : status === "processing"
                    ? "Processing your request…"
                    : status === "speaking"
                      ? "JARVIS is speaking."
                      : status === "error"
                        ? "Something needs attention."
                        : "Tap Mic and speak, or type below."}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={stopSpeaking}
              disabled={status !== "speaking"}
              className="rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-200 disabled:opacity-40"
            >
              Stop speaking
            </button>
            {voiceOutput === "live" ? (
              <button
                type="button"
                onClick={() => {
                  const next = !liveMuted;
                  liveSessionRef.current?.mute(next);
                  setLiveMuted(next);
                }}
                className="rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-200"
              >
                {liveMuted ? "Unmute mic" : "Mute mic"}
              </button>
            ) : null}
            <label className="flex items-center gap-2 rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-200">
              <input
                type="checkbox"
                className="h-4 w-4 accent-cyan-500"
                checked={autoSpeak}
                onChange={(e) => setAutoSpeak(e.target.checked)}
              />
              Speak responses
            </label>
            <button
              type="button"
              onClick={clearConversation}
              className="rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-200"
            >
              Clear chat
            </button>
          </div>
        </section>

      {voiceOutput === "live" ? (
        <section className="rounded-xl border border-cyan-900 bg-cyan-950/30 p-4">
          <p className="text-sm font-semibold text-cyan-200">Live voice mode: {liveStatus}</p>
          <p className="mt-1 text-sm text-cyan-100/80">
            {liveStatus === "connecting"
              ? "Connecting to the OpenAI Realtime provider using a server-minted ephemeral credential."
              : liveStatus === "connected" || liveStatus === "listening"
                ? "Microphone audio is streaming and playback will use generated audio."
                : liveStatus === "speaking"
                  ? "Assistant is speaking. Speak to interrupt."
                  : liveStatus === "error"
                    ? liveMessage ?? "Live voice failed; switch to browser or text fallback."
                    : "Connection is stopped. Tap Mic to connect."}
          </p>
        </section>
      ) : null}

        <section
          className="rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4"
          aria-live="polite"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-100">Live transcript</h2>
            <span className="text-xs text-zinc-500">Speech is not recorded or uploaded as audio.</span>
          </div>
          <p className="whitespace-pre-wrap rounded-xl border border-zinc-800 bg-zinc-900 p-3 text-sm text-zinc-100">
            {interim || transcript || "Listening transcript will appear here."}
          </p>
          {error ? (
            <p
              role="alert"
              className="mt-3 rounded-xl border border-red-900 bg-red-950/40 p-3 text-sm text-red-200"
            >
              {error}
            </p>
          ) : null}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-zinc-100">Conversation</h2>
          <div className="max-h-80 space-y-2 overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-950/70 p-3">
            {conversation.length === 0 ? (
              <p className="p-3 text-sm text-zinc-400">
                Say or type something to start. Example: “Hey Jarvis, kya haal hai?”
              </p>
            ) : (
              conversation.map((turn) => (
                <article
                  key={turn.id}
                  className={`rounded-xl border px-3 py-2 text-sm ${
                    turn.role === "user"
                      ? "ml-4 border-zinc-800 bg-zinc-900 text-zinc-100"
                      : "mr-4 border-cyan-900/60 bg-cyan-950/30 text-cyan-50"
                  }`}
                >
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
                    {turn.role}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap break-words">{turn.text}</p>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
          <h2 className="text-sm font-semibold text-zinc-100">Text input fallback</h2>
          <p className="mb-3 mt-1 text-xs text-zinc-400">
            Text is always available when speech plugins are blocked, unavailable, or inaccurate.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <textarea
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              rows={2}
              placeholder="Type in English, Hindi, or Hinglish"
              className="min-h-12 flex-1 resize-none rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-cyan-700 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => void sendText(manual, "text")}
              disabled={status === "processing" || manual.trim().length === 0}
              className="h-12 self-end rounded-xl border border-cyan-600 px-5 text-sm font-semibold text-cyan-200 disabled:opacity-40 sm:self-auto"
            >
              Send
            </button>
          </div>
        </section>

        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
          <h2 className="text-sm font-semibold text-zinc-100">Quick reminder</h2>
          <p className="mt-1 text-xs text-zinc-400">
            reminders are created through existing backend APIs; speech is only the transcript.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <input
              value={reminderTitle}
              onChange={(e) => setReminderTitle(e.target.value)}
              placeholder="Reminder title"
              className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
            />
            <input
              type="datetime-local"
              value={reminderTime}
              onChange={(e) => setReminderTime(e.target.value)}
              className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
            />
            <input
              value={reminderNote}
              onChange={(e) => setReminderNote(e.target.value)}
              placeholder="Optional note"
              className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void createReminder()}
              className="rounded-xl border border-cyan-600 px-4 py-2 text-sm font-semibold text-cyan-200"
            >
              Save reminder
            </button>
            <button
              type="button"
              onClick={() => void requestBrowserNotifications()}
              className="rounded-xl border border-zinc-700 px-4 py-2 text-sm text-zinc-200"
            >
              Enable browser notifications
            </button>
          </div>
          <ul className="mt-4 space-y-2">
            {reminders.length === 0 ? (
              <li className="text-sm text-zinc-500">No reminders yet.</li>
            ) : (
              reminders.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950 p-3 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate text-zinc-100">{r.title}</p>
                    <p className="text-xs text-zinc-500">
                      {new Date(r.scheduled_at).toLocaleString()} · {r.status}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void cancelReminder(r.id)}
                    className="shrink-0 text-xs font-medium text-red-300"
                  >
                    Cancel
                  </button>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}

