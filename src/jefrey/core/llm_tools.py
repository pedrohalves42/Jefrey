"""Chamada de ferramentas nativa para Ollama, compativel-OpenAI e Claude.

Formato neutro de mensagens (o que o agente usa):
  {"role": "system"|"user"|"assistant", "content": str, "tool_calls": [ToolCall-dict]?}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}
ToolCall-dict = {"id": str, "name": str, "arguments": dict}

Ferramentas neutras: {"name", "description", "parameters": <JSON Schema>}.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Union


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


StreamItem = Union[str, ToolCall]


def _args(value: Any) -> dict:
    """Argumentos podem chegar como dict ou como texto JSON; qualquer outra coisa vira {}."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


# --------------------------------------------------------------------------- definicoes
def tool_defs(provider: str, tools: list[dict]) -> list[dict]:
    if provider == "anthropic":
        return [{"name": t["name"], "description": t.get("description", ""),
                 "input_schema": t.get("parameters") or {"type": "object", "properties": {}}} for t in tools]
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t.get("parameters") or {"type": "object", "properties": {}}}}
            for t in tools]


# --------------------------------------------------------------------------- mensagens
def to_provider_messages(provider: str, messages: list[dict]) -> tuple[str, list[dict]]:
    """Converte mensagens neutras. Retorna (system, mensagens); system so e separado no Claude."""
    if provider == "anthropic":
        return _to_anthropic(messages)
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            calls = m["tool_calls"]
            if provider == "ollama":
                out.append({"role": "assistant", "content": m.get("content") or "",
                            "tool_calls": [{"function": {"name": c["name"], "arguments": c.get("arguments") or {}}} for c in calls]})
            else:
                out.append({"role": "assistant", "content": m.get("content") or None,
                            "tool_calls": [{"id": c["id"], "type": "function",
                                            "function": {"name": c["name"],
                                                         "arguments": json.dumps(c.get("arguments") or {}, ensure_ascii=False)}}
                                           for c in calls]})
        elif role == "tool":
            if provider == "ollama":
                out.append({"role": "tool", "tool_name": m.get("name", ""), "content": m.get("content", "")})
            else:
                out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""), "content": m.get("content", "")})
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return "", out


def _to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    system = "\n\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        if role == "assistant" and m.get("tool_calls"):
            blocks: list[dict] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for c in m["tool_calls"]:
                blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c.get("arguments") or {}})
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            block = {"type": "tool_result", "tool_use_id": m.get("tool_call_id", ""), "content": m.get("content", "")}
            # resultados consecutivos precisam ir numa unica mensagem de usuario
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) \
                    and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return system, out


# --------------------------------------------------------------------------- streaming
class StreamParser:
    """Le o stream de um provedor e devolve texto (str) e chamadas de ferramenta (ToolCall)."""

    def __init__(self, provider: str):
        self.provider = provider
        self.done = False
        self._n = 0
        self._acc: dict[int, dict] = {}  # openai: index -> {id,name,args}; anthropic: index -> {...}

    def _next_id(self) -> str:
        self._n += 1
        return f"call_{self._n}"

    def feed(self, line: str) -> list[StreamItem]:
        line = line.strip()
        if not line:
            return []
        if self.provider == "ollama":
            return self._ollama(line)
        if not line.startswith("data:"):
            return []
        payload = line[5:].strip()
        if payload == "[DONE]":
            self.done = True
            return self.flush()
        try:
            data = json.loads(payload)
        except ValueError:
            return []
        return self._openai(data) if self.provider == "openai" else self._anthropic(data)

    # ---- ollama: cada linha e um JSON; tool_calls chegam completos
    def _ollama(self, line: str) -> list[StreamItem]:
        try:
            data = json.loads(line)
        except ValueError:
            return []
        out: list[StreamItem] = []
        msg = data.get("message") or {}
        if msg.get("content"):
            out.append(msg["content"])
        for c in msg.get("tool_calls") or []:
            fn = (c or {}).get("function") or {}
            if fn.get("name"):
                out.append(ToolCall(self._next_id(), fn["name"], _args(fn.get("arguments"))))
        if data.get("done"):
            self.done = True
        return out

    # ---- openai: tool_calls chegam em pedacos, acumulados por indice
    def _openai(self, data: dict) -> list[StreamItem]:
        out: list[StreamItem] = []
        choices = data.get("choices") or []
        if not choices:
            return out
        choice = choices[0]
        delta = choice.get("delta") or {}
        if delta.get("content"):
            out.append(delta["content"])
        for tc in delta.get("tool_calls") or []:
            idx = int(tc.get("index", 0))
            slot = self._acc.setdefault(idx, {"id": "", "name": "", "args": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["args"] += fn["arguments"]
        if choice.get("finish_reason") in ("tool_calls", "stop", "length"):
            out.extend(self.flush())
        return out

    # ---- anthropic: blocos tool_use com input_json_delta
    def _anthropic(self, data: dict) -> list[StreamItem]:
        kind = data.get("type")
        idx = int(data.get("index", 0))
        out: list[StreamItem] = []
        if kind == "content_block_start":
            block = data.get("content_block") or {}
            if block.get("type") == "tool_use":
                self._acc[idx] = {"id": block.get("id") or self._next_id(), "name": block.get("name", ""), "args": ""}
        elif kind == "content_block_delta":
            d = data.get("delta") or {}
            if d.get("type") == "input_json_delta":
                if idx in self._acc:
                    self._acc[idx]["args"] += d.get("partial_json", "")
            elif d.get("text"):  # text_delta (ou variantes sem "type")
                out.append(d["text"])
        elif kind == "content_block_stop":
            slot = self._acc.pop(idx, None)
            if slot and slot["name"]:
                out.append(ToolCall(slot["id"], slot["name"], _args(slot["args"])))
        elif kind == "message_stop":
            self.done = True
            out.extend(self.flush())
        return out

    def flush(self) -> list[StreamItem]:
        """Emite chamadas acumuladas que ainda nao foram entregues (openai)."""
        out: list[StreamItem] = []
        for idx in sorted(self._acc):
            slot = self._acc[idx]
            if slot["name"]:
                out.append(ToolCall(slot["id"] or self._next_id(), slot["name"], _args(slot["args"])))
        self._acc.clear()
        return out
