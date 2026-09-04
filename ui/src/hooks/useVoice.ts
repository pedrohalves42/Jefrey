// P1.3 useVoice â€” Axiom #1/#2, HPP, Building LLM Apps fallback
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
      try { (window as any).__setHudLevel?.(lv) } catch {}
      rafRef.current = requestAnimationFrame(tick);
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    const t = getToken();
    if (!t) {
      setError("Sem token â€” va em Settings (Axiom #1)");
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
        try { (window as any).__setHudState?.("thinking") } catch {}
        try {
          const blob = new Blob(chunksRef.current, { type: mime });
          if (blob.size < 500) throw new Error("audio muito curto");
          // POST /stt â€” DRY via authHeaders (Axiom #2 X-User-Id obrigatorio)
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
            const cj: any = await chatR.json();
            if (cj.status === "complete") replyText = cj.response || cj.message || txt;
            else if (cj.status === "running") {
              for (let i=0;i<40;i++) {
                await new Promise((r)=>setTimeout(r,1500));
                const pr = await fetch(`/chat/status/${encodeURIComponent(threadId)}`, { headers: authHeaders() as any });
                if (!pr.ok) continue;
                const pj: any = await pr.json().catch(()=>({}));
                if (pj.status === "complete") { replyText = pj.response || pj.message || txt; break; }
                if (pj.status === "error") break;
              }
            } else replyText = cj.response || cj.message || txt;
          }
          opts?.onReply?.(String(replyText).slice(0, 4000));
          // Local-AI-Companion: sentence-by-sentence TTS for minimal latency + lip-sync volume
          // POST /tts sentence streaming (Local-AI pipeline_runtime SentenceSplitter + isair tune_player)
          const sentences = String(replyText).slice(0,4000).split(/(?<=[.!?])\s+/).filter(s=>s.trim().length>4)
          const toSpeak = sentences.length ? sentences : [String(replyText).slice(0,4000)]
          // limit to first 4 sentences for latency (Stark: conciso)
          const limited = toSpeak.slice(0,4)
          let idx=0
          const playNext = async ()=>{
            if (idx>=limited.length) { setState("idle"); try { (window as any).__setHudState?.("idle") } catch {} ; return }
            const chunk = limited[idx++].trim()
            if (!chunk) { playNext(); return }
            try {
              const ttsR = await fetch("/tts", {
                method: "POST",
                headers: { ...authHeaders(), "Content-Type": "application/json" },
                body: JSON.stringify({ text: chunk }),
              });
              if (!ttsR.ok) { playNext(); return }
              const buf = await ttsR.arrayBuffer();
              if (buf.byteLength===0) { playNext(); return }
              const blobUrl = URL.createObjectURL(new Blob([buf], { type: ttsR.headers.get("content-type") || "audio/mpeg" }));
              const audio = new Audio(blobUrl);
              setState("playing");
              try { (window as any).__setHudState?.("speaking") } catch {}
              audio.onended = () => { URL.revokeObjectURL(blobUrl); playNext(); };
              audio.onerror = () => { URL.revokeObjectURL(blobUrl); playNext(); };
              await audio.play().catch(()=>{ URL.revokeObjectURL(blobUrl); playNext(); });
            } catch { playNext(); }
          }
          await playNext();
          try { (window as any).__setHudState?.("idle") } catch {}
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          setError(msg);
          setState("error");
          try { (window as any).__setHudState?.("idle") } catch {}
        }
      };
      mediaRef.current = mr;
      mr.start(100);
      setState("recording");
      try { (window as any).__setHudState?.("listening") } catch {}
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg || "mic permission negada");
      setState("error");
    }
  }, [tick, opts]);

  const stop = useCallback(() => {
    try { (window as any).__setHudState?.("idle") } catch {}
    try { (window as any).__setHudLevel?.(0) } catch {}
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
    try { (window as any).__setHudState?.("idle") } catch {}
  }, [stop]);

  return { state, transcript, error, level, start, stop, cancel, isRecording: state === "recording", isProcessing: state === "processing" || state === "playing" };
}

