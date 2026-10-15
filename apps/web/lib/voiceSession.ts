// Clean, replaceable interface for future real-time speech providers.
//
// The current implementation uses browser speech synthesis/recognition as a safe
// fallback. A signed real-time provider must be configured server-side and use
// only short-lived client credentials obtained through an authenticated API call.
//
// Audio bytes are never treated as commands; Availablenfunction arguments are
// validated server-side through the existing JARVIS tool registry before action.

export type VoiceConnectionState = "idle" | "connecting" | "connected" | "interrupted" | "disconnected" | "error";

export interface VoiceSession {
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  mute(muted: boolean): void;
  interrupt(): Promise<void>;
  connectionState(): VoiceConnectionState;
}

export function isLiveVoiceConfigured(): boolean {
  // Real-time language model providers do not automatically imply
  // duplex audio. Keep this false until an authenticated, credentialed,
  // explicitly enrolled voice backend is configured.
  return false;
}
