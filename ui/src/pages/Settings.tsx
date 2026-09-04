import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getToken, getUserId, getThreadId, setToken, setUserId, setThreadId } from "@/lib/api"
import { useWakeWord } from "@/hooks/useWakeWord"

export default function Settings() {
  // P1.4 Voz Wake + TTS picker (Axiom #1/5, Mark-LII 5 vozes) {
  const [token, setTokenState] = useState("")
  const [userId, setUserIdState] = useState("")
  const [threadId, setThreadIdLocal] = useState("")
  const [showToken, setShowToken] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    setTokenState(getToken() || "")
    setUserIdState(getUserId())
    setThreadIdLocal(getThreadId())
  }, [])

  function save() {
    // nunca loga token (CIPHER-010 redact_pii)
    setToken(token.trim())
    setUserId(userId.trim() || "demo")
    setThreadId(threadId.trim() || "demo-1")
    setTestResult("Salvo em localStorage. Chat/Memory ja usam este token + user_id (Axiom #2).")
  }

  async function testAuth() {
    setTesting(true); setTestResult(null)
    try {
      const headers: Record<string, string> = {}
      if (token.trim()) headers["Authorization"] = `Bearer ${token.trim()}`
      const res = await fetch("/health", { headers })
      const body = await res.text()
      setTestResult(`GET /health ${res.status}: ${body.slice(0, 500)}`)
      // tamb�m testa /chat sem enviar mensagem para ver 401 vs 200
      const res2 = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token.trim() ? { Authorization: `Bearer ${token.trim()}` } : {}) },
        body: JSON.stringify({ message: "teste settings", thread_id: threadId || "demo-1", user_id: userId || "demo" }),
      })
      const chatText = await res2.text(); setTestResult((prev) => (prev || "") + ` | POST /chat ${res2.status} ${chatText.slice(0, 300)}`)
    } catch (e) {
      setTestResult(e instanceof Error ? e.message : String(e))
    } finally { setTesting(false) }
  }

  function clear() {
    try { localStorage.removeItem("jefrey_token"); localStorage.removeItem("jefrey_user_id"); localStorage.removeItem("jefrey_thread_id"); } catch {}
    setTokenState(""); setUserIdState("demo"); setThreadIdLocal("demo-1")
    setTestResult("Limpo. Agora /chat voltara a 401 (fail-closed).")
  }

    const [vozWake, setVozWake] = useState(()=> { try { return localStorage.getItem("jefrey_wake_enabled")==="1"; } catch { return false; } });
  const [vozVoice, setVozVoice] = useState(()=> { try { return localStorage.getItem("jefrey_voice_id") || "pt_BR-faber-medium"; } catch { return "pt_BR-faber-medium"; } });
  const wake = useWakeWord({ enabled: vozWake, keyword: "jarvis", onWake: ()=> { try { document.querySelector<HTMLButtonElement>('[aria-label="Falar com Jefrey"]')?.click(); } catch {} } });
  useEffect(()=>{ try { localStorage.setItem("jefrey_wake_enabled", vozWake?"1":"0"); } catch {} }, [vozWake]);
  useEffect(()=>{ try { localStorage.setItem("jefrey_voice_id", vozVoice); } catch {} }, [vozVoice]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Settings <Badge variant="secondary">CIPHER-031</Badge>
            <Badge variant="outline">localStorage</Badge>
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Unico lugar que persiste Bearer token (nunca em URL, Livro 3 cap8) + user_id/thread_id (Axiom #2). Token nunca logado (CIPHER-010).
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Bearer token</label>
            <div className="flex gap-2">
              <input
                className="flex-1 rounded-md border px-3 py-2 text-sm font-mono"
                type={showToken ? "text" : "password"}
                placeholder="Bearer token (em dev: JEFREY_API__SECRET_KEY)"
                value={token}
                onChange={(e) => setTokenState(e.target.value)}
                aria-label="bearer token"
                autoComplete="off"
              />
              <Button variant="outline" onClick={() => setShowToken((v) => !v)}>{showToken ? "Ocultar" : "Mostrar"}</Button>
            </div>
            <p className="text-xs text-muted-foreground">Salvo em localStorage jeyfry_token � nunca enviado em query.</p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">user_id (Axiom #2 isolamento)</label>
              <input
                className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                placeholder="demo"
                value={userId}
                onChange={(e) => setUserIdState(e.target.value)}
                aria-label="user_id"
              />
              <p className="text-xs text-muted-foreground">Todo POST leva este user_id � sem default system.</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">thread_id</label>
              <input
                className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                placeholder="demo-1"
                value={threadId}
                onChange={(e) => setThreadIdLocal(e.target.value)}
                aria-label="thread_id"
              />
              <p className="text-xs text-muted-foreground">Persistido como jefrey_thread_id.</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={save}>Salvar</Button>
            <Button variant="outline" onClick={testAuth} disabled={testing}>{testing ? "Testando�" : "Testar /health + /chat"}</Button>
            <Button variant="destructive" onClick={clear}>Limpar</Button>
            <Badge variant="secondary">ENV dev</Badge>
            <a href="/docs" target="_blank" rel="noreferrer" className="text-sm underline">Abrir /docs</a>
          </div>

          {testResult && <div className="rounded-md border bg-muted p-3 text-sm whitespace-pre-wrap break-words">{testResult}</div>}

          <div className="rounded-md border p-3 text-xs bg-muted/30">
            <div className="font-medium mb-1">Como usar como 1 programa (Guia leigo):</div>
            <ol className="list-decimal ml-4 space-y-1">
              <li>Cole seu Bearer token acima e clique Salvar.</li>
              <li>V� em Chat e envie mensagem � agora POST /chat 200 (antes 401).</li>
              <li>V� em Memoria e busque � POST /memory/search com mesmo user_id.</li>
              <li>Approvals/Observability leem /approvals e /metrics vivos (15s).</li>
            </ol>
          </div>
        </CardContent>
      </Card>
    
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">Voz — STT/TTS + Wake &quot;jarvis&quot; <Badge variant="secondary">P1</Badge></CardTitle>
          <p className="text-sm text-muted-foreground">Microfone MediaRecorder 16k → POST /stt (whisper small) → /chat qwen2:0.5b → POST /tts. Wake usa Web Speech &quot;jarvis&quot; (porcupine quando key configurada).</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={vozWake} onChange={(e)=> setVozWake(e.target.checked)} />
              Wake &quot;jarvis&quot; {wake.listening ? "(ouvindo...)" : "(off)"} {!wake.supported && <span className="text-xs text-muted-foreground">— navegador sem SpeechRecognition</span>}
            </label>
            <Badge variant={wake.listening ? "success" : "outline"}>{wake.listening ? "wake ativo" : "wake off"}</Badge>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">Voz TTS (Mark-LII 5 vozes + Piper)</label>
            <select value={vozVoice} onChange={(e)=> setVozVoice(e.target.value)} className="rounded-md border px-3 py-2 text-sm">
              <option value="pt_BR-faber-medium">Faber PT-BR (piper local, sem custo)</option>
              <option value="Charon">Charon — masc grave (ElevenLabs)</option>
              <option value="Puck">Puck — masc jovem (ElevenLabs)</option>
              <option value="Kore">Kore — fem suave (ElevenLabs)</option>
              <option value="Fenrir">Fenrir — masc forte (ElevenLabs)</option>
              <option value="Aoede">Aoede — fem clara (ElevenLabs)</option>
            </select>
            <p className="text-xs text-muted-foreground">Requer JEFREY_TTS__API_KEY para ElevenLabs; sem key usa piper/pyttsx3 fallback (Building LLM Apps).</p>
          </div>
          <div className="rounded-md border p-3 text-xs bg-muted/20">
            <div>STT: <span className="font-mono">small pt int8</span> — mock dev via JEFREY_STT__MOCK=1</div>
            <div>LLM: <span className="font-mono">qwen2:0.5b 352MB</span> (workaround OOM 8b 3.3GB)</div>
            <div>HUD pulse: Analyser reativa (CEOGPT) no botao mic</div>
          </div>
        </CardContent>
      </Card>

</div>
  )
}

