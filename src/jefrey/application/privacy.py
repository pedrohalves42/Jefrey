"""Casos de uso: seus dados (LGPD): ver o que o Jefrey guarda, baixar uma copia e apagar tudo.

"Apagar tudo" remove os dados PESSOAIS da pessoa (nome, conversas, fatos, diario, estudos, resumos, lembretes, notas e memorias,
WhatsApp e conexoes com o Google). Nao remove a escolha da inteligencia (modelo/chave), que e do programa e nao da pessoa.
Registros de seguranca (auditoria de aprovacoes) ficam: nao tem o texto das conversas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from src.jefrey.ports.registry import use

logger = logging.getLogger(__name__)


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception as e:  # uma parte quebrada nao pode impedir a pessoa de ver/apagar o resto
        logger.warning("privacidade: parte indisponivel (%s)", type(e).__name__)
        return default


def export_all(user_id: str) -> dict:
    """Tudo que o Jefrey guarda sobre a pessoa, em um dicionario legivel (vira JSON)."""
    d = use("personal_data")
    out: dict[str, Any] = {"gerado_em": datetime.now(timezone.utc).isoformat(), "pessoa": user_id}
    out["nome"] = _safe(lambda: d.name(user_id))
    out["o_que_aprendi"] = _safe(lambda: [{"tipo": f["kind"], "texto": f["text"], "delicado": f["sensitive"], "desde": f["created_at"]}
                                          for f in d.facts(user_id)], [])
    out["diario"] = _safe(lambda: d.diary(user_id), [])
    out["estudos"] = _safe(lambda: [{"assunto": t["title"], "nivel": t["level_label"], "guia": t["body"], "fontes": t["sources"]} for t in d.studies(user_id)], [])
    out["resumos_da_manha"] = _safe(lambda: [{"dia": b["day"], "texto": b["text"]} for b in d.briefings(user_id)], [])
    out["lembretes_pendentes"] = _safe(lambda: [{"texto": r["text"], "quando": r["due_label"]} for r in d.reminders(user_id)], [])
    out["memorias_e_notas"] = _safe(lambda: [{"texto": m["content"], "quando": m["metadata"].get("timestamp")} for m in d.memories(user_id)], [])
    out["conversas"] = _safe(lambda: [{"quando": r["ts"], "quem": "voce" if r["role"] == "user" else "jefrey", "texto": r["content"]} for r in d.conversation(user_id)], [])

    def wa() -> dict:
        w = d.whatsapp(user_id)
        return {"conversas_liberadas": [{"nome": c["display"], "modo": c["mode"]} for c in w["chats"]],
                "respostas": [{"conversa": x["chat"], "mensagem_recebida": x["incoming"], "resposta": x["reply"], "situacao": x["status"]} for x in w["drafts"]]}

    out["whatsapp"] = _safe(wa, {})
    g = _safe(lambda: d.google(user_id), {})
    out["google"] = {"conectado": bool(g.get("connected")), "email": g.get("email"), "servicos": g.get("services", [])}
    return out


def summary(user_id: str) -> dict:
    """Contagens simples para a tela (sem o conteudo)."""
    d = export_all(user_id)
    return {"nome": bool(d["nome"]), "fatos": len(d["o_que_aprendi"]), "diario": len(d["diario"]), "assuntos": len(d["estudos"]),
            "lembretes": len(d["lembretes_pendentes"]), "memorias": len(d["memorias_e_notas"]), "mensagens": len(d["conversas"]),
            "whatsapp": len(d["whatsapp"].get("respostas", [])) if isinstance(d["whatsapp"], dict) else 0, "google": d["google"]["conectado"]}


def erase_all(user_id: str) -> dict:
    """Apaga os dados pessoais. Devolve o que foi apagado e os tokens do Google para revogar (feito pela rota)."""
    d = use("personal_data")
    res: dict[str, Any] = {}
    res["fatos"] = _safe(lambda: d.forget_facts(user_id), 0)
    res["diario"] = _safe(lambda: d.forget_diary(user_id), 0)
    res["estudos"] = _safe(lambda: d.forget_studies(user_id), 0)
    res["resumos"] = _safe(lambda: d.forget_briefings(user_id), 0)
    res["whatsapp"] = _safe(lambda: d.forget_whatsapp(user_id), 0)
    res["nome"] = _safe(lambda: d.forget_name(user_id), 0)
    res["mensagens"] = _safe(lambda: d.forget_conversation(user_id), 0)
    res["lembretes"] = _safe(lambda: d.cancel_reminders(user_id), 0)
    res["memorias"] = _safe(lambda: d.forget_memories(user_id), 0)
    res["_google_tokens"] = _safe(lambda: d.delete_google_tokens(user_id), [])
    return res
