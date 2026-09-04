// P1.3 useVoice — Axiom #1/#2, HPP, Building LLM Apps fallback
import { useCallback, useRef, useState } from "react";
import { getToken, getUserId, getThreadId, authHeaders } from "@/lib/api";
import { getSupportedMimeType, createAnalyser, getAudioLevel } from "@/lib/audio";

type VoiceState = "idle" | "recording" | "processing" | "playing" | "error";

export function useVoice(opts?: { onTranscript?: (t: string) => void; onReply?: (t: string) => void }) {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const rafRef = useRef<number | null>(null);

  const tick = useCallback(() => {
    if (analyserRef.current) {
      const lv = getAudioLevel(analyserRef.current);
      setLevel(lv);
      rafRef.current = requestAnimationFrame(tick);
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    const t = getToken();
    if (!t) {
      setError("Sem token — va em Settings (Axiom #1)");
      setState("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
      const { ctx, analyser } = createAnalyser(stream);
      ctxRef.current = ctx;
      analyserRef.current = analyser;
      tick();
      const mime = getSupportedMimeType();
      const mr = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        setState("processing");
        try {
          const blob = new Blob(chunksRef.current, { type: mime });
          if (blob.size < 500) throw new Error("audio muito curto");
          // POST /stt — DRY via authHeaders (Axiom #2 X-User-Id obrigatorio)
          const fd = new FormData();
          fd.append("audio", blob, "audio.webm");
          const headers = authHeaders();
          const r = await fetch("/stt", { method: "POST", headers: headers as HeadersInit, body: fd });
          if (!r.ok) {
            const j = await r.json().catch(() => ({ detail: r.statusText }));
            throw new Error(j.detail || `STT ${r.status} ${r.statusText}`);
          }
          const j = await r.json();
          const txt: string = j.transcript || j.text || "";
          if (!txt) throw new Error("transcricao vazia");
          setTranscript(txt);
          opts?.onTranscript?.(txt);
          // POST /chat to get LLM reply (qwen2:0.5b <1s)
          const threadId = getThreadId();
          const chatR = await fetch("/chat", {
            method: "POST",
            headers: { ...authHeaders(), "Content-Type": "application/json" },
            body: JSON.stringify({ message: txt, thread_id: threadId, user_id: getUserId() }),
          });
          let replyText = txt;
          if (chatR.ok) {
            const cj = await chatR.json();
            replyText = cj.response || cj.message || txt;
            if (cj.status === "running" || cj.status === "pending_approval") replyText = cj.message || txt;
          }
          opts?.onReply?.(String(replyText).slice(0, 2000));
          // POST /tts to play
          try {
            const ttsR = await fetch("/tts", {
              method: "POST",
              headers: { ...authHeaders(), "Content-Type": "application/json" },
              body: JSON.stringify({ text: String(replyText).slice(0, 2000) }),
            });
            if (ttsR.ok) {
              const buf = await ttsR.arrayBuffer();
              if (buf.byteLength > 0) {
                const blobUrl = URL.createObjectURL(new Blob([buf], { type: ttsR.headers.get("content-type") || "audio/mpeg" }));
                const audio = new Audio(blobUrl);
                setState("playing");
                audio.onended = () => {
                  setState("idle");
                  URL.revokeObjectURL(blobUrl);
                };
                audio.onerror = () => setState("idle");
                await audio.play().catch(() => setState("idle"));
              } else setState("idle");
            } else setState("idle");
          } catch {
            setState("idle");
          }
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          setError(msg);
          setState("error");
        }
      };
      mediaRef.current = mr;
      mr.start(100);
      setState("recording");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg || "mic permission negada");
      setState("error");
    }
  }, [tick, opts]);

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    try {
      analyserRef.current = null;
    } catch {}
    try {
      ctxRef.current?.close();
    } catch {}
    try {
      if (mediaRef.current?.state !== "inactive") mediaRef.current?.stop();
    } catch {}
    try {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    } catch {}
    setLevel(0);
  }, []);

  const cancel = useCallback(() => {
    stop();
    setState("idle");
    setError(null);
  }, [stop]);

  return { state, transcript, error, level, start, stop, cancel, isRecording: state === "recording", isProcessing: state === "processing" || state === "playing" };
}
