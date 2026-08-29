"""Agente Principal Jefrey - LangGraph State Machine."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Annotated
import json
import logging

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langsmith import traceable

# Ativa logging estruturado (JSON) no runtime do agente.
import src.jefrey.core.logging  # noqa: F401
from src.jefrey.core.config import get_settings
from src.jefrey.core.policy import get_policy_engine, PolicyContext, Decision
from src.jefrey.core.memory import get_memory_manager
from src.jefrey.core.events import event_bus, SystemEvents
from src.jefrey.core.checkpointer import get_postgres_checkpointer

logger = logging.getLogger(__name__)

# Lazy skill loading - called in __init__
def _get_skill_registry():
    from src.jefrey.skills import skill_registry, load_skills
    load_skills()
    return skill_registry


@dataclass
class AgentState:
    """Estado do agente para LangGraph."""
    messages: Annotated[list[BaseMessage], "add_messages"] = field(default_factory=list)
    user_input: str = ""
    current_step: str = "start"
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    memory_context: dict = field(default_factory=dict)
    error: str | None = None
    metadata: dict = field(default_factory=dict)
    thread_id: str = "default"


class JefreyAgent:
    """Agente principal Jefrey usando LangGraph."""
    
    def __init__(self, tools: list[BaseTool] | None = None):
        # Carrega tools das skills se não fornecido
        if tools is None:
            skill_registry = _get_skill_registry()
            tools = skill_registry.get_all_tools()

        self.tools = tools
        self._backend = None

        # Fase P2: runtime selecionável por config (JEFREY_AGENT__PROVIDER).
        # "openai" -> OpenAI Agents SDK & Responses API (com PostgresSessionStore).
        # default "langgraph" -> LangGraph com checkpointer Postgres (substitui MemorySaver).
        if get_settings().agent.provider == "openai":
            from src.jefrey.core.openai_agent import OpenAIAgent

            self._backend = OpenAIAgent(tools=self.tools)
            self.graph = None
            self._system_prompt_template = None
            return

        self.memory = get_memory_manager()
        self.llm = self._create_llm()
        self.llm_with_tools = self.llm.bind_tools(self.tools) if self.tools else self.llm
        self.graph = self._build_graph()
        self._system_prompt_template = self._load_system_prompt_template()
        self._policy = get_policy_engine()

    async def _compile(self):
        """Compila o grafo LangGraph com o checkpointer Postgres (criado sob demanda)."""
        cp = await get_postgres_checkpointer()
        return self.graph.compile(checkpointer=cp)
    
    def _create_llm(self):
        """Cria instância do LLM baseada na configuração."""
        cfg = get_settings().llm
        
        # base_url já vem normalizado (sem /v1) do config
        base_url = cfg.base_url
        
        if cfg.provider == "openai":
            return ChatOpenAI(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=cfg.api_key or "not-needed",
                base_url=base_url,
                streaming=True,
                default_headers={"User-Agent": "Jefrey/0.1.0"},
            )
        elif cfg.provider == "anthropic":
            return ChatAnthropic(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=cfg.api_key,
                streaming=True,
            )
        elif cfg.provider == "ollama":
            return ChatOllama(
                model=cfg.model,
                temperature=cfg.temperature,
                base_url=base_url or "http://localhost:11434",
                timeout=300,  # 5 min para carregar modelo
                num_ctx=4096,
                num_predict=2048,
            )
        else:
            raise ValueError(f"Provider desconhecido: {cfg.provider}")
    
    def _load_system_prompt_template(self) -> str:
        """Carrega template do prompt do sistema."""
        prompt_path = Path("config/prompts/system_prompt.md")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "Você é o Jefrey, um assistente pessoal avançado."
    
    def _load_skill_prompts(self) -> str:
        """Carrega prompts das skills ativas."""
        skills_dir = Path("config/prompts/skills")
        if not skills_dir.exists():
            return ""
        
        active_skills = [
            k for k, v in get_settings().skills.model_dump().items() if v
        ]
        
        prompts = []
        for skill in active_skills:
            skill_file = skills_dir / f"{skill}.md"
            if skill_file.exists():
                prompts.append(f"## Skill: {skill}\n{skill_file.read_text(encoding='utf-8')}")
        
        return "\n\n".join(prompts)
    
    def _build_graph(self) -> StateGraph:
        """Constrói o grafo de estados do agente."""
        workflow = StateGraph(AgentState)
        
        # Nós
        workflow.add_node("load_context", self._load_context)
        workflow.add_node("reasoning", self._reasoning)
        workflow.add_node("execute_tools", self._execute_tools)
        workflow.add_node("save_memory", self._save_memory)
        workflow.add_node("format_response", self._format_response)
        
        # Edges
        workflow.set_entry_point("load_context")
        workflow.add_edge("load_context", "reasoning")
        workflow.add_conditional_edges(
            "reasoning",
            self._should_use_tools,
            {
                "tools": "execute_tools",
                "respond": "format_response",
            },
        )
        workflow.add_edge("execute_tools", "reasoning")
        workflow.add_edge("format_response", "save_memory")
        workflow.add_edge("save_memory", END)
        
        return workflow
    
    @traceable(name="load_context")
    async def _load_context(self, state: AgentState) -> AgentState:
        """Carrega contexto de memória."""
        context = self.memory.get_context(state.user_input)
        state.memory_context = context
        
        # Adiciona memórias relevantes como mensagens de sistema
        if context["relevant_memories"]:
            mem_text = "\n".join([
                f"[Memória {m['similarity']:.0%}]: {m['content']}"
                for m in context["relevant_memories"]
            ])
            state.messages.insert(0, SystemMessage(
                content=f"Memórias relevantes:\n{mem_text}"
            ))
        
        await event_bus.emit_sync(SystemEvents.MEMORY_RETRIEVED, {
            "count": len(context["relevant_memories"]),
            "query": state.user_input,
            "thread_id": state.thread_id,
        })
        
        return state
    
    @traceable(name="reasoning")
    async def _reasoning(self, state: AgentState) -> AgentState:
        """Raciocínio do LLM."""
        cfg = get_settings()
        
        # Prepara mensagens com system prompt
        system_prompt = self._system_prompt_template.format(
            tools=", ".join([t.name for t in self.tools]) if self.tools else "nenhuma",
            version=cfg.version,
            user_name=cfg.user_name,
            chat_history="",
            relevant_memories="",
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        skill_prompts = self._load_skill_prompts()
        
        full_system = f"{system_prompt}\n\n{skill_prompts}".strip()
        
        messages = [SystemMessage(content=full_system)] + state.messages
        
        # Chama LLM
        response = await self.llm_with_tools.ainvoke(messages)
        state.messages.append(response)
        
        # Captura tool calls se houver
        if hasattr(response, "tool_calls") and response.tool_calls:
            state.tool_calls = response.tool_calls
            state.current_step = "tools"
        
        return state
    
    def _should_use_tools(self, state: AgentState) -> Literal["tools", "respond"]:
        """Decide se deve executar ferramentas."""
        if state.tool_calls:
            return "tools"
        return "respond"
    
    @traceable(name="execute_tools")
    async def _execute_tools(self, state: AgentState) -> AgentState:
        """Executa ferramentas chamadas pelo LLM."""
        tool_map = {tool.name: tool for tool in self.tools}
        results = []
        
        for tool_call in state.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            await event_bus.emit_sync(SystemEvents.TOOL_CALL, {
                "tool": tool_name,
                "args": tool_args,
                "thread_id": state.thread_id,
            })
            
            try:
                tool = tool_map.get(tool_name)
                if not tool:
                    raise ValueError(f"Ferramenta não encontrada: {tool_name}")

                # Policy Engine: aplica RBAC/HITL antes de executar a ferramenta.
                pres = self._policy.decide(tool_name, tool_args, PolicyContext(thread_id=state.thread_id))
                self._policy.audit(tool_name, pres, PolicyContext(thread_id=state.thread_id))
                if pres.decision == Decision.DENY:
                    results.append({
                        "tool_call_id": tool_id, "name": tool_name,
                        "result": f"[BLOQUEADO PELA POLÍTICA] {pres.reason}",
                    })
                    await event_bus.emit_sync(SystemEvents.TOOL_RESULT, {
                        "tool": tool_name, "success": False, "blocked": True,
                        "thread_id": state.thread_id,
                    })
                    continue
                if pres.decision == Decision.HITL:
                    results.append({
                        "tool_call_id": tool_id, "name": tool_name,
                        "result": f"[AGUARDANDO APROVAÇÃO] pedido {pres.approval_id} registrado",
                    })
                    await event_bus.emit_sync(SystemEvents.TOOL_RESULT, {
                        "tool": tool_name, "success": False, "blocked": True,
                        "thread_id": state.thread_id,
                    })
                    continue

                result = await tool.ainvoke(tool_args)
                results.append({
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "result": result,
                })
                
                await event_bus.emit_sync(SystemEvents.TOOL_RESULT, {
                    "tool": tool_name,
                    "success": True,
                    "thread_id": state.thread_id,
                })
                
            except Exception as e:
                logger.error(f"Erro ao executar {tool_name}: {e}", exc_info=True)
                results.append({
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "error": str(e),
                })
                await event_bus.emit_sync(SystemEvents.TOOL_RESULT, {
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                    "thread_id": state.thread_id,
                })
        
        state.tool_results = results
        
        # Adiciona resultados como ToolMessage
        for result in results:
            if "error" in result:
                content = f"Erro: {result['error']}"
            else:
                content = json.dumps(result["result"], ensure_ascii=False)
            
            state.messages.append(ToolMessage(
                content=content,
                tool_call_id=result["tool_call_id"],
            ))
        
        state.tool_calls = []  # Limpa para próximo ciclo
        return state
    
    @traceable(name="save_memory")
    async def _save_memory(self, state: AgentState) -> AgentState:
        """Salva memórias importantes."""
        if state.user_input:
            last_ai = next((m for m in reversed(state.messages) if isinstance(m, AIMessage)), None)
            if last_ai:
                self.memory.add_conversation(state.user_input, last_ai.content)
        
        await event_bus.emit_sync(SystemEvents.MEMORY_SAVED, {
            "short_term_messages": len(self.memory.short_term.get_messages()),
            "thread_id": state.thread_id,
        })
        
        return state
    
    @traceable(name="format_response")
    async def _format_response(self, state: AgentState) -> AgentState:
        """Formata resposta final."""
        state.current_step = "complete"
        return state
    
    @traceable(name="agent_run")
    async def run(self, user_input: str, thread_id: str = "default") -> str:
        """Executa o agente para uma entrada do usuário."""
        if self._backend is not None:
            return await self._backend.run(user_input, thread_id)

        initial_state = AgentState(
            messages=[HumanMessage(content=user_input)],
            user_input=user_input,
            thread_id=thread_id,
        )

        await event_bus.emit_sync(SystemEvents.USER_MESSAGE, {
            "input": user_input,
            "thread_id": thread_id,
        })

        config = {"configurable": {"thread_id": thread_id}}
        compiled = await self._compile()
        final_state = await compiled.ainvoke(initial_state, config=config)

        ai_messages = [m for m in final_state["messages"] if isinstance(m, AIMessage)]
        response = ai_messages[-1].content if ai_messages else "Sem resposta."

        await event_bus.emit_sync(SystemEvents.ASSISTANT_RESPONSE, {
            "response": response,
            "thread_id": thread_id,
        })

        return response
    
    @traceable(name="agent_stream")
    async def stream(self, user_input: str, thread_id: str = "default"):
        """Stream da resposta (para UI em tempo real)."""
        if self._backend is not None:
            async for delta in self._backend.stream(user_input, thread_id):
                yield delta
            return

        initial_state = AgentState(
            messages=[HumanMessage(content=user_input)],
            user_input=user_input,
            thread_id=thread_id,
        )

        config = {"configurable": {"thread_id": thread_id}}

        await event_bus.emit_sync(SystemEvents.USER_MESSAGE, {
            "input": user_input,
            "thread_id": thread_id,
        })

        compiled = await self._compile()
        async for chunk in compiled.astream(initial_state, config=config):
            yield chunk
    
    def get_graph_visualization(self) -> str:
        """Retorna visualização Mermaid do grafo (apenas runtime LangGraph)."""
        if self.graph is None:
            return "(runtime openai: grafo LangGraph indisponível)"
        return self.graph.draw_mermaid()
    
    async def health_check(self) -> dict:
        """Verifica saúde do agente."""
        if self._backend is not None:
            return await self._backend.health_check()

        try:
            # Teste rápido de LLM
            test_resp = await self.llm.ainvoke("OK")
            llm_ok = bool(test_resp.content)
        except Exception as e:
            llm_ok = False
            logger.error(f"Health check LLM falhou: {e}")
        
        try:
            # Teste de memória
            mem_count = self.memory.long_term.count()
            memory_ok = True
        except Exception as e:
            mem_count = 0
            memory_ok = False
            logger.error(f"Health check Memory falhou: {e}")
        
        try:
            # Teste do checkpointer Postgres (substitui o MemorySaver em memória)
            cp = await get_postgres_checkpointer()
            await cp.aget_tuple({"configurable": {"thread_id": "__health__"}})
            checkpoint_ok = True
        except Exception as e:
            checkpoint_ok = False
            logger.error(f"Health check checkpointer falhou: {e}")

        overall = llm_ok and memory_ok and checkpoint_ok
        return {
            "status": "healthy" if overall else "degraded",
            "llm": "ok" if llm_ok else "error",
            "memory": "ok" if memory_ok else "error",
            "checkpoint": "ok" if checkpoint_ok else "error",
            "policy": "disabled" if self._policy.mode == "off" else "enabled",
            "policy_mode": self._policy.mode,
            "memory_count": mem_count,
            "tools_available": len(self.tools),
            "version": get_settings().version,
        }