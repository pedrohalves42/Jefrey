"""compute_readiness - % Implementacao/Producao/Comercial (Etapa 6.5 DRY - AXIOM/CIPHER)."""
from __future__ import annotations
import argparse
import json
from typing import Final, Literal, TypedDict

# Pesos funcionais (Kleppmann: peso por dominio, nao LOC) - soma 100 (Anderson: fail-closed gate)
WEIGHTS: Final[dict[str, int]] = {
    "Config/Secrets": 10,
    "Postgres+pgvector": 20,
    "Redis Working Memory": 10,
    "Agent LangGraph": 20,
    "Skills": 15,
    "EventBus": 5,
    "Policy/HITL": 10,
    "Infra/Observabilidade": 10,
}

Status = Literal["READY", "PARTIAL", "PLACEHOLDER", "BROKEN", "NOT_IMPLEMENTED", "NOT_VERIFIED"]

FACTOR: Final[dict[str, float]] = {
    "READY": 1.0,
    "PARTIAL": 0.6,
    "PLACEHOLDER": 0.2,
    "BROKEN": 0.0,
    "NOT_IMPLEMENTED": 0.0,
    "NOT_VERIFIED": 0.0,
}

# Estado P0 real pos-6.4 auditado 2026-08-31 (5 READY + 3 PARTIAL = 86.0 impl)
P0_STATUS: Final[dict[str, Status]] = {
    "Config/Secrets": "READY",
    "Postgres+pgvector": "READY",
    "Redis Working Memory": "READY",
    "Agent LangGraph": "READY",
    "Skills": "PARTIAL",
    "EventBus": "READY",
    "Policy/HITL": "PARTIAL",
    "Infra/Observabilidade": "PARTIAL",
}

class ReadinessResult(TypedDict):
    implementacao: float
    producao: float
    comercial: float
    fator_infra: float
    status: dict[str, Status]
    pesos: dict[str, int]

def compute(status: dict[str, Status] | None = None) -> ReadinessResult:
    st = dict(P0_STATUS)
    if status:
        unknown = set(status) - set(WEIGHTS)
        if unknown:
            raise ValueError(f"dominios desconhecidos: {sorted(unknown)} - validos: {sorted(WEIGHTS)}")
        for k, v in status.items():
            if v not in FACTOR:
                raise ValueError(f"status invalido {k}={v!r} - validos: {sorted(FACTOR)}")
        st.update(status)  # type: ignore[arg-type]
    impl = sum(WEIGHTS[k] * FACTOR[st[k]] for k in WEIGHTS) / 100.0
    # fator_infra: 0.73 se docker+healthchecks verdes (pos-6.4), 0.5 caso contrario (AXIOM: observabilidade)
    infra_ok = all(st[k] in ("READY", "PARTIAL") for k in ["Config/Secrets", "Postgres+pgvector", "Redis Working Memory", "Infra/Observabilidade"])
    fator_infra: float = 0.73 if infra_ok else 0.5
    prod = impl * fator_infra
    comercial = prod * 0.90  # go-to-market pos-P0 (Anderson) - sobe com P1 OAuth/UI
    return {
        "implementacao": round(impl * 100, 1),
        "producao": round(prod * 100, 1),
        "comercial": round(comercial * 100, 1),
        "fator_infra": fator_infra,
        "status": st,
        "pesos": dict(WEIGHTS),
    }

def main() -> int:
    ap = argparse.ArgumentParser(description="Calcula prontidao P0->P1 (AXIOM dry-run seguro)")
    ap.add_argument("--json", action="store_true", help="saida JSON")
    ap.add_argument("--status", type=str, default="", help="JSON override ex: '{\"Skills\":\"READY\"}'")
    args = ap.parse_args()
    st: dict[str, Status] = dict(P0_STATUS)  # type: ignore[arg-type]
    if args.status:
        override: dict[str, Status] = json.loads(args.status)
        st.update(override)
    r = compute(st)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Implementacao: {r['implementacao']}%")
        print(f"Producao:      {r['producao']}%")
        print(f"Comercial:     {r['comercial']}%")
        print(f"Fator infra:   {r['fator_infra']}")
        for k in WEIGHTS:
            print(f"  {k:22s} {st[k]:16s} peso {WEIGHTS[k]:2d} fator {FACTOR[st[k]]}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
