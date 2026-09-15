import { useState, useEffect } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useNavigate } from "react-router-dom"
import { Badge } from "@/components/ui/badge"

type SkillDefinition = {
  id: string
  name: string
  description: string
  category: "automation" | "integration" | "memory" | "knowledge" | "ui"
  status: "pending" | "active" | "error"
  lastExecution?: string
  userId?: string
}

export function SkillManager() {
  const navigate = useNavigate()
  const [skills, setSkills] = useState<SkillDefinition[]>([])
  const [newSkill, setNewSkill] = useState<SkillDefinition>({
    id: "",
    name: "",
    description: "",
    category: "automation",
    status: "pending",
  })
  const [isLoading, setIsLoading] = useState(false)

  // Load skills from API or registry
  useEffect(() => {
    // Load registered skills from the Jefrey skill registry
    // This would connect to the skill system
    const mockSkills: SkillDefinition[] = [
      {
        id: "notes",
        name: "Notes",
        description: "CRUD de notas com busca semântica",
        category: "knowledge",
        status: "active",
      },
      {
        id: "automation",
        name: "Automação",
        description: "Workflow automation with user_id isolation",
        category: "automation",
        status: "active",
      },
      {
        id: "web_search",
        name: "Web Search",
        description: "Busca web via Tavily/DDG",
        category: "integration",
        status: "active",
      },
    ]
    setSkills(mockSkills)
  }, [navigate])

  const handleAddSkill = async () => {
    if (!newSkill.name.trim()) return
    setIsLoading(true)
    try {
      // Here we would register the new skill with the Jefrey skill system
      // For now, add to local state and navigate to setup
      const newSkillWithId = {
        ...newSkill,
        id: newSkill.name.toLowerCase().replace(/[^a-z0-9]/g, "_") || crypto.randomUUID(),
        lastExecution: new Date().toISOString(),
      }
      setSkills((prev) => [...prev, newSkillWithId])
      setNewSkill({ id: "", name: "", description: "", category: "automation", status: "pending" })
      // Navigate to skill configuration
      navigate(`/skills/${newSkillWithId.id}/configure`)
    } catch (e) {
      console.error("Failed to add skill:", e)
    } finally {
      setIsLoading(false)
    }
  }

  const handleEditSkill = (id: string) => {
    navigate(`/skills/${id}/configure`)
  }

  return (
    <Card className="glass-strong border-indigo-500/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            {skills.length} Skills
          </Badge>
          Gerenciar Skills
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <p className="text-sm text-muted-foreground">Carregando skills...</p>
        )}

        {skills.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nenhuma skill cadastrada. Clique abaixo para adicionar sua primeira skill.
          </p>
        )}

        <div className="space-y-3 pt-3 border-t border-indigo-500/10">
          {skills.map((skill) => (
            <div key={skill.id} className="flex items-center gap-3 p-2 rounded-md bg-card/50 transition-colors">
              <Badge
                variant={skill.status === "active" ? "default" : skill.status === "error" ? "destructive" : "outline"}
                className="text-xs"
              >
                {skill.status}
              </Badge>
              <span className="font-medium truncate">{skill.name}</span>
              <span className="text-xs text-muted-foreground">
                {skill.description}
              </span>
              <div className="ml-auto flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleEditSkill(skill.id)}
                  aria-label="Configurar skill"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M11 3.979a1 1 0 011.414 1.414l7 7a1 1 0 010 1.414l-7 7a1 1 0 01-1.414-1.414L15 7.079V3.979a1 1 0 011.414-1.414z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M18.364 5.636l-1.414-1.415-7 7a1 1 0 01-1.414 0l-7-7a1 1 0 011.414-1.414L12 9.906l6.364-6.364a1 1 0 011.414 0z"
                    />
                  </svg>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    // Remove skill - in production would have confirmation
                    setSkills((prev) => prev.filter((s) => s.id !== skill.id))
                  }}
                  aria-label="Remover skill"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.832A2 2 0 0116.168 21H7.832a2 2 0 01-1.995-1.832L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3m4 6h.01M4.234 5.234a1 1 0 010 1.414l1.414 1.414a1 1 0 01-1.414 1.414l-1.414-1.414a1 1 0 011.414-1.414l1.414 1.414a1 1 0 011.414 1.414l-1.414 1.414a1 1 0 01-1.414-1.414L4.234 5.234z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M14 7v5a2 2 0 002 2h4a2 2 0 002-2v-5m-7-3h7m-7 0h7m-7-7h7"
                    />
                  </svg>
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>

    {/* Add New Skill Form */}
    <Card className="mt-4 glass-strong border-indigo-500/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Plus className="h-4 w-4 text-indigo-400" />
          Adicionar Nova Skill
          <Badge variant="outline" className="text-xs ml-2">
            +99 mais
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-3">
          Adicione novas capacidades ao Jefrey. O sistema suporta automações, integrações,
          memória e interface personalizada.
        </p>

        <form
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault()
            handleAddSkill()
          }}
          className="space-y-3"
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground uppercase">Nome da Skill</label>
              <Input
                value={newSkill.name}
                onChange={(e) =>
                  setNewSkill({
                    ...newSkill,
                    name: e.target.value,
                  })
                }
                placeholder="Ex: QR Remote, Morning Briefing, HW Monitor"
                required
                disabled={isLoading}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground uppercase">Categoria</label>
              <Select value={newSkill.category} onValueChange={(v: string) =>
                setNewSkill({ ...newSkill, category: v as SkillDefinition["category"] })
              }>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="automation">Automação</SelectItem>
                  <SelectItem value="integration">Integração</SelectItem>
                  <SelectItem value="memory">Memória</SelectItem>
                  <SelectItem value="knowledge">Conhecimento</SelectItem>
                  <SelectItem value="ui">Interface</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground uppercase">Descrição</label>
              <Input
                value={newSkill.description}
                onChange={(e) =>
                  setNewSkill({
                    ...newSkill,
                    description: e.target.value,
                  })
                }
                placeholder="Descreva o que esta skill faz"
                rows={2}
                disabled={isLoading}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground uppercase">Status</label>
              <Select value={newSkill.status} onValueChange={(v: string) =>
                setNewSkill({ ...newSkill, status: v as SkillDefinition["status"] })
              }>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button
            type="submit"
            disabled={isLoading || !newSkill.name.trim()}
            className="w-full"
          >
            {isLoading ? (
              <>
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-b-2 border-current"></span> Adicionando...
              </>
            ) : "Adicionar Skill ao Jefrey"
            }</Button>
        </form>
      </CardContent>
    </Card>
  )
}