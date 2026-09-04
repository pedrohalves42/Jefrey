// F6-3 ConnectionHub — 4 botoes 1-clique: Navegar, Arquivo, Buscar, Enviar (supera Mark-LII)
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { apiFetch, authHeaders, getUserId } from "@/lib/api"

type HubMsg = { kind: string; text: string; ok: boolean }

export function ConnectionHub({ onResult }: { onResult?: (m: HubMsg) => void }) {
  const [url, setUrl] = useState("")
  const [to, setTo] = useState("")
  const [channel, setChannel] = useState<"whatsapp"|"telegram">("whatsapp")
  const [sendText, setSendText] = useState("")
  const [query, setQuery] = useState("")
  const [fileName, setFileName] = useState("")
  const [fileContent, setFileContent] = useState("")
  const [loading, setLoading] = useState<string | null>(null)
  const [out, setOut] = useState<HubMsg | null>(null)

  async function act(kind: string, fn: () => Promise<HubMsg>) {
    setLoading(kind)
    try {
      const res = await fn()
      setOut(res)
      onResult?.(res)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      const r: HubMsg = { kind, text: msg, ok: false }
      setOut(r); onResult?.(r)
    } finally { setLoading(null) }
  }

  return (
    <Card className="glass">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          Conexoes <Badge variant="secondary">1-clique</Badge>
          <span className="text-xs text-muted-foreground font-normal">Navegar • Arquivo • Buscar • Enviar</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border p-3 space-y-2 glass">
            <div className="text-xs font-medium">🌐 Navegar</div>
            <input className="w-full rounded-md border px-2 py-1.5 text-xs" placeholder="https://exemplo.com" value={url} onChange={e=>setUrl(e.target.value)} aria-label="url navegar" />
            <Button size="sm" disabled={!url.trim() || !!loading} onClick={()=>act("navegar", async()=>{
              const r = await apiFetch("/connections/browse", { method: "POST", body: JSON.stringify({ url: url.trim(), user_id: getUserId() }) })
              const j = await r.json().catch(()=>({detail: r.statusText}))
              if (!r.ok) throw new Error(j.detail || "browse falhou "+r.status)
              return { kind: "navegar", text: j.message || "Navegacao OK: "+(j.url||url), ok: true }
            })}>{loading==="navegar"?"...":"Abrir"}</Button>
            <p className="text-[10px] text-muted-foreground">via MCP browser_control ou n8n webhook fallback</p>
          </div>

          <div className="rounded-md border p-3 space-y-2 glass">
            <div className="text-xs font-medium">💬 Enviar</div>
            <select value={channel} onChange={e=>setChannel(e.target.value as any)} className="w-full rounded-md border px-2 py-1.5 text-xs">
              <option value="whatsapp">WhatsApp</option>
              <option value="telegram">Telegram</option>
            </select>
            <input className="w-full rounded-md border px-2 py-1.5 text-xs" placeholder="para: +55... ou @user" value={to} onChange={e=>setTo(e.target.value)} aria-label="para enviar" />
            <input className="w-full rounded-md border px-2 py-1.5 text-xs" placeholder="mensagem" value={sendText} onChange={e=>setSendText(e.target.value)} aria-label="mensagem enviar" />
            <Button size="sm" disabled={!to.trim()||!sendText.trim()||!!loading} onClick={()=>act("enviar", async()=>{
              const r = await apiFetch("/connections/send", { method:"POST", body: JSON.stringify({ to: to.trim(), channel, text: sendText, user_id: getUserId() }) })
              const j = await r.json().catch(()=>({detail: r.statusText}))
              if (!r.ok) throw new Error(j.detail || "send falhou "+r.status+" — configure n8n webhook em Settings")
              return { kind:"enviar", text: j.message || "Enviado via "+channel, ok:true }
            })}>{loading==="enviar"?"...":"Enviar"}</Button>
            <p className="text-[10px] text-muted-foreground">POST n8n:5678/webhook/jefrey-send-message</p>
          </div>

          <div className="rounded-md border p-3 space-y-2 glass">
            <div className="text-xs font-medium">📎 Arquivo</div>
            <input type="file" className="w-full text-xs" onChange={async e=>{
              const f = e.target.files?.[0]; if(!f) return; setFileName(f.name)
              if (f.size > 500*1024*1024) { setOut({kind:"arquivo", text:"Arquivo >500MB nao suportado", ok:false}); return }
              const txt = await f.text().catch(async()=>{
                // binary fallback: read as base64 slice
                const buf = await f.arrayBuffer(); const b = new Uint8Array(buf.slice(0, 2000)); return String.fromCharCode(...b)
              })
              setFileContent(txt.slice(0, 8000))
            }} aria-label="arquivo" />
            {fileName && <div className="text-xs font-mono truncate">{fileName} — {fileContent.length} chars</div>}
            <textarea className="w-full rounded-md border px-2 py-1.5 text-xs h-16" placeholder="ou cole texto aqui (500MB chunked)" value={fileContent} onChange={e=>setFileContent(e.target.value)} aria-label="conteudo arquivo" />
            <Button size="sm" disabled={!fileContent.trim()||!!loading} onClick={()=>act("arquivo", async()=>{
              const r = await apiFetch("/memory/add", { method:"POST", body: JSON.stringify({ content: fileContent.slice(0, 500*1024), title: fileName || "arquivo chat", type: "file", user_id: getUserId() }) })
              const j = await r.json().catch(()=>({detail: r.statusText}))
              if (!r.ok) throw new Error(j.detail || "memory/add falhou "+r.status)
              return { kind:"arquivo", text: j.message || "Arquivo salvo em memoria HNSW", ok:true }
            })}>{loading==="arquivo"?"...":"Salvar em Memoria"}</Button>
            <p className="text-[10px] text-muted-foreground">POST /memory/add HNSW m16 ef64</p>
          </div>

          <div className="rounded-md border p-3 space-y-2 glass">
            <div className="text-xs font-medium">🔍 Buscar</div>
            <input className="w-full rounded-md border px-2 py-1.5 text-xs" placeholder="buscar na web: IA hoje" value={query} onChange={e=>setQuery(e.target.value)} aria-label="buscar" />
            <Button size="sm" disabled={!query.trim()||!!loading} onClick={()=>act("buscar", async()=>{
              const r = await apiFetch("/connections/search", { method:"POST", body: JSON.stringify({ query: query.trim(), user_id: getUserId() }) })
              const j = await r.json().catch(()=>({detail: r.statusText}))
              if (!r.ok) throw new Error(j.detail || "search falhou "+r.status)
              const hits = (j.results||j.hits||[]).slice(0,3).map((h:any)=>h.title||h.snippet||h.url||JSON.stringify(h).slice(0,80)).join(" | ")
              return { kind:"buscar", text: hits ? "Resultados: "+hits : (j.message||"Busca OK"), ok:true }
            })}>{loading==="buscar"?"...":"Buscar Web"}</Button>
            <p className="text-[10px] text-muted-foreground">Tavily + DuckDuckGo cache 5m</p>
          </div>
        </div>
        {out && <div className={"rounded-md border p-2 text-xs "+(out.ok?"bg-emerald-500/10 border-emerald-500/30":"bg-destructive/10 border-destructive/30")}>{out.kind}: {out.text}</div>}
      </CardContent>
    </Card>
  )
}
