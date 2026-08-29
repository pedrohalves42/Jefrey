"""Skill: Automação e Workflows."""
from __future__ import annotations
from typing import Any
import json
import uuid
import logging
from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.memory import get_memory_manager

logger = logging.getLogger(__name__)

WORKFLOWS_DIR = Path("data/workflows")


class AutomationSkill(SkillBase):
    metadata = SkillMetadata(
        name="automation",
        description="Cria e executa workflows de automação multi-passo",
        tags=["automation", "workflow", "productivity"],
        enabled_by_default=True,
    )
    
    def __init__(self):
        super().__init__()
        self.memory = get_memory_manager()
        WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    
    def initialize(self) -> bool:
        return True
    
    def get_tools(self) -> list:
        return [
            self.create_workflow,
            self.run_workflow,
            self.list_workflows,
            self.get_workflow,
            self.delete_workflow,
            self.plan_task,
        ]
    
    @tool(description="Cria um workflow de automação salvo")
    async def create_workflow(
        self,
        name: str,
        description: str,
        steps: list[dict],
        tags: list[str] | None = None,
    ) -> dict:
        """
        Cria workflow.
        steps: lista de {id, tool, params, output_var?, condition?}
        Exemplo:
        [
            {"id": "1", "tool": "web_search", "params": {"query": "clima SP"}, "output_var": "weather"},
            {"id": "2", "tool": "notes_save", "params": {"title": "Clima", "content": "{weather}"}}
        ]
        """
        workflow_id = str(uuid.uuid4())[:8]
        workflow = {
            "id": workflow_id,
            "name": name,
            "description": description,
            "steps": steps,
            "tags": tags or [],
            "created_at": __import__("datetime").datetime.now().isoformat(),
        }
        
        file_path = WORKFLOWS_DIR / f"{workflow_id}.json"
        file_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False))
        
        logger.info(f"Workflow criado: {name} ({workflow_id})")
        return {"id": workflow_id, "name": name, "message": f"✅ Workflow '{name}' criado"}
    
    @tool(description="Executa um workflow salvo")
    async def run_workflow(
        self,
        workflow_id: str,
        params: dict | None = None,
    ) -> dict:
        """Executa workflow passo a passo com substituição de variáveis."""
        file_path = WORKFLOWS_DIR / f"{workflow_id}.json"
        if not file_path.exists():
            # Tenta buscar por nome
            for f in WORKFLOWS_DIR.glob("*.json"):
                wf = json.loads(f.read_text())
                if wf["name"] == workflow_id or wf["id"] == workflow_id:
                    file_path = f
                    workflow_id = wf["id"]
                    break
            else:
                return {"error": f"Workflow não encontrado: {workflow_id}"}
        
        workflow = json.loads(file_path.read_text())
        params = params or {}
        context = {**params}
        results = []
        
        from src.jefrey.skills import skill_registry
        
        for step in workflow["steps"]:
            step_id = step["id"]
            tool_name = step["tool"]
            step_params = step.get("params", {})
            output_var = step.get("output_var")
            
            # Substitui variáveis nos params
            resolved_params = self._resolve_vars(step_params, context)
            
            # Executa tool
            tool = skill_registry.get_tool(tool_name)
            if not tool:
                return {"error": f"Ferramenta não encontrada: {tool_name}", "step": step_id}
            
            try:
                result = await tool.ainvoke(resolved_params)
                results.append({"step": step_id, "tool": tool_name, "result": result})
                
                if output_var:
                    context[output_var] = result
                    
            except Exception as e:
                logger.error(f"Erro no step {step_id}: {e}")
                return {"error": str(e), "step": step_id, "results_so_far": results}
        
        return {
            "workflow_id": workflow_id,
            "completed": True,
            "steps_executed": len(results),
            "results": results,
            "final_context": context,
        }
    
    def _resolve_vars(self, obj: Any, context: dict) -> Any:
        """Resolve variáveis {var} em strings recursivamente."""
        if isinstance(obj, str):
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in obj:
                    # Converte valor para string se necessário
                    if isinstance(value, dict):
                        import json
                        value = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, list):
                        import json
                        value = json.dumps(value, ensure_ascii=False)
                    elif not isinstance(value, str):
                        value = str(value)
                    obj = obj.replace(placeholder, value)
            return obj
        elif isinstance(obj, dict):
            return {k: self._resolve_vars(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_vars(item, context) for item in obj]
        return obj
    
    @tool(description="Lista workflows salvos")
    async def list_workflows(self, tags: list[str] | None = None) -> list[dict]:
        """Lista workflows salvos."""
        workflows = []
        for f in WORKFLOWS_DIR.glob("*.json"):
            wf = json.loads(f.read_text())
            if tags is None or any(t in wf.get("tags", []) for t in tags):
                workflows.append({
                    "id": wf["id"],
                    "name": wf["name"],
                    "description": wf["description"],
                    "tags": wf.get("tags", []),
                    "steps_count": len(wf["steps"]),
                    "created_at": wf["created_at"],
                })
        return sorted(workflows, key=lambda w: w["created_at"], reverse=True)
    
    @tool(description="Obtém detalhes de um workflow")
    async def get_workflow(self, workflow_id: str) -> dict | None:
        """Obtém workflow completo."""
        file_path = WORKFLOWS_DIR / f"{workflow_id}.json"
        if file_path.exists():
            return json.loads(file_path.read_text())
        
        # Busca por nome
        for f in WORKFLOWS_DIR.glob("*.json"):
            wf = json.loads(f.read_text())
            if wf["name"] == workflow_id:
                return wf
        return None
    
    @tool(description="Remove workflow")
    async def delete_workflow(self, workflow_id: str) -> dict:
        """Remove workflow."""
        file_path = WORKFLOWS_DIR / f"{workflow_id}.json"
        if file_path.exists():
            file_path.unlink()
            return {"success": True, "message": f"Workflow {workflow_id} removido"}
        return {"error": "Workflow não encontrado"}
    
    @tool(description="Planeja tarefa complexa em steps (usa LLM do agente)")
    async def plan_task(self, goal: str, context: str | None = None) -> dict:
        """
        Gera plano de execução para objetivo complexo.
        O agente (LLM) deve chamar esta tool e depois executar os steps.
        """
        # Salva o plano como nota para referência
        plan_content = f"Objetivo: {goal}\n\nContexto: {context or 'N/A'}\n\n---\nPlano a ser executado pelo agente."
        note_id = self.memory.save_important_memory(
            plan_content,
            tags=["#automation", "#plan"],
            source="planning",
            goal=goal,
        )
        
        return {
            "goal": goal,
            "plan_note_id": note_id,
            "message": f"Plano salvo (ID: {note_id[:8]}...). O agente deve agora decompor em steps executáveis.",
            "suggestion": "Use as ferramentas disponíveis para executar cada passo do plano.",
        }


@skill("automation", "Cria e executa workflows de automação multi-passo", tags=["automation", "workflow"])
class _AutomationWrapper(AutomationSkill):
    pass