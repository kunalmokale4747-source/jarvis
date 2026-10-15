// Optional server-mediated OpenAI Realtime client.
//
// The permanent API key never leaves the backend. This class only receives an
// ephemeral token returned by /api/v1/voice/realtime/session.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type RealtimeStatus = "idle" | "connecting" | "connected" | "listening" | "thinking" | "speaking" | "interrupted" | "disconnected" | "error";

export interface RealtimeCallbacks {
  onState?: (state: RealtimeStatus) => void;
  onTranscript?: (text: string) => void;
  onAssistantText?: (text: string) => void;
  onError?: (message: string) => void;
}

export class OpenAIRealtimeSession {
  private peer: RTCPeerConnection | null = null;
  private channel: RTCDataChannel | null = null;
  private localStream: MediaStream | null = null;
  private remoteAudio: HTMLAudioElement | null = null;
  private state: RealtimeStatus = "idle";
  private remoteStream: MediaStream | null = null;
  private playbackAllowed = true;

  constructor(private token: string, private callbacks: RealtimeCallbacks = {}) {
    if (typeof window !== "undefined") {
      const audio = new Audio();
      audio.autoplay = true;
      this.remoteAudio = audio;
    }
  }

  private setState(next: RealtimeStatus) {
    this.state = next;
    this.callbacks.onState?.(next);
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem("jarvis_token");
  }

  async connect(): Promise<void> {
    if (this.state === "connecting" || this.state === "connected") return;
    this.setState("connecting");

    let sessionInfo: {
      ephemeral_key?: string;
      expires_at?: number;
      sdp_endpoint?: string;
      voice?: string;
      model?: string;
    };
    try {
      const response = await fetch(`${API_URL}/api/v1/voice/realtime/session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.token}`,
        },
      });
      if (!response.ok) throw new Error(`session_setup_failed_${response.status}`);
      sessionInfo = await response.json();
    } catch (error) {
      this.setState("error");
      this.callbacks.onError?.(error instanceof Error ? error.message : "Voice session could not be created.");
      throw error;
    }

    const key = String(sessionInfo.ephemeral_key ?? "");
    if (!key) {
      this.setState("error");
      this.callbacks.onError?.("Server did not return a valid live-voice credential.");
      throw new Error("missing_ephemeral_credential");
    }

    let pc: RTCPeerConnection;
    try {
      pc = new RTCPeerConnection();
    } catch (error) {
      this.setState("error");
      this.callbacks.onError?.("WebRTC is unavailable in this browser or device.");
      throw error;
    }
    this.peer = pc;

    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (error) {
      await this.cleanup();
      this.setState("error");
      this.callbacks.onError?.("Microphone permission was denied or unavailable.");
      throw error;
    }

    for (const track of this.localStream.getTracks()) {
      pc.addTrack(track, this.localStream);
    }

    pc.ontrack = (event) => {
      const [stream] = event.streams;
      if (!stream || !this.remoteAudio) return;
      this.remoteStream = stream;
      this.remoteAudio.srcObject = stream;
      void this.remoteAudio.play().catch(() => {
        this.callbacks.onError?.("Browser blocked autoplay for generated speech. Tap to continue and keep the page visible.");
      });
    };

    pc.onconnectionstatechange = () => {
      const next = pc.connectionState;
      if (next === "connected") this.setState("connected");
      if (next === "failed" || next === "disconnected" || next === "closed") this.setState(next === "failed" ? "error" : "disconnected");
    };

    const channel = pc.createDataChannel("oai-events");
    this.channel = channel;
    channel.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const type = String(payload.type ?? "");
        if (type === "response.created") this.setState("thinking");
        if (type === "response.output_audio.delta" || type === "response.audio.delta") this.setState("speaking");
        if (type === "response.done") this.setState("connected");
        if (type === "response.cancelled") this.setState("interrupted");
        if (type === "input_audio_buffer.speech_started") {
          this.interrupt().catch(() => undefined);
          this.setState("connected");
        }
        const transcript = payload?.transcript || payload?.item?.content?.[0]?.transcript;
        if (typeof transcript === "string" && transcript.trim()) this.callbacks.onTranscript?.(transcript.trim());
        const text = payload?.response?.output?.[0]?.content?.[0]?.text;
        if (typeof text === "string" && text.trim()) this.callbacks.onAssistantText?.(text.trim());
        if (type === "error") {
          this.setState("error");
          this.callbacks.onError?.(String(payload?.error?.message ?? "Live voice session error."));
        }
      } catch {
        // Event payloads are advisory; keep the audio session alive.
      }
    };

    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await this.waitForIce(pc);
      const sdpResponse = await fetch(sessionInfo.sdp_endpoint ?? "https://api.openai.com/v1/realtime/calls", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/sdp",
        },
        body: pc.localDescription?.sdp ?? offer.sdp,
      });
      if (!sdpResponse.ok) {
        let detail = `realtime_sdp_failed_${sdpResponse.status}`;
        try {
          detail = await sdpResponse.text();
        } catch {
          // Keep the normalized code.
        }
        throw new Error(detail);
      }
      const answer = await sdpResponse.text();
      await pc.setRemoteDescription({ type: "answer", sdp: answer });
      this.setState("connected");
    } catch (error) {
      await this.cleanup();
      this.setState("error");
      this.callbacks.onError?.(error instanceof Error ? error.message : "Live voice connection failed.");
      throw error;
    }
  }

  private waitForIce(pc: RTCPeerConnection): Promise<void> {
    return new Promise((resolve) => {
      if (pc.iceGatheringState === "complete") {
        resolve();
        return;
      }
      const timeout = window.setTimeout(() => resolve(), 5000);
      pc.onicegatheringstatechange = () => {
        if (pc.iceGatheringState === "complete") {
          window.clearTimeout(timeout);
          resolve();
        }
      };
    });
  }

  mute(muted: boolean) {
    this.playbackAllowed = !muted;
    if (this.localStream) {
      for (const track of this.localStream.getAudioTracks()) track.enabled = !muted;
    }
    if (muted && this.remoteAudio) {
      this.remoteAudio.pause();
    } else {
      void this.remoteAudio?.play().catch(() => undefined);
    }
  }

  async interrupt(): Promise<void> {
    if (this.channel?.readyState === "open") {
      this.channel.send(JSON.stringify({ type: "response.cancel" }));
    }
    if (this.remoteAudio) {
      try {
        this.remoteAudio.pause();
        this.remoteAudio.srcObject = null;
      } catch {
        // continue cleanup
      }
    }
    this.setState("interrupted");
  }

  async disconnect(): Promise<void> {
    await this.cleanup();
    this.setState("disconnected");
  }

  private async cleanup(): Promise<void> {
    try {
      this.channel?.close();
    } catch {
      // Clean up anyway.
    }
    this.channel = null;
    try {
      this.peer?.close();
    } catch {
      // Continue cleanup.
    }
    this.peer = null;
    if (this.localStream) {
      for (const track of this.localStream.getTracks()) track.stop();
      this.localStream = null;
    }
    if (this.remoteAudio) {
      try {
        this.remoteAudio.pause();
        this.remoteAudio.srcObject = null;
      } catch {
        // Cleanup failure should not be user-facing.
      }
    }
  }

  connectionState(): RealtimeStatus {
    return this.state;
  }
}
