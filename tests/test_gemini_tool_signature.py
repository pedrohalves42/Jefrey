"""Gemini (modo compativel com OpenAI) exige que a assinatura de raciocinio de cada chamada de ferramenta volte no historico."""
import json

from src.jefrey.domain import llm_tools as T

ASSINATURA = {"google": {"thought_signature": "c2lnbmF0dXJl"}}


def _stream(chunks):
    p = T.StreamParser("openai")
    items = []
    for c in chunks:
        items += p.feed("data: " + json.dumps(c))
    items += p.feed("data: [DONE]")
    return [i for i in items if isinstance(i, T.ToolCall)]


def test_assinatura_do_gemini_e_guardada_e_devolvida():
    calls = _stream([{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "extra_content": ASSINATURA,
                                                             "function": {"name": "list_reminders", "arguments": "{}"}}]},
                                   "finish_reason": "tool_calls"}]}])
    assert len(calls) == 1 and calls[0].extra == ASSINATURA
    historico = [{"role": "assistant", "content": "", "tool_calls": [calls[0].as_dict()]}]
    _, enviado = T.to_provider_messages("openai", historico)
    assert enviado[0]["tool_calls"][0]["extra_content"] == ASSINATURA


def test_sem_assinatura_nada_muda():
    c = T.ToolCall("c1", "x", {"a": 1})
    assert "extra_content" not in c.as_dict()
