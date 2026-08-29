"""Agente Principal - LangGraph State Machine."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Annotated
import json
import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

from src.jarvis.core.config import settings
from src.jarvis.core.memory import MemoryManager
from src.jarvis.core.events import event_bus, SystemEvents

logger = logging.getLogger(__name__)


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


class JarvisAgent:
    """Agente principal Jarvis usando LangGraph."""
    
    def __init__(self, tools: list[BaseTool] | None = None):
        self.tools = tools or []
        self.memory = MemoryManager()
        self.llm = self._create_llm()
        self.llm_with_tools = self.llm.bind_tools(self.tools) if self.tools else self.llm
        self.graph = self._build_graph()
        self.checkpointer = MemorySaver()
        self._compiled = self.graph.compile(checkpointer=self.checkpointer)
    
    def _create_llm(self):
        """Cria instância do LLM baseada na configuração."""
        cfg = settings.llm
        
        # Normaliza base_url: remove /v1 se presente no final
        # O langchain-openai adiciona /chat/completions automaticamente
        base_url = cfg.base_url
        if base_url:
            base_url = base_url.rstrip("/")
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]  # Remove o /v1 final
        
        if cfg.provider == "openai":
            # Para endpoints compatíveis com OpenAI (LM Studio, vLLM, Ollama server, etc)
            return ChatOpenAI(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=cfg.api_key or "not-needed",  # Alguns servers locais não exigem
                base_url=base_url,  # SEM /v1 no final!
                streaming=True,
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
            # Ollama nativo não precisa de /v1
            return ChatOllama(
                model=cfg.model,
                temperature=cfg.temperature,
                base_url=base_url or "http://localhost:11434",
            )
        else:
            raise ValueError(f"Provider desconhecido: {cfg.provider}")
    
    def _load_system_prompt(self) -> str:
        """Carrega prompt do sistema."""
        prompt_path = Path("config/prompts/system_prompt.md")
        if prompt_path.exists():
            template = prompt_path.read_text(encoding="utf-8")
            # Substitui placeholders
            return template.format(
                tools=", ".join([t.name for t in self.tools]) if self.tools else "nenhuma",
                version=settings.version,
                user_name=settings.user_name,
            )
        return "Você é o Jefrey, um assistente pessoal avançado."
    
    def _load_skill_prompts(self) -> str:
        """Carrega prompts das skills ativas."""
        skills_dir = Path("config/prompts/skills")
        if not skills_dir.exists():
            return ""
        
        active_skills = [
            k for k, v in settings.skills.model_dump().items() if v
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
    
    async def _load_context(self, state: AgentState) -> AgentState:
        """Carrega contexto de memória."""
        # Memória relevante para a query atual
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
        })
        
        return state
    
    async def _reasoning(self, state: AgentState) -> AgentState:
        """Raciocínio do LLM."""
        # Prepara mensagens com system prompt
        system_prompt = self._load_system_prompt()
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
            })
            
            try:
                tool = tool_map.get(tool_name)
                if not tool:
                    raise ValueError(f"Ferramenta não encontrada: {tool_name}")
                
                result = await tool.ainvoke(tool_args)
                results.append({
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "result": result,
                })
                
                await event_bus.emit_sync(SystemEvents.TOOL_RESULT, {
                    "tool": tool_name,
                    "success": True,
                })
                
            except Exception as e:
                logger.error(f"Erro ao executar {tool_name}: {e}")
                results.append({
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "error": str(e),
                })
                await event_bus.emit_sync(SystemEvents.TOOL_RESULT, {
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
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
    
    async def _save_memory(self, state: AgentState) -> AgentState:
        """Salva memórias importantes."""
        # Salva conversa na memória curta
        if state.user_input:
            last_ai = next((m for m in reversed(state.messages) if isinstance(m, AIMessage)), None)
            if last_ai:
                self.memory.add_conversation(state.user_input, last_ai.content)
        
        await event_bus.emit_sync(SystemEvents.MEMORY_SAVED, {
            "short_term_messages": len(self.memory.short_term.get_messages()),
        })
        
        return state
    
    async def _format_response(self, state: AgentState) -> AgentState:
        """Formata resposta final."""
        state.current_step = "complete"
        return state
    
    async def run(self, user_input: str, thread_id: str = "default") -> str:
        """Executa o agente para uma entrada do usuário."""
        # Estado inicial
        initial_state = AgentState(
            messages=[HumanMessage(content=user_input)],
            user_input=user_input,
        )
        
        await event_bus.emit_sync(SystemEvents.USER_MESSAGE, {"input": user_input})
        
        # Configuração do thread
        config = {"configurable": {"thread_id": thread_id}}
        
        # Executa grafo
        final_state = await self._compiled.ainvoke(initial_state, config=config)
        
        # Extrai resposta final
        ai_messages = [m for m in final_state["messages"] if isinstance(m, AIMessage)]
        response = ai_messages[-1].content if ai_messages else "Sem resposta."
        
        await event_bus.emit_sync(SystemEvents.ASSISTANT_RESPONSE, {"response": response})
        
        return response
    
    async def stream(self, user_input: str, thread_id: str = "default"):
        """Stream da resposta (para UI em tempo real)."""
        initial_state = AgentState(
            messages=[HumanMessage(content=user_input)],
            user_input=user_input,
        )
        
        config = {"configurable": {"thread_id": thread_id}}
        
        async for chunk in self._compiled.astream(initial_state, config=config):
            yield chunk


from pathlib import Path