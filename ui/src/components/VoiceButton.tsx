// P1.3 VoiceButton — CEOGPT glass + neon pulse (Livro 4 cap11, Mark-LII HUD)
import { useVoice } from "@/hooks/useVoice";
import { Button } from "@/components/ui/button";
import { Mic, MicOff, Loader2, Volume2 } from "lucide-react";

export function VoiceButton({ onTranscript, onReply }: { onTranscript?: (t:string)=>void; onReply?: (t:string)=>void }) {
  const { state, error, level, start, stop } = useVoice({ onTranscript, onReply });
  const isRec = state==="recording";
  const isBusy = state==="processing" || state==="playing";
  const scale = 1 + level * 0.6; // pulse 1.0..1.6 (CEOGPT HUD)

  return (
    <div className="flex flex-col items-center gap-1">
      <Button
        type="button"
        variant={isRec ? "destructive" : "secondary"}
        size="icon"
        aria-label={isRec ? "Parar gravacao" : "Falar com Jefrey"}
        onClick={()=> isRec ? stop() : start()}
        disabled={isBusy}
        className="relative h-12 w-12 rounded-full border shadow-lg transition-transform"
        style={{ transform: isRec ? `scale(${scale})` : undefined, boxShadow: isRec ? "0 0 20px rgba(34,211,238,0.8)" : undefined }}
      >
        {isBusy ? <Loader2 className="h-6 w-6 animate-spin" /> : isRec ? <MicOff className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
        {isRec && <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-cyan-400 animate-pulse border-2 border-background" />}
      </Button>
      <span className="text-[10px] text-muted-foreground flex items-center gap-1">
        {isRec ? "gravando..." : isBusy ? "processando..." : "falar"}
        {state==="playing" && <Volume2 className="h-3 w-3" />}
      </span>
      {error && <span className="text-xs text-destructive max-w-[180px] truncate" title={error}>{error}</span>}
    </div>
  );
}
