"""Ranking dos cerebros por uso real (REGRAS PURAS): o mais rapido e confiavel para a funcao vai na frente.

`stats[chave] = {"n": chamadas, "ok": chamadas que deram certo, "median": mediana dos segundos ate o primeiro token}`.
Sem dados suficientes (menos de MIN_CALLS chamadas em pelo menos dois cerebros) a ordem de conexao e mantida.
"""
from __future__ import annotations

from statistics import median
from typing import Mapping, Sequence

MIN_CALLS = 5  # chamadas minimas de um cerebro para ele ser comparado
FAIL_COST_S = 30.0  # cada falha "custa" isto (proporcional a taxa de falha): quem falha muito desce, mesmo rapido


def _score(s: Mapping) -> float:
    n = max(int(s.get("n", 0)), 1)
    ok_rate = min(max(int(s.get("ok", 0)) / n, 0.0), 1.0)
    med = float(s["median"]) if s.get("median") is not None else FAIL_COST_S
    return med + (1.0 - ok_rate) * FAIL_COST_S


def rank(keys: Sequence[str], stats: Mapping[str, Mapping]) -> list[str]:
    """Reordena `keys` (ordem de conexao) pelo desempenho. Empate respeita a ordem original; cerebro sem historico fica no meio."""
    keys = list(keys)
    scored = {k: _score(stats[k]) for k in keys if k in stats and int(stats[k].get("n", 0)) >= MIN_CALLS}
    if len(scored) < 2:
        return keys
    neutral = median(scored.values())
    return sorted(keys, key=lambda k: (scored.get(k, neutral), keys.index(k)))
