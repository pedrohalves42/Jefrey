"""Loop do agente com ferramentas: seleciona, chama (nativo ou texto), executa com seguranca, responde.

Pensado para modelos pequenos e locais:
  - so expoe ao modelo as ferramentas relevantes para a mensagem (menos confusao);
  - pedidos triviais (hora, conta) tem roteador deterministico: nao dependem do modelo;
  - se o modelo escrever a chamada como texto JSON, ela e recuperada.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from src.jefrey.core.llm_tools import ToolCall
from src.jefrey.domain.agenda import agenda_day, day_bounds, format_agenda
from src.jefrey.core.tool_catalog import CATALOG, policy_for
from src.jefrey.core.tool_runtime import ToolOutcome, ToolRuntime, tool_spec

logger = logging.getLogger(__name__)

MAX_STEPS = 4
Event = dict[str, Any]


def _norm(text: str) -> str:
    """minusculas e sem acento: 'Previsão' -> 'previsao'."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


# --------------------------------------------------------------------------- selecao
# Sem sinal na mensagem = nenhuma ferramenta oferecida: conversa e conhecimento geral ficam
# sem ferramentas (modelos pequenos chamam ferramenta a toa ou ficam inseguros quando ha varias).
GROUPS: list[tuple[tuple[str, ...], list[str]]] = [
    (("lembrete", "me lembr", "me avis", "avise-me", "me acorde"), ["set_reminder", "list_reminders", "cancel_reminder"]),
    (("anote", "anota", "anotei", "guarde", "guarda", "guardei", "salve", "salvei", "lembre", "lembra", "nota", "anotac",
      "o que eu te disse", "o que voce sabe", "registre"), ["save_note", "search_notes"]),
    (("hora", "data", "hoje", "amanha", "ontem", "dia da semana", "que dia"), ["current_time"]),
    (("calcul", "quanto e", "quanto da", "porcento", "raiz", "soma", "somar", "multiplic", "dividid", "vezes", "%"), ["calculator"]),
    (("pesquis", "busca", "noticia", "internet", "google", "site ", "na web", "online"), ["search", "search_news", "extract"]),
    (("clima", "tempo em", "temperatura", "chuva", "previsao", "vai chover", "calor", "frio"), ["weather"]),
    (("agenda", "evento", "reuniao", "compromisso", "calendario", "horario livre", "marcar"),
     ["list_events", "create_event", "find_free_slots", "update_event", "delete_event"]),
    (("email", "e-mail", "caixa de entrada", "gmail", "mensagem de"),
     ["list_messages", "get_message", "search_messages", "send_message", "reply_message"]),
    (("tarefa", "a fazer", "afazer", "to-do", "todo"), ["tasks_list", "tasks_add", "tasks_done"]),
    (("contato", "telefone do", "telefone da", "numero do", "numero da", "celular do", "celular da", "e-mail do", "e-mail da"), ["contacts_find"]),
    (("drive", "nuvem"), ["list_files", "search_files", "get_file_metadata", "download_file"]),
    (("arquivo", "pasta", "documento", "txt"), ["files_list", "files_read", "files_write"]),
    (("nota", "anot", "lembre", "guarde", "salve", "apague"), ["list_notes", "get_note", "update_note", "delete_note"]),
    (("automa", "workflow", "rotina"), ["list_workflows", "get_workflow", "create_workflow", "plan_task"]),
    (("abre ", "abra ", "abrir", "abri ", "inicia", "iniciar", "executa", "programa", "aplicativo", "app "), ["open_app", "open_folder", "open_website"]),
    (("site", "youtube", "gmail", "pagina", "navegador", "internet"), ["open_website"]),
    (("pasta", "downloads", "documentos", "area de trabalho", "fotos", "imagens"), ["open_folder"]),
    (("alexa", "echo", "anuncia", "fala na ", "avisa na ", "rotina da", "acende a luz", "apaga a luz"), ["alexa_say", "alexa_routine", "alexa_list"]),
    (("fecha ", "fechar", "feche ", "encerra"), ["close_app"]),
    (("blender", "cubo", "esfera", "objeto 3d", "modelo 3d"), ["app_command"]),
    (("digita", "digite", "escreve no", "escreve na", "escreva no", "escreva na", "atalho", "foca ", "focar", "traz para a frente"), ["focus_window", "type_text", "press_hotkey"]),
    (("musica", "música", "pausa", "pausar", "proxima", "próxima", "toca", "continua"), ["media_control"]),
    (("pesquisa", "pesquisar", "procura", "procurar", "google"), ["search_in_browser"]),
    (("volume", "som ", "mudo", "silenci", "aumenta", "diminui", "mais alto", "mais baixo"), ["set_volume"]),
]


CONTROL_ONLY = {"focus_window", "type_text", "press_hotkey", "close_app", "app_command"}  # agem em outros programas


def begin_turn() -> None:
    """Uma nova fala da pessoa encerra a "parada": ela pode pedir de novo."""
    from src.jefrey.core import halt

    halt.clear()


def select_tools(message: str, available: list[str], offer_all: bool = False) -> list[str]:
    """Ferramentas a oferecer ao modelo.

    Modelo de nuvem (offer_all): TODAS as disponiveis; ele escolhe bem (a mensagem "o que esta acontecendo no Brasil?" nao tem
    palavra-chave nenhuma e mesmo assim precisa da busca). Modelo local pequeno: so os grupos cujas palavras aparecem na mensagem.
    As ferramentas de risco continuam exigindo aprovacao, em qualquer caso.
    """
    msg = _norm(message)
    chosen: list[str] = []
    for words, tools in GROUPS:
        if any(w in msg for w in words):
            chosen += tools
    if offer_all:
        # controle do computador so quando a PESSOA pediu: texto de e-mail/site/documento nunca liga estas ferramentas
        return [t for t in available if t in CATALOG and (t not in CONTROL_ONLY or t in chosen)]
    seen: set[str] = set()
    out = []
    for t in chosen:
        if t in available and t in CATALOG and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# --------------------------------------------------------------------------- roteador
# Casa a mensagem INTEIRA: "que horas sao" dispara; "que horas devo dormir..." nao.
_TIME = re.compile(
    r"^(?:agora )?que horas (?:sao|e)(?: agora| neste momento)?$"
    r"|^(?:qual (?:e )?a |me diga a |diga a )?hora (?:atual|agora)$"
    r"|^(?:que dia e hoje|qual (?:e )?a data (?:de hoje|atual)|data de hoje|em que dia estamos|"
    r"que dia da semana e hoje|qual (?:e )?o dia da semana)$")
_NUM = r"-?\d+(?:[.,]\d+)?"
_OPS = r"(?:\+|-|\*|/|x|×|÷|\^|vezes|mais|menos|dividido por|elevado a)"
_CALC = re.compile(rf"^(?:quanto\s+(?:e|da|fica|vale)|calcule|calcula|resultado\s+de|conta)?\s*"
                   rf"(\(?\s*{_NUM}(?:\s*{_OPS}\s*\(?\s*{_NUM}\s*\)?)+)\s*\??\s*$")
_WORDOPS = [(" vezes ", " * "), (" mais ", " + "), (" menos ", " - "), (" dividido por ", " / "),
            (" elevado a ", " ** "), (" x ", " * "), ("×", "*"), ("÷", "/")]


# Perguntas sobre o que o usuario guardou: o roteador busca; o modelo so RESUME o resultado.
_RECALL = [
    re.compile(r"^(?:o que|oque)\s+(?:eu\s+)?(?:anotei|guardei|salvei|escrevi|te disse|te falei|te contei)\s+(?:sobre|de|do|da|dos|das)\s+(.+)$"),
    re.compile(r"^(?:o que|oque)\s+(?:voce|vc)\s+(?:sabe|lembra|tem)\s+(?:sobre|de|do|da)\s+(.+)$"),
    re.compile(r"^(?:busque|procure|pesquise|ache|encontre)\s+(?:nas|em)\s+(?:minhas\s+)?(?:notas|anotacoes)\s+(?:sobre|de|do|da)?\s*(.+)$"),
    re.compile(r"^(?:quais|mostre|liste|me mostre)\s+(?:sao\s+)?(?:as\s+)?(?:minhas\s+)?(?:notas|anotacoes)\s+(?:sobre|de|do|da)\s+(.+)$"),
]
SUMMARIZE_TOOLS = {"search_notes"}


_LIST_REMINDERS = re.compile(r"^(?:quais|mostre|liste|me mostre|ver|veja|tenho)\s*(?:sao\s+)?(?:os\s+|meus\s+|algum\s+)*lembretes?(?:\s+(?:que\s+)?(?:eu\s+)?(?:tenho|pendentes?))?$"
                             r"|^meus lembretes$|^tem(?:os)? lembretes?$")


_VERBS = r"(?:guarda|guarde|anota|anote|salva|salve|registra|registre|memoriza|memorize)"
_SAVE_TRAIL = re.compile(rf"^(.{{3,400}}?)[.,;!]?\s*(?:por favor,?\s*)?{_VERBS}\s+(?:isso|ai|isso ai|essa informacao|essa info)$")
_SAVE_LEAD = re.compile(rf"^(?:por favor,?\s*)?{_VERBS}(?:\s+ai)?\s*[:,-]\s*(.{{3,600}})$")
_LIST_NOTES = re.compile(r"^(?:o que|oque)\s+(?:eu\s+)?(?:anotei|guardei|salvei)(?:\s+ate\s+agora)?$"
                         r"|^(?:minhas|mostre minhas|me mostre minhas|liste minhas|ver minhas|quais sao minhas|quais as minhas)\s+(?:notas|anotacoes)$")


def _save_request(orig: str, msg: str) -> Optional[str]:
    """'Meu nome e Carla. Guarda isso.' -> 'Meu nome e Carla'  (conteudo vem da propria mensagem)."""
    same = len(orig) == len(msg)
    for pat in (_SAVE_TRAIL, _SAVE_LEAD):
        m = pat.match(msg)
        if m and m.group(1).strip():
            content = (orig[m.start(1):m.end(1)] if same else m.group(1)).strip()
            if _norm(content) not in ("isso", "ai", "isso ai"):
                return content
    return None


def route_intent(message: str) -> Optional[tuple[str, dict]]:
    """Pedidos triviais que NAO precisam do modelo. None = deixa o modelo decidir."""
    orig = message.strip().rstrip("?!. ")
    msg = _norm(orig)
    if len(msg) > 700:
        return None
    if _LIST_REMINDERS.match(msg):
        return "list_reminders", {}
    if _LIST_NOTES.match(msg):
        return "list_notes", {}
    fact = _save_request(orig, msg)
    if fact:
        return "save_note", {"title": fact[:60], "content": fact}
    from src.jefrey.core.reminders import parse_request
    rq = parse_request(message)
    if rq is not None:
        # o horario e interpretado pelo codigo (modelo pequeno erra datas); a ferramenta repete o texto bruto
        return "set_reminder", {"text": rq.text, "when": " ".join(msg.split())}
    if len(msg) > 120:
        return None
    if _TIME.match(msg):
        return "current_time", {}
    day = agenda_day(msg)
    if day:  # "o que tenho hoje?": le a agenda e responde direto (antes: 4 rodadas do modelo, ~20 s)
        from src.jefrey.core.reminders import local_tz

        start, end = day_bounds(day, datetime.now(local_tz()))
        return "list_events", {"time_min": start.isoformat(), "time_max": end.isoformat(), "max_results": 20}
    for pat in _RECALL:
        rm = pat.match(msg)
        if rm and rm.group(1).strip():
            same = len(orig) == len(msg)  # preserva acentos da consulta quando da para alinhar
            query = (orig[rm.start(1):rm.end(1)] if same else rm.group(1)).strip()
            return "search_notes", {"query": query}
    m = _CALC.match(msg)
    if m:
        expr = f" {m.group(1)} "
        for a, b in _WORDOPS:
            expr = expr.replace(a, b)
        expr = expr.strip()
        if re.search(r"\d", expr) and re.search(r"[+\-*/^]", expr[1:]):
            return "calculator", {"expression": expr}
    return None


# --------------------------------------------------------------------------- recuperacao de texto
_TEXT_CALL_HINT = ("{", "[", "```", "<tool_call>")


def looks_like_text_call(text: str) -> bool:
    return text.lstrip().startswith(_TEXT_CALL_HINT)


def parse_text_tool_call(text: str, allowed: set[str]) -> Optional[ToolCall]:
    """Recupera {"name": ..., "arguments": {...}} escrito como texto pelo modelo."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    t = re.sub(r"^<tool_call>\s*|\s*</tool_call>$", "", t).strip()
    try:
        data = json.loads(t)
    except ValueError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except ValueError:
            return None
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict):
        return None
    name = data.get("name") or data.get("tool") or (data.get("function") or {}).get("name")
    args = data.get("arguments", data.get("params", data.get("parameters", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    if name not in allowed or not isinstance(args, dict):
        return None
    return ToolCall("text_call", str(name), args)


# --------------------------------------------------------------------------- loop
@dataclass
class LoopConfig:
    max_steps: int = MAX_STEPS
    offer_all: Optional[bool] = None  # None = automatico: nuvem oferece todas as ferramentas, local so as relevantes


async def _run_tool_with_events(runtime: ToolRuntime, call: ToolCall) -> AsyncIterator[Event | ToolOutcome]:
    """Executa a ferramenta e repassa eventos de aprovacao enquanto espera. Ultimo item: ToolOutcome."""
    q: asyncio.Queue = asyncio.Queue()

    async def hook(approval_id: str, tool: str, info: dict) -> None:
        await q.put({"type": "approval_required", "approval_id": approval_id, "tool": tool,
                     "label": info.get("label", tool), "risk": info.get("risk")})

    runtime.on_approval = hook
    task = asyncio.create_task(runtime.run(call.name, call.arguments))
    try:
        while not task.done():
            try:
                yield await asyncio.wait_for(q.get(), timeout=0.25)
            except asyncio.TimeoutError:
                pass
        while not q.empty():
            yield q.get_nowait()
        yield task.result()
    finally:
        if not task.done():
            task.cancel()  # cliente desconectou: nao deixa a ferramenta rodando solta


def _summary(outcome: ToolOutcome) -> str:
    return outcome.content.replace("\n", " ")[:200]


async def run_agent(
    llm: Any,
    runtime: ToolRuntime,
    messages: list[dict],
    tools: dict[str, Any],
    user_input: str,
    config: Optional[LoopConfig] = None,
) -> AsyncIterator[Event]:
    """Gera eventos {token|tool_start|approval_required|tool_end}. O chamador acrescenta 'done'."""
    begin_turn()
    cfg = config or LoopConfig()
    msgs = list(messages)
    offer_all = cfg.offer_all if cfg.offer_all is not None else bool(getattr(getattr(llm, "config", None), "is_cloud", False))
    offered = select_tools(user_input, list(tools.keys()), offer_all)
    specs = [tool_spec(tools[n]) for n in offered]
    allowed = set(offered)

    # ---- atalho deterministico (hora, contas) ----
    routed = route_intent(user_input)
    if routed and routed[0] in tools:
        name, args = routed
        label = policy_for(name).label if policy_for(name) else name
        yield {"type": "tool_start", "tool": name, "label": label, "risk": "low"}
        outcome: ToolOutcome | None = None
        async for item in _run_tool_with_events(runtime, ToolCall("route", name, args)):
            if isinstance(item, ToolOutcome):
                outcome = item
            else:
                yield item
        assert outcome is not None
        yield {"type": "tool_end", "tool": name, "ok": outcome.ok, "status": outcome.status, "summary": _summary(outcome)}
        if outcome.ok and name not in SUMMARIZE_TOOLS:
            yield {"type": "token", "content": format_agenda(outcome.content, agenda_day(_norm(user_input.strip().rstrip("?!. ")))) if name == "list_events" else outcome.content}
            return
        # busca em notas (ou falha): o modelo responde usando SO o resultado, sem ferramentas
        msgs.append({"role": "assistant", "content": "", "tool_calls": [ToolCall("route", name, args).as_dict()]})
        msgs.append({"role": "tool", "tool_call_id": "route", "name": name, "content": outcome.content})
        msgs.append({"role": "system", "content": (
            "Responda ao usuario usando SOMENTE o resultado da ferramenta acima. "
            "Se nao houver nada relevante, diga com clareza que nao encontrou nada. Nao invente.")})
        emitted = False
        async for item in llm.stream_events(msgs, tools=None):
            if isinstance(item, str) and item:
                emitted = True
                yield {"type": "token", "content": item}
        if not emitted:
            yield {"type": "token", "content": outcome.content if outcome.ok else "Nao consegui consultar isso agora."}
        return

    seen_calls: set[str] = set()
    for step in range(cfg.max_steps + 1):
        use_tools = specs if (step < cfg.max_steps and specs) else None
        text_parts: list[str] = []
        held: list[str] = []
        holding: Optional[bool] = None
        calls: list[ToolCall] = []

        async for item in llm.stream_events(msgs, tools=use_tools):
            if isinstance(item, ToolCall):
                calls.append(item)
                continue
            text_parts.append(item)
            if holding is None and item.strip():
                holding = looks_like_text_call("".join(text_parts)) and use_tools is not None
                if holding is False:
                    yield {"type": "token", "content": "".join(text_parts)}
                    continue
            if holding:
                held.append(item)
            elif holding is False:
                yield {"type": "token", "content": item}
            # holding None (so espacos ate agora): espera o primeiro caractere util

        full = "".join(text_parts)
        if not calls and holding and use_tools is not None:
            recovered = parse_text_tool_call(full, allowed)
            if recovered:
                calls = [recovered]
            else:
                yield {"type": "token", "content": full}  # nao era chamada: era texto mesmo
        elif not calls and holding is None and full:
            yield {"type": "token", "content": full}

        if not calls:
            return

        msgs.append({"role": "assistant", "content": "" if holding else full,
                     "tool_calls": [c.as_dict() for c in calls]})
        for call in calls:
            key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, default=str)}"
            if key in seen_calls:
                msgs.append({"role": "tool", "tool_call_id": call.id, "name": call.name,
                             "content": "Voce ja chamou esta ferramenta com os mesmos argumentos. Use o resultado anterior."})
                continue
            seen_calls.add(key)
            pol = policy_for(call.name)
            yield {"type": "tool_start", "tool": call.name, "label": pol.label if pol else call.name,
                   "risk": pol.risk if pol else "unknown"}
            outcome = None
            async for item in _run_tool_with_events(runtime, call):
                if isinstance(item, ToolOutcome):
                    outcome = item
                else:
                    yield item
            assert outcome is not None
            yield {"type": "tool_end", "tool": call.name, "ok": outcome.ok, "status": outcome.status,
                   "summary": _summary(outcome)}
            msgs.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": outcome.content})

    yield {"type": "token", "content": "Nao consegui concluir isso com as ferramentas disponiveis."}
