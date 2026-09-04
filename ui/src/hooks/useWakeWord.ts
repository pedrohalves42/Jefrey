// useWakeWord — Axiom #7 sem novo container, CIPHER-032, CEOGPT Jarvis Aufbau wake "jefrey/jarvis" (alias)
// Adaptado de isair/jarvis listening/wake_detection.py (fuzzy_ratio 0.78) + Local-AI fallback
import { useCallback, useEffect, useRef, useState } from "react";

function fuzzyRatio(a: string, b: string): number {
  // isair difflib.SequenceMatcher ~ Levenshtein ratio simplified
  if (a===b) return 1
  const la=a.length, lb=b.length
  if (la===0||lb===0) return 0
  // bigram dice
  const bigrams=(s:string)=>{ const m=new Map<string,number>(); for(let i=0;i<s.length-1;i++){ const bg=s.slice(i,i+2); m.set(bg,(m.get(bg)||0)+1)} return m }
  const ma=bigrams(a), mb=bigrams(b)
  let inter=0
  for(const [k,c] of ma){ const cb=mb.get(k)||0; inter+=Math.min(c,cb) }
  return (2*inter)/(la+lb-1)
}
function isWakeDetected(textLower: string, keyword: string, aliases: string[], ratio=0.78): boolean {
  const all = new Set([keyword, ...aliases])
  if (textLower.includes(keyword)) return true
  for(const al of aliases) if(textLower.includes(al)) return true
  const tokens = textLower.split(/\s+/).map(t=> t.replace(/^[.,!?;:"'()\[\]{}]+|[.,!?;:"'()\[\]{}]+$/g,"")).filter(Boolean)
  for(const token of tokens){ for(const alias of all){ if(fuzzyRatio(alias, token) >= ratio) return true } }
  return false
}

export function useWakeWord(opts: { keyword?: string; aliases?: string[]; onWake?: ()=>void; enabled?: boolean }) {
  const keyword = (opts.keyword || "jefrey").toLowerCase();
  const aliases = (opts.aliases || ["jefrey","jarvis","sir","hey jarvis"]).map(s=>s.toLowerCase());
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
          const txt = String(e.results[i][0].transcript || "").toLowerCase();
          if (isWakeDetected(txt, keyword, aliases)) {
            onWakeRef.current?.();
            try { navigator.vibrate?.(90); } catch {}
            // chime feedback
            try { new Audio("/vite.svg").play().catch(()=>{}) } catch {}
          }
        }
      };
      rec.onend = ()=> { if (enabled) try{ rec.start(); } catch{} };
      rec.onerror = ()=> {};
      rec.start();
      recRef.current = rec;
      setListening(true);
    } catch {}
  }, [enabled, listening, keyword, aliases]);

  const stop = useCallback(()=>{
    try { recRef.current?.stop(); } catch {}
    recRef.current = null;
    setListening(false);
  }, []);

  useEffect(()=>{
    if (enabled) start(); else stop();
    return ()=> stop();
  }, [enabled, start, stop]);

  return { listening, supported, start, stop, isWakeDetected };
}
