"""Tarefa 3 do plano: o Jefrey aprende com o uso qual cerebro e mais rapido e confiavel para cada funcao."""
from src.jefrey.domain.brain_rank import MIN_CALLS, rank


def stats(**kw):
    return {k: {"n": v[0], "ok": v[1], "median": v[2]} for k, v in kw.items()}


def test_o_mais_rapido_e_confiavel_vai_para_a_frente():
    s = stats(gemini=(10, 10, 20.0), groq=(10, 10, 0.5))
    assert rank(["gemini", "groq"], s) == ["groq", "gemini"]


def test_quem_falha_muito_desce_mesmo_sendo_rapido():
    s = stats(rapido_mas_falha=(10, 2, 0.3), lento_confiavel=(10, 10, 4.0))
    assert rank(["rapido_mas_falha", "lento_confiavel"], s) == ["lento_confiavel", "rapido_mas_falha"]


def test_sem_dados_suficientes_mantem_a_ordem_original():
    s = stats(a=(MIN_CALLS - 1, MIN_CALLS - 1, 9.0), b=(MIN_CALLS - 1, MIN_CALLS - 1, 0.1))
    assert rank(["a", "b"], s) == ["a", "b"]
    assert rank(["a", "b"], {}) == ["a", "b"]


def test_cerebro_novo_sem_historico_nao_e_enterrado():
    s = stats(a=(10, 10, 1.0), b=(10, 10, 2.0))
    assert rank(["a", "novo", "b"], s)[0] == "a"
    assert rank(["b", "novo", "a"], s).index("novo") < rank(["b", "novo", "a"], s).index("b") + 2


def test_empate_respeita_a_ordem_de_conexao():
    s = stats(a=(10, 10, 1.0), b=(10, 10, 1.0))
    assert rank(["b", "a"], s) == ["b", "a"]
