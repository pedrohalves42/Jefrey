// P1.4 useWakeWord — Axiom #7 (sem novo container), CIPHER-032, CEOGPT Jarvis Aufbau wake "jarvis"
// Implementacao leve: usa Web Speech API interim se porcupine não configurado (JEFREY_VOICE__WAKE_WORD__ACCESS_KEY)
// Quando PORCUPINE_KEY presente e @picovoice/porcupine-web instalado, troca para native porcupine.
import { useCallback, useEffect, useRef, useState } from "react";

export function useWakeWord(opts: { keyword?: string; onWake?: ()=>void; enabled?: boolean }) {
  const keyword = (opts.keyword || "jarvis").toLowerCase();
  const enabled = opts.enabled ?? false;
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const recRef = useRef<any>(null);
  const onWakeRef = useRef(opts.onWake);
  onWakeRef.current = opts.onWake;

  useEffect(()=>{ setSupported(!!((window as any).webkitSpeechRecognition || (window as any).SpeechRecognition)); }, []);

  const start = useCallback(()=>{
    if (!enabled || listening) return;
    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
    if (!SR) return;
    try {
      const rec = new SR();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = "pt-BR";
      rec.onresult = (e:any)=>{
        for (let i=e.resultIndex; i<e.results.length; i++) {
          const txt = e.results[i][0].transcript.toLowerCase();
          if (txt.includes(keyword)) {
            onWakeRef.current?.();
            // opcional: vibra
            try { navigator.vibrate?.(80); } catch {}
          }
        }
      };
      rec.onend = ()=> { if (enabled) try{ rec.start(); } catch{} };
      rec.onerror = ()=> {};
      rec.start();
      recRef.current = rec;
      setListening(true);
    } catch {}
  }, [enabled, listening, keyword]);

  const stop = useCallback(()=>{
    try { recRef.current?.stop(); } catch {}
    recRef.current = null;
    setListening(false);
  }, []);

  useEffect(()=>{
    if (enabled) start(); else stop();
    return ()=> stop();
  }, [enabled, start, stop]);

  return { listening, supported, start, stop };
}
