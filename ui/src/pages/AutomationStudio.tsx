import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { apiFetch, getUserId } from "@/lib/api"
import { Zap, Play, Pause, Trash2, Settings, Workflow } from "lucide-react"

type Workflow = { id: string; name: string; description: string; status: "active" | "paused"; triggers: string[]; actions: string[] }

export default function AutomationStudio() {
  const [workflows, setWorkflows] = useState<Workflow[]>([
    { id: "1", name: "Daily Summary", description: "Resumo diário de tarefas", status: "active", triggers: ["cron:0 9 * * *"], actions: ["send_daily_summary"] },
    { id: "2", name: "Email Alert", description: "Alerta de e-mails importantes", status: "paused", triggers: ["email:high_priority"], actions: ["send_notification"] },
  ])
  const [newWorkflowName, setNewWorkflowName] = useState("")
  const [newWorkflowDesc, setNewWorkflowDesc] = useState("")
  const [loading, setLoading] = useState(false)

  const handleCreateWorkflow = () => {
    if (!newWorkflowName.trim()) return
    
    const newWorkflow: Workflow = {
      id: Date.now().toString(),
      name: newWorkflowName,
      description: newWorkflowDesc || "Sem descrição",
      status: "paused",
      triggers: [],
      actions: [],
    }
    
    setWorkflows((w) => [...w, newWorkflow])
    setNewWorkflowName("")
    setNewWorkflowDesc("")
  }

  const handleToggleStatus = (id: string) => {
    setWorkflows((w) => w.map(wf => 
      wf.id === id ? { ...wf, status: wf.status === "active" ? "paused" : "active" } : wf
    ))
  }

  const handleDelete = (id: string) => {
    setWorkflows((w) => w.filter(wf => wf.id !== id))
  }

  return (
    <div className="space-y-4">
      <Card className="glass border-cyan-500/20" glassStrong>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-cyan-100">
            <Zap className="w-5 h-5 text-cyan-400" />
            Automation Studio
            <Badge variant="glass" className="ml-2 font-mono text-[10px]">{workflows.length} workflows</Badge>
          </CardTitle>
          <p className="text-xs text-cyan-200/50 font-mono">
            Sir, Automation Studio — workflows, triggers e skills.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Create Workflow */}
          <div className="space-y-2 p-4 glass-subtle border border-cyan-500/15 rounded-lg">
            <Input
              glass
              placeholder="Nome do workflow..."
              value={newWorkflowName}
              onChange={(e) => setNewWorkflowName(e.target.value)}
            />
            <Textarea
              placeholder="Descrição do workflow..."
              value={newWorkflowDesc}
              onChange={(e) => setNewWorkflowDesc(e.target.value)}
              rows={2}
            />
            <div className="flex justify-end">
              <Button onClick={handleCreateWorkflow} disabled={!newWorkflowName.trim()} className="bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_12px_rgba(6,182,212,0.4)]">
                <Workflow className="w-4 h-4 mr-2" />
                Criar Workflow
              </Button>
            </div>
          </div>

          {/* Workflows List */}
          <div className="h-[40vh] overflow-y-auto rounded-md border border-cyan-500/10 bg-black/30 p-3 space-y-3 backdrop-blur">
            {workflows.length === 0 ? (
              <div className="text-center text-cyan-200/40 py-8">
                <Workflow className="w-12 h-12 mx-auto mb-2 text-cyan-400/30" />
                <p className="text-sm">Nenhum workflow configurado, Sir.</p>
              </div>
            ) : (
              workflows.map((wf) => (
                <div key={wf.id} className="glass-subtle border border-cyan-500/15 rounded-lg p-4 backdrop-blur">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-sm font-semibold text-cyan-100">{wf.name}</h3>
                        <Badge variant={wf.status === "active" ? "success" : "secondary"} className="text-[10px]">
                          {wf.status === "active" ? "Ativo" : "Pausado"}
                        </Badge>
                      </div>
                      <p className="text-xs text-cyan-200/60 mb-2">{wf.description}</p>
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1">
                          <Settings className="w-3 h-3 text-cyan-400/50" />
                          <span className="text-[10px] text-cyan-200/40">{wf.triggers.length} triggers</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Zap className="w-3 h-3 text-cyan-400/50" />
                          <span className="text-[10px] text-cyan-200/40">{wf.actions.length} ações</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleStatus(wf.id)}
                        className={wf.status === "active" ? "border-amber-500/30 hover:bg-amber-500/10 text-amber-400" : "border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-400"}
                      >
                        {wf.status === "active" ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDelete(wf.id)}
                        className="border-red-500/30 hover:bg-red-500/10 text-red-400"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
