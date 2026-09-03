import { useState } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
export function Chat() {
  const [input, setInput] = useState("")
  const [msgs, setMsgs] = useState<{role:string, content:string}[]>([{role:"assistant", content:"Ola! Sou o Jefrey — 1 programa, 7 pecas. Como posso ajudar?"}])
  const send = async () => {
    if(!input.trim()) return
    const user = {role:"user", content: input}
    setMsgs(m=>[...m, user])
    setInput("")
    try {
      const r = await fetch("/chat", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({message: user.content, thread_id: "demo-1"})})
      const j = await r.json()
      setMsgs(m=>[...m, {role:"assistant", content: j.response || j.message || JSON.stringify(j).slice(0,500)}])
    } catch(e:any) {
      setMsgs(m=>[...m, {role:"assistant", content: "Sem conexao com API :8000 — verifique docker compose ps 7/7. Erro: "+String(e)}])
    }
  }
  return (
    <div className="grid gap-4">
      <Card><CardHeader><CardTitle>Chat — thread_id demo-1</CardTitle></CardHeader><CardContent className="space-y-2">
        <div className="h-[420px] overflow-auto border rounded p-3 space-y-2 bg-muted/20">
          {msgs.map((m,i)=>(<div key={i} className={m.role==="user"?"text-right":"text-left"}><span className={m.role==="user"?"inline-block bg-primary text-primary-foreground px-3 py-2 rounded-lg":"inline-block bg-card border px-3 py-2 rounded-lg"}>{m.content}</span></div>))}
        </div>
        <div className="flex gap-2">
          <input className="flex-1 border rounded px-3 py-2" placeholder="Digite sua mensagem..." value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} />
          <Button onClick={send}>Enviar</Button>
        </div>
      </CardContent></Card>
    </div>
  )
}
